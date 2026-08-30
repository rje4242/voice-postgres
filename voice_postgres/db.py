from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from voice_postgres.config import SQL_DIR, settings

log = logging.getLogger(__name__)

pool: AsyncConnectionPool | None = None

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def quote_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


async def init_pool() -> AsyncConnectionPool:
    global pool
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=8,
        kwargs={"row_factory": dict_row, "autocommit": False},
        open=False,
    )
    await pool.open()
    return pool


async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def require_pool() -> AsyncConnectionPool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized.")
    return pool


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    async with require_pool().connection() as conn:
        yield conn


async def fetch_all(sql: str, params: Any = None) -> list[dict[str, Any]]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
        await conn.commit()
        return list(rows)


async def fetch_one(sql: str, params: Any = None) -> dict[str, Any] | None:
    rows = await fetch_all(sql, params)
    return rows[0] if rows else None


async def execute(sql: str, params: Any = None) -> None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
        await conn.commit()


def _sql_files() -> list[Path]:
    return sorted(SQL_DIR.glob("*.sql"))


async def apply_schema() -> None:
    files = _sql_files()
    if not files:
        raise FileNotFoundError(f"No SQL files in {SQL_DIR}")
    async with connection() as conn:
        async with conn.cursor() as cur:
            for path in files:
                log.info("Applying %s", path.name)
                await cur.execute(path.read_text(encoding="utf-8"))
        await conn.commit()


async def health() -> dict[str, Any]:
    try:
        row = await fetch_one("SELECT current_database() AS db, NOW() AS now")
        counts = await fetch_all(
            """
            SELECT relname AS name, n_live_tup::int AS approx_rows
            FROM pg_stat_user_tables
            ORDER BY relname
            """
        )
        return {"ok": True, "database": row["db"] if row else None, "tables": counts}
    except Exception as exc:  # noqa: BLE001 — surface health errors to the UI
        return {"ok": False, "error": str(exc)}
