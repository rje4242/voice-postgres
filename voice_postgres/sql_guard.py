"""Reject anything that is not a single read-only SELECT / WITH statement."""

from __future__ import annotations

import re

_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_LEADING = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|MERGE|UPSERT|"
    r"DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"COPY|CALL|DO|EXECUTE|PERFORM|"
    r"VACUUM|ANALYZE|CLUSTER|REINDEX|"
    r"LISTEN|NOTIFY|LOAD|RESET|"
    r"SECURITY\s+LABEL|LOCK|SET\s+ROLE|"
    r"pg_sleep|lo_import|lo_export|"
    r"dblink|file_fdw|postgres_fdw"
    r")\b",
    re.IGNORECASE,
)
_INTO = re.compile(r"\bINTO\s+(TEMP|TEMPORARY|TABLE|STDOUT|[a-z_])", re.IGNORECASE)
_FOR_UPDATE = re.compile(r"\bFOR\s+(UPDATE|NO\s+KEY\s+UPDATE|SHARE|KEY\s+SHARE)\b", re.IGNORECASE)


def sanitize_select(sql: str) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL is empty.")

    cleaned = _COMMENT_BLOCK.sub(" ", sql)
    cleaned = _COMMENT_LINE.sub(" ", cleaned)
    cleaned = cleaned.strip().rstrip(";").strip()

    if not cleaned:
        raise ValueError("SQL is empty after removing comments.")
    if ";" in cleaned:
        raise ValueError("Only a single SQL statement is allowed.")
    if not _LEADING.match(cleaned):
        raise ValueError("Only SELECT or WITH (CTE) queries are allowed.")
    if _FORBIDDEN.search(cleaned):
        raise ValueError("Query contains a forbidden keyword.")
    if _INTO.search(cleaned):
        raise ValueError("SELECT INTO is not allowed.")
    if _FOR_UPDATE.search(cleaned):
        raise ValueError("FOR UPDATE / FOR SHARE is not allowed.")
    return cleaned
