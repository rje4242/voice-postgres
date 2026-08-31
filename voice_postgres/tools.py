from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from voice_postgres.config import settings
from voice_postgres.db import connection, fetch_all, fetch_one
from voice_postgres.history import record
from voice_postgres.sql_guard import sanitize_select

log = logging.getLogger(__name__)

ORDER_STATUSES = {"pending", "preparing", "ready", "completed", "cancelled"}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "inspect_schema",
        "description": (
            "Describe tables, views, and columns in the Harbor & Bean Postgres database. "
            "Call this when you need to know what you can query. Optional table_name filters "
            "to one relation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Optional table or view name (for example orders, v_daily_sales).",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "query_database",
        "description": (
            "Run a single read-only SELECT or WITH query against Postgres. "
            "Use this for lookups, totals, rankings, and filters. "
            "Do not include INSERT/UPDATE/DELETE. Results are capped."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A single SELECT or WITH statement.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "type": "function",
        "name": "create_customer",
        "description": "Insert a loyalty customer. Confirm name and email with the operator first.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
            },
            "required": ["name", "email"],
        },
    },
    {
        "type": "function",
        "name": "create_order",
        "description": (
            "Create a ticket: look up the customer by email, add line items by SKU or product "
            "name, decrement stock, and return the new order. Confirm the cart first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_email": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product": {
                                "type": "string",
                                "description": "SKU (e.g. LAT-OAT) or product name.",
                            },
                            "quantity": {"type": "integer", "minimum": 1},
                        },
                        "required": ["product", "quantity"],
                    },
                },
                "notes": {"type": "string"},
                "employee_name": {
                    "type": "string",
                    "description": "Optional barista to attach to the ticket.",
                },
            },
            "required": ["customer_email", "items"],
        },
    },
    {
        "type": "function",
        "name": "update_order_status",
        "description": "Move a ticket to pending, preparing, ready, completed, or cancelled.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer"},
                "status": {
                    "type": "string",
                    "enum": sorted(ORDER_STATUSES),
                },
            },
            "required": ["order_id", "status"],
        },
    },
    {
        "type": "function",
        "name": "adjust_inventory",
        "description": (
            "Change on-hand stock for a product (positive receives, negative waste/sale "
            "correction) and write an inventory_adjustments row."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "SKU or product name.",
                },
                "delta": {"type": "integer", "description": "Signed quantity change."},
                "reason": {"type": "string"},
            },
            "required": ["product", "delta", "reason"],
        },
    },
]


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def dump(payload: Any) -> str:
    return json.dumps(jsonable(payload), default=str)


async def inspect_schema(table_name: str | None = None) -> dict[str, Any]:
    params: list[Any] = []
    where = ""
    if table_name:
        where = "WHERE c.relname = %s"
        params.append(table_name)
    rows = await fetch_all(
        f"""
        SELECT
            n.nspname AS schema,
            c.relname AS name,
            CASE c.relkind
                WHEN 'r' THEN 'table'
                WHEN 'v' THEN 'view'
                ELSE c.relkind::text
            END AS kind,
            obj_description(c.oid) AS comment,
            a.attname AS column_name,
            pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
            NOT a.attnotnull AS nullable,
            col_description(c.oid, a.attnum) AS column_comment
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'v')
          {where}
        ORDER BY c.relname, a.attnum
        """,
        params or None,
    )
    tables: dict[str, Any] = {}
    for row in rows:
        entry = tables.setdefault(
            row["name"],
            {
                "name": row["name"],
                "kind": row["kind"],
                "comment": row["comment"],
                "columns": [],
            },
        )
        entry["columns"].append(
            {
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["nullable"],
                "comment": row["column_comment"],
            }
        )
    if table_name and not tables:
        return {"error": f"No table or view named {table_name!r}."}
    return {"relations": list(tables.values())}


def _apply_limit(sql: str) -> str:
    # Wrap so we can cap rows even when the model omitted LIMIT.
    return (
        f"SELECT * FROM ({sql}) AS voice_postgres_q "
        f"LIMIT {int(settings.query_row_limit)}"
    )


async def query_database(sql: str) -> dict[str, Any]:
    cleaned = sanitize_select(sql)
    wrapped = _apply_limit(cleaned)
    timeout_ms = int(settings.query_timeout_ms)
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SET TRANSACTION READ ONLY")
            await cur.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
            await cur.execute(wrapped)
            rows = await cur.fetchall()
            columns = [desc.name for desc in cur.description] if cur.description else []
        await conn.commit()
    result = {
        "sql": cleaned,
        "columns": columns,
        "row_count": len(rows),
        "truncated_to": settings.query_row_limit,
        "rows": jsonable(rows),
    }
    record("sql", source="tool", sql=cleaned, row_count=len(rows), columns=columns)
    return result


async def create_customer(
    name: str,
    email: str,
    phone: str | None = None,
) -> dict[str, Any]:
    row = await fetch_one(
        """
        INSERT INTO customers (name, email, phone)
        VALUES (%s, %s, %s)
        RETURNING id, name, email, phone, loyalty_points, created_at
        """,
        (name.strip(), email.strip().lower(), phone.strip() if phone else None),
    )
    return {"customer": jsonable(row)}


async def _find_product(conn, product: str) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, sku, name, unit_price, stock_qty
            FROM products
            WHERE lower(sku) = lower(%s)
               OR lower(name) = lower(%s)
            ORDER BY CASE WHEN lower(sku) = lower(%s) THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (product, product, product),
        )
        return await cur.fetchone()


