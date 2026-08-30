"""Interactive SQL console against the project's local Postgres.

Same DATABASE_URL as the voice app. Run:

    python scripts/db_console.py
    python -m voice_postgres.console
    voice-pg
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from psycopg import Connection, ProgrammingError
from psycopg.rows import dict_row

from voice_postgres.config import settings
from voice_postgres.db import quote_ident

HISTORY_PATH = Path.home() / ".voice_postgres_history"
PREVIEW_LIMIT = 20

HELP = """\
SQL
  Type statements ending with ;  (multi-line is fine)

Meta
  \\tables / \\dt          list tables
  \\views / \\dv           list views
  \\d NAME                columns + comment for a table or view
  \\preview NAME          SELECT * LIMIT 20
  \\counts                live row counts
  \\low                   v_low_stock
  \\open                  tickets not completed/cancelled
  \\shift                 who is on today
  \\sales                 v_daily_sales
  \\i FILE.sql            run a file
  \\url                   print the connection target (password hidden)
  \\help / \\h / ?         this help
  \\q / exit / quit       leave

One-shot
  python scripts/db_console.py -c "SELECT * FROM v_low_stock"
  python scripts/db_console.py --preview products
"""

SHORTCUTS: dict[str, str] = {
    "low": "SELECT * FROM v_low_stock",
    "open": """
        SELECT o.id, c.name, o.status, o.notes, o.placed_at, t.total
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        JOIN v_order_totals t ON t.order_id = o.id
        WHERE o.status NOT IN ('completed', 'cancelled')
        ORDER BY o.placed_at
    """,
    "shift": """
        SELECT s.shift_date, s.start_time, s.end_time, s.station, e.name, e.role
        FROM shifts s
        JOIN employees e ON e.id = s.employee_id
        WHERE s.shift_date = CURRENT_DATE
        ORDER BY s.start_time, e.name
    """,
    "sales": "SELECT * FROM v_daily_sales LIMIT 14",
}


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat(sep=" ", timespec="seconds")
        except TypeError:
            return value.isoformat()
    if isinstance(value, bool):
        return "t" if value else "f"
    return str(value)


def format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(0 rows)"
    cols = list(rows[0].keys())
    cells = [{k: _cell(row.get(k)) for k in cols} for row in rows]
    widths = {k: max(len(str(k)), max(len(c[k]) for c in cells)) for k in cols}
    header = " | ".join(str(k).ljust(widths[k]) for k in cols)
    rule = "-+-".join("-" * widths[k] for k in cols)
    body = [" | ".join(c[k].ljust(widths[k]) for k in cols) for c in cells]
    return "\n".join([header, rule, *body, f"({len(rows)} row{'s' if len(rows) != 1 else ''})"])


def masked_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    user = f"{parsed.username}@" if parsed.username else ""
    return f"{parsed.scheme}://{user}{host}{port}{parsed.path}"


def connect() -> Connection:
    return Connection.connect(settings.database_url, row_factory=dict_row, autocommit=True)


def run_sql(conn: Connection, sql: str) -> str:
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        return ""
    with conn.cursor() as cur:
        cur.execute(sql)
        if cur.description is None:
            status = cur.statusmessage or "OK"
            if cur.rowcount is not None and cur.rowcount >= 0:
                return f"{status}  ({cur.rowcount} row{'s' if cur.rowcount != 1 else ''} affected)"
            return status
        rows = list(cur.fetchall())
        return format_table(rows)


def list_relations(conn: Connection, kinds: tuple[str, ...] = ("r", "v")) -> str:
    kind_sql = ",".join(f"'{k}'" for k in kinds)
    return run_sql(
        conn,
        f"""
        SELECT
            c.relname AS name,
            CASE c.relkind
                WHEN 'r' THEN 'table'
                WHEN 'v' THEN 'view'
                ELSE c.relkind::text
            END AS kind,
            obj_description(c.oid) AS comment
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ({kind_sql})
        ORDER BY c.relkind, c.relname
        """,
    )


def describe_relation(conn: Connection, name: str) -> str:
    ident = quote_ident(name)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.attname AS column,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS type,
                NOT a.attnotnull AS nullable,
                col_description(c.oid, a.attnum) AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE n.nspname = 'public' AND c.relname = %s
            ORDER BY a.attnum
            """,
            (name,),
        )
        rows = list(cur.fetchall())
    if not rows:
        raise ValueError(f"No table or view named {name!r}.")
    counts = run_sql(conn, f"SELECT COUNT(*) AS rows FROM {ident}")
    return f"{format_table(rows)}\n\n{counts}"


