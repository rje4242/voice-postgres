"""Bridge a browser WebSocket to xAI's Speech to Speech API and run DB tools."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect as xai_connect
from websockets.exceptions import ConnectionClosed

from voice_postgres.config import settings
from voice_postgres.history import new_session, parse_user_text, record
from voice_postgres.prompt import INSTRUCTIONS
from voice_postgres.tools import TOOL_SCHEMAS, dispatch
from voice_postgres.voices import clamp_speed, resolve_voice

log = logging.getLogger(__name__)

GREETING = (
    "Harbor and Bean, floor assistant on the line. Ask me about sales, stock, "
    "tickets, or who's on shift."
)


def session_update_event(
    sample_rate: int,
    voice: str | None = None,
    speed: float | None = None,
) -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "voice": resolve_voice(voice),
            "instructions": INSTRUCTIONS,
            "turn_detection": {
                "type": "server_vad",
                "silence_duration_ms": 600,
            },
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": sample_rate,
                    },
                    "transcription": {
                        "language_hint": "en",
                        "keyterms": [
                            "Harbor and Bean",
                            "oat latte",
                            "pour over",
                            "cold brew",
                            "croissant",
                            "loyalty points",
                            "SKU",
                        ],
                    },
                },
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": sample_rate,
                    },
                    "speed": clamp_speed(speed),
                },
            },
            "tools": TOOL_SCHEMAS,
        },
    }


def force_greeting() -> dict[str, Any]:
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "force_message",
            "role": "assistant",
            "interruptible": True,
            "content": [{"type": "output_text", "text": GREETING}],
        },
    }


class VoiceBridge:
    def __init__(self, client: WebSocket) -> None:
        self.client = client
        self._pending: dict[str, bool] = {}
        self._response_done = False
        self._xai = None
        self._session_id = new_session("voice")
        self._assistant_text = ""
        self._last_user = ""

    async def _send_client(self, payload: dict[str, Any]) -> None:
        await self.client.send_json(payload)

    async def _send_xai(self, payload: dict[str, Any]) -> None:
        assert self._xai is not None
        await self._xai.send(json.dumps(payload))

    async def _maybe_continue(self) -> None:
        if not self._pending:
            return
        if not self._response_done:
            return
        if not all(self._pending.values()):
            return
        self._pending = {}
        self._response_done = False
        await self._send_xai({"type": "response.create"})

    async def _handle_tool(self, event: dict[str, Any]) -> None:
        call_id = event.get("call_id") or ""
        name = event.get("name") or ""
        raw_args = event.get("arguments") or "{}"
        self._pending[call_id] = False
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            if not isinstance(arguments, dict):
                arguments = {}
        except json.JSONDecodeError:
            arguments = {}
            output = json.dumps({"error": "Tool arguments were not valid JSON."})
        else:
            log.info("Tool call %s %s %s", call_id, name, arguments)
            output = await dispatch(name, arguments)

        preview = output if len(output) < 4000 else output[:4000] + "…"
        await self._send_client(
            {
                "type": "local.tool_call",
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
                "output": json.loads(output) if output.startswith("{") or output.startswith("[") else output,
                "output_preview": preview,
            }
        )
        await self._send_xai(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            }
        )
        self._pending[call_id] = True
        await self._maybe_continue()

    def _log_user(self, text: str, via: str) -> None:
        text = (text or "").strip()
        if not text or text == self._last_user:
            return
        self._last_user = text
        record("voice.user", via=via, text=text)

    def _log_xai_transcripts(self, event: dict[str, Any]) -> None:
        etype = event.get("type") or ""
        parsed = parse_user_text(event)
        if parsed:
            self._log_user(*parsed)
        if etype in {
            "response.output_audio_transcript.delta",
            "response.audio_transcript.delta",
        }:
            self._assistant_text += event.get("delta") or ""
        elif etype in {
            "response.output_audio_transcript.done",
            "response.audio_transcript.done",
        }:
            text = (event.get("transcript") or self._assistant_text or "").strip()
            if text:
                record("voice.assistant", text=text)
            self._assistant_text = ""
        elif etype == "response.done" and self._assistant_text.strip():
            record("voice.assistant", text=self._assistant_text.strip())
            self._assistant_text = ""

    async def _on_xai_message(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            return
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Non-JSON from xAI: %s", raw[:200])
            return

        etype = event.get("type")
        self._log_xai_transcripts(event)
        if etype == "response.function_call_arguments.done":
            await self._handle_tool(event)
        elif etype == "response.created":
            self._response_done = False
            self._assistant_text = ""
        elif etype == "response.done":
            self._response_done = True
            await self._maybe_continue()

        await self._send_client(event)

    async def run(self) -> None:
        start = await self.client.receive_json()
        sample_rate = int(start.get("sample_rate") or settings.audio_sample_rate)
        if sample_rate not in {8000, 16000, 22050, 24000, 32000, 44100, 48000}:
            sample_rate = settings.audio_sample_rate
        voice = resolve_voice(start.get("voice"))
        speed = clamp_speed(start.get("speed"))

        if not settings.xai_api_key:
            await self._send_client(
                {
                    "type": "error",
                    "error": {
                        "message": "XAI_API_KEY is not set. Copy .env.example to .env and add a key from https://console.x.ai."
                    },
                }
            )
            return

        url = f"{settings.xai_realtime_url}?model={settings.xai_voice_model}"
        headers = {"Authorization": f"Bearer {settings.xai_api_key}"}
        log.info(
            "Connecting to %s (pcm %s Hz, voice=%s, speed=%s, session=%s)",
            url,
            sample_rate,
            voice,
            speed,
            self._session_id,
        )
        record(
            "session.start",
            model=settings.xai_voice_model,
            voice=voice,
            speed=speed,
            sample_rate=sample_rate,
        )

        async with xai_connect(url, additional_headers=headers, open_timeout=20) as xai_ws:
            self._xai = xai_ws
            await self._send_xai(session_update_event(sample_rate, voice, speed))
            await self._send_xai(force_greeting())
            await self._send_client(
                {
                    "type": "local.ready",
                    "voice": voice,
                    "speed": speed,
                    "model": settings.xai_voice_model,
                    "sample_rate": sample_rate,
                }
            )

            async def from_client() -> None:
                try:
                    while True:
                        text = await self.client.receive_text()
                        try:
                            event = json.loads(text)
                        except json.JSONDecodeError:
                            await xai_ws.send(text)
                            continue
                        if event.get("type") == "local.set_voice":
                            new_voice = resolve_voice(event.get("voice"))
                            record("voice", voice=new_voice)
                            await self._send_xai(
                                {"type": "session.update", "session": {"voice": new_voice}}
                            )
                            await self._send_client(
                                {
                                    "type": "local.voice",
                                    "voice": new_voice,
                                }
                            )
                            continue
                        if event.get("type") == "local.set_speed":
                            new_speed = clamp_speed(event.get("speed"))
                            record("speed", speed=new_speed)
                            await self._send_xai(
                                {
                                    "type": "session.update",
                                    "session": {"audio": {"output": {"speed": new_speed}}},
                                }
                            )
                            await self._send_client(
                                {
                                    "type": "local.speed",
                                    "speed": new_speed,
                                }
                            )
                            continue
                        parsed = parse_user_text(event)
                        if parsed:
                            self._log_user(*parsed)
                        await xai_ws.send(text)
                except WebSocketDisconnect:
                    return

            async def from_xai() -> None:
                try:
                    async for raw in xai_ws:
                        await self._on_xai_message(raw)
                except ConnectionClosed:
                    return

            try:
                client_task = asyncio.create_task(from_client(), name="client->xai")
                xai_task = asyncio.create_task(from_xai(), name="xai->client")
                done, pending = await asyncio.wait(
                    {client_task, xai_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    exc = task.exception()
                    if exc:
                        raise exc
            finally:
                record("session.end")
                self._xai = None
