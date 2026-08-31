"""Built-in xAI Speech to Speech / TTS voices, plus an optional live fetch."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from voice_postgres.config import settings

log = logging.getLogger(__name__)

# Original five, then the 2026 flagship roster. Same IDs work on Speech to Speech
# and TTS. Case-insensitive on the wire; we store lowercase.
BUILTIN: list[dict[str, str]] = [
    {"id": "ara", "name": "Ara", "group": "original", "description": "Warm and friendly"},
    {"id": "eve", "name": "Eve", "group": "original", "description": "Energetic and upbeat"},
    {"id": "leo", "name": "Leo", "group": "original", "description": "Authoritative and strong"},
    {"id": "rex", "name": "Rex", "group": "original", "description": "Confident and clear"},
    {"id": "sal", "name": "Sal", "group": "original", "description": "Smooth and balanced"},
    {"id": "altair", "name": "Altair", "group": "flagship", "description": "Bright and precise"},
    {"id": "atlas", "name": "Atlas", "group": "flagship", "description": "Grounded and steady"},
    {"id": "aurora", "name": "Aurora", "group": "flagship", "description": "Light and luminous"},
    {"id": "carina", "name": "Carina", "group": "flagship", "description": "Soft, empathetic, soothing"},
    {"id": "castor", "name": "Castor", "group": "flagship", "description": "Crisp and composed"},
    {"id": "celeste", "name": "Celeste", "group": "flagship", "description": "Airy and graceful"},
    {"id": "cosmo", "name": "Cosmo", "group": "flagship", "description": "Curious and playful"},
    {"id": "helios", "name": "Helios", "group": "flagship", "description": "Warm and radiant"},
    {"id": "helix", "name": "Helix", "group": "flagship", "description": "Bold and dynamic"},
    {"id": "iris", "name": "Iris", "group": "flagship", "description": "Clear and articulate"},
    {"id": "kepler", "name": "Kepler", "group": "flagship", "description": "Thoughtful and measured"},
    {"id": "liora", "name": "Liora", "group": "flagship", "description": "Gentle and bright"},
    {"id": "lumen", "name": "Lumen", "group": "flagship", "description": "Open and conversational"},
    {"id": "luna", "name": "Luna", "group": "flagship", "description": "Calm and nighttime-soft"},
    {"id": "lux", "name": "Lux", "group": "flagship", "description": "Polished and present"},
    {"id": "naksh", "name": "Naksh", "group": "flagship", "description": "Expressive and distinctive"},
    {"id": "orion", "name": "Orion", "group": "flagship", "description": "Rich, cinematic, resonant"},
    {"id": "perseus", "name": "Perseus", "group": "flagship", "description": "Heroic and direct"},
    {"id": "rigel", "name": "Rigel", "group": "flagship", "description": "Cool and assured"},
    {"id": "sirius", "name": "Sirius", "group": "flagship", "description": "Sharp and lively"},
    {"id": "ursa", "name": "Ursa", "group": "flagship", "description": "Deep and unhurried"},
    {"id": "zagan", "name": "Zagan", "group": "flagship", "description": "Powerful and dramatic"},
    {"id": "zenith", "name": "Zenith", "group": "flagship", "description": "High, clean, expansive"},
]

BUILTIN_BY_ID = {v["id"]: v for v in BUILTIN}
_CUSTOM_ID = re.compile(r"^[a-z0-9]{8}$")


SPEED_MIN = 0.7
SPEED_MAX = 1.5
SPEED_DEFAULT = 1.0


def clamp_speed(value: object, default: float = SPEED_DEFAULT) -> float:
    try:
        speed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(SPEED_MIN, min(SPEED_MAX, round(speed, 2)))


def resolve_voice(name: str | None) -> str:
    raw = (name or settings.xai_voice or "eve").strip().lower()
    if raw in BUILTIN_BY_ID or _CUSTOM_ID.fullmatch(raw):
        return raw
    return (settings.xai_voice or "eve").strip().lower()


def _from_xai() -> list[dict[str, str]] | None:
    if not settings.xai_api_key:
        return None
    req = urllib.request.Request(
        "https://api.x.ai/v1/tts/voices",
        headers={"Authorization": f"Bearer {settings.xai_api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        log.warning("Could not list xAI voices: %s", exc)
        return None
    out: list[dict[str, str]] = []
    for item in payload.get("voices") or []:
        vid = str(item.get("voice_id") or item.get("id") or "").strip().lower()
        if not vid:
            continue
        known = BUILTIN_BY_ID.get(vid)
        name = str(item.get("name") or (known["name"] if known else vid)).strip()
        desc = str(
            item.get("description")
            or (known["description"] if known else "Custom or additional voice")
        ).strip()
        group = known["group"] if known else "custom"
        out.append({"id": vid, "name": name, "group": group, "description": desc})
    return out or None


def list_voices() -> dict[str, Any]:
    live = _from_xai()
    voices = live if live is not None else list(BUILTIN)
    default = resolve_voice(settings.xai_voice)
    if default not in {v["id"] for v in voices}:
        voices.insert(0, BUILTIN_BY_ID.get(default, {"id": default, "name": default, "group": "custom", "description": ""}))
    return {"default": default, "source": "xai" if live is not None else "builtin", "voices": voices}