def preview(conn: Connection, name: str) -> str:
    ident = quote_ident(name)
    return run_sql(conn, f"SELECT * FROM {ident} LIMIT {PREVIEW_LIMIT}")


def row_counts(conn: Connection) -> str:
    return run_sql(
        conn,
        """
        SELECT relname AS name, n_live_tup::int AS approx_rows
        FROM pg_stat_user_tables
        ORDER BY relname
        """,
    )


def handle_meta(conn: Connection, line: str) -> str | None:
    raw = line.strip()
    if raw in {"q", "quit", "exit"}:
        return None
    if raw in {"h", "help", "?"}:
        return HELP
    if raw in {"tables", "dt"}:
        return list_relations(conn, ("r",))
    if raw in {"views", "dv"}:
        return list_relations(conn, ("v",))
    if raw == "counts":
        return row_counts(conn)
    if raw == "url":
        return masked_url(settings.database_url)
    if raw in SHORTCUTS:
        return run_sql(conn, SHORTCUTS[raw])
    if raw == "d":
        return list_relations(conn)
    if raw.startswith("d "):
        return describe_relation(conn, raw[2:].strip())
    if raw.startswith("preview "):
        return preview(conn, raw.split(None, 1)[1].strip())
    if raw.startswith("i "):
        path = Path(raw.split(None, 1)[1].strip()).expanduser()
        sql = path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is not None:
                return format_table(list(cur.fetchall()))
            return cur.statusmessage or f"ran {path}"
    raise ValueError(f"Unknown command \\{raw}. Try \\help.")


def _load_history() -> None:
    try:
        import readline
    except ImportError:
        return
    readline.parse_and_bind("tab: complete")
    if HISTORY_PATH.exists():
        readline.read_history_file(HISTORY_PATH)


def _save_history() -> None:
    try:
        import readline
    except ImportError:
        return
    try:
        readline.write_history_file(HISTORY_PATH)
    except OSError:
        pass


def repl(conn: Connection) -> int:
    _load_history()
    print(f"voice-postgres  {masked_url(settings.database_url)}")
    print("SQL ends with ;    \\help for commands    \\q to quit")
    buf: list[str] = []
    try:
        while True:
            try:
                prompt = "voice=> " if not buf else "voice-> "
                line = input(prompt)
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                buf = []
                continue

            stripped = line.strip()
            if not buf and stripped.startswith("\\"):
                try:
                    result = handle_meta(conn, stripped[1:])
                except (ValueError, ProgrammingError, OSError) as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    continue
                if result is None:
                    break
                if result:
                    print(result)
                continue
            if not buf and stripped.lower() in {"quit", "exit"}:
                break

            buf.append(line)
            joined = "\n".join(buf)
            if ";" not in joined:
                continue
            sql = joined
            buf = []
            try:
                print(run_sql(conn, sql))
            except Exception as exc:  # noqa: BLE001 — show the server error, keep the REPL
                print(f"ERROR: {exc}", file=sys.stderr)
    finally:
        _save_history()
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Talk to the voice-postgres Harbor & Bean database with SQL.",
    )
    parser.add_argument("-c", "--command", help="Run one SQL statement and exit")
    parser.add_argument("--preview", metavar="NAME", help="Preview a table or view and exit")
    parser.add_argument("--tables", action="store_true", help="List tables and exit")
    parser.add_argument("--counts", action="store_true", help="Print row counts and exit")
    parser.add_argument(
        "shortcut",
        nargs="?",
        choices=sorted(SHORTCUTS),
        help="Run a named shortcut (low, open, shift, sales) and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        conn = connect()
    except Exception as exc:  # noqa: BLE001
        print(
            f"Could not connect to {masked_url(settings.database_url)}\n{exc}\n"
            "Start Postgres with: docker compose up -d",
            file=sys.stderr,
        )
        return 1

    with conn:
        try:
            if args.command:
                print(run_sql(conn, args.command))
                return 0
            if args.preview:
                print(preview(conn, args.preview))
                return 0
            if args.tables:
                print(list_relations(conn, ("r",)))
                return 0
            if args.counts:
                print(row_counts(conn))
                return 0
            if args.shortcut:
                print(run_sql(conn, SHORTCUTS[args.shortcut]))
                return 0
            return repl(conn)
        except (ValueError, ProgrammingError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