async def create_order(
    customer_email: str,
    items: list[dict[str, Any]],
    notes: str | None = None,
    employee_name: str | None = None,
) -> dict[str, Any]:
    if not items:
        return {"error": "Order has no items."}

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, email FROM customers WHERE lower(email) = lower(%s)",
                (customer_email.strip(),),
            )
            customer = await cur.fetchone()
            if not customer:
                await conn.rollback()
                return {"error": f"No customer with email {customer_email!r}."}

            employee_id = None
            if employee_name:
                await cur.execute(
                    "SELECT id FROM employees WHERE lower(name) = lower(%s) AND active LIMIT 1",
                    (employee_name.strip(),),
                )
                emp = await cur.fetchone()
                if emp:
                    employee_id = emp["id"]

            await cur.execute(
                """
                INSERT INTO orders (customer_id, employee_id, status, notes)
                VALUES (%s, %s, 'pending', %s)
                RETURNING id, status, placed_at
                """,
                (customer["id"], employee_id, notes),
            )
            order = await cur.fetchone()
            assert order is not None

            line_rows: list[dict[str, Any]] = []
            for raw in items:
                product_key = str(raw.get("product") or "").strip()
                qty = int(raw.get("quantity") or 0)
                if not product_key or qty < 1:
                    await conn.rollback()
                    return {"error": f"Invalid line item: {raw!r}."}
                product = await _find_product(conn, product_key)
                if not product:
                    await conn.rollback()
                    return {"error": f"Unknown product {product_key!r}."}
                if product["stock_qty"] < qty:
                    await conn.rollback()
                    return {
                        "error": (
                            f"Not enough stock for {product['name']} "
                            f"(have {product['stock_qty']}, need {qty})."
                        )
                    }
                await cur.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (order["id"], product["id"], qty, product["unit_price"]),
                )
                await cur.execute(
                    """
                    UPDATE products SET stock_qty = stock_qty - %s
                    WHERE id = %s
                    """,
                    (qty, product["id"]),
                )
                await cur.execute(
                    """
                    INSERT INTO inventory_adjustments (product_id, delta, reason)
                    VALUES (%s, %s, %s)
                    """,
                    (product["id"], -qty, f"order {order['id']}"),
                )
                line_rows.append(
                    {
                        "sku": product["sku"],
                        "name": product["name"],
                        "quantity": qty,
                        "unit_price": product["unit_price"],
                    }
                )

            await cur.execute(
                "SELECT COALESCE(SUM(quantity * unit_price), 0) AS total FROM order_items WHERE order_id = %s",
                (order["id"],),
            )
            total_row = await cur.fetchone()
        await conn.commit()

    return {
        "order_id": order["id"],
        "status": order["status"],
        "customer": customer["name"],
        "email": customer["email"],
        "items": jsonable(line_rows),
        "total": jsonable(total_row["total"] if total_row else 0),
        "notes": notes,
    }


async def update_order_status(order_id: int, status: str) -> dict[str, Any]:
    status = status.strip().lower()
    if status not in ORDER_STATUSES:
        return {"error": f"Invalid status {status!r}."}
    row = await fetch_one(
        """
        UPDATE orders
        SET status = %s,
            completed_at = CASE
                WHEN %s IN ('completed', 'cancelled') THEN COALESCE(completed_at, NOW())
                ELSE completed_at
            END
        WHERE id = %s
        RETURNING id, customer_id, status, notes, placed_at, completed_at
        """,
        (status, status, int(order_id)),
    )
    if not row:
        return {"error": f"No order with id {order_id}."}
    return {"order": jsonable(row)}


async def adjust_inventory(product: str, delta: int, reason: str) -> dict[str, Any]:
    delta = int(delta)
    if delta == 0:
        return {"error": "delta must be non-zero."}
    async with connection() as conn:
        found = await _find_product(conn, product)
        if not found:
            await conn.rollback()
            return {"error": f"Unknown product {product!r}."}
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE products
                SET stock_qty = stock_qty + %s
                WHERE id = %s AND stock_qty + %s >= 0
                RETURNING id, sku, name, stock_qty
                """,
                (delta, found["id"], delta),
            )
            updated = await cur.fetchone()
            if not updated:
                await conn.rollback()
                return {
                    "error": (
                        f"Adjustment would make stock negative for {found['name']} "
                        f"(on hand {found['stock_qty']})."
                    )
                }
            await cur.execute(
                """
                INSERT INTO inventory_adjustments (product_id, delta, reason)
                VALUES (%s, %s, %s)
                RETURNING id, created_at
                """,
                (found["id"], delta, reason.strip()),
            )
            adj = await cur.fetchone()
        await conn.commit()
    return {"product": jsonable(updated), "adjustment": jsonable(adj), "reason": reason}


HANDLERS = {
    "inspect_schema": inspect_schema,
    "query_database": query_database,
    "create_customer": create_customer,
    "create_order": create_order,
    "update_order_status": update_order_status,
    "adjust_inventory": adjust_inventory,
}


async def dispatch(name: str, arguments: dict[str, Any]) -> str:
    handler = HANDLERS.get(name)
    if handler is None:
        output = dump({"error": f"Unknown tool {name!r}."})
        record("tool", name=name, arguments=arguments, output=output, error=True)
        return output
    try:
        result = await handler(**arguments)
        output = dump(result)
        record("tool", name=name, arguments=arguments, output=jsonable(result))
        return output
    except TypeError as exc:
        log.exception("Bad arguments for %s: %s", name, arguments)
        output = dump({"error": f"Bad arguments: {exc}"})
        record("tool", name=name, arguments=arguments, output=output, error=True)
        return output
    except Exception as exc:  # noqa: BLE001 — return to the model, keep the session alive
        log.exception("Tool %s failed", name)
        output = dump({"error": str(exc)})
        record("tool", name=name, arguments=arguments, output=output, error=True)
        return output
