"""Append-only JSONL logs under history/."""

from __future__ import annotations

import json
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from voice_postgres.config import ROOT

HISTORY_DIR = ROOT / "history"
_lock = threading.Lock()
session_id_var: ContextVar[str | None] = ContextVar("history_session_id", default=None)

_MAX = 8000


def new_session(kind: str = "voice") -> str:
    sid = f"{kind}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    session_id_var.set(sid)
    return sid


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX:
        return value[:_MAX] + "…"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > 40:
            return [_clip(v) for v in value[:40]] + [f"… {len(value) - 40} more"]
        return [_clip(v) for v in value]
    return value


def record(kind: str, **fields: Any) -> None:
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": session_id_var.get() or "none",
        "kind": kind,
        **{k: _clip(v) for k, v in fields.items()},
    }
    line = json.dumps(event, default=str, ensure_ascii=False) + "\n"
    day = event["ts"][:10]
    session = event["session"]
    with _lock:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        (HISTORY_DIR / "sessions").mkdir(exist_ok=True)
        (HISTORY_DIR / f"{day}.jsonl").open("a", encoding="utf-8").write(line)
        (HISTORY_DIR / "sessions" / f"{session}.jsonl").open("a", encoding="utf-8").write(line)


def parse_user_text(event: dict[str, Any]) -> tuple[str, str] | None:
    """Return (text, via) from an xAI or client conversation item event."""
    etype = event.get("type") or ""
    if etype.endswith("input_audio_transcription.completed") or etype.endswith(
        "input_audio_transcription.done"
    ):
        text = (event.get("transcript") or "").strip()
        return (text, "audio") if text else None

    item = event.get("item")
    if not isinstance(item, dict):
        return None
    role = item.get("role")
    content = item.get("content") or []
    if etype == "conversation.item.create" and item.get("type") == "message":
        role = role or "user"
    if role != "user" or not isinstance(content, list):
        return None
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("transcript"):
            return str(part["transcript"]).strip(), "audio"
        if part.get("type") in {"input_text", "text"} and part.get("text"):
            return str(part["text"]).strip(), "text"
    return None
