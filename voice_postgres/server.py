from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from voice_postgres.config import STATIC_DIR, settings
from voice_postgres.db import apply_schema, close_pool, health as db_health, init_pool, quote_ident
from voice_postgres.realtime import VoiceBridge
from voice_postgres.tools import inspect_schema, query_database
from voice_postgres.voices import list_voices

log = logging.getLogger("voice_postgres")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("Connecting to Postgres at %s", settings.database_url)
    await init_pool()
    await apply_schema()
    log.info("Schema ready. Voice model=%s voice=%s", settings.xai_voice_model, settings.xai_voice)
    if not settings.xai_api_key:
        log.warning("XAI_API_KEY is not set — the talk button will not connect to xAI.")
    yield
    await close_pool()


app = FastAPI(title="voice-postgres", lifespan=lifespan)


@app.get("/api/health")
async def health():
    db = await db_health()
    return {
        "ok": db.get("ok", False),
        "db": db,
        "voice": settings.xai_voice,
        "model": settings.xai_voice_model,
        "has_api_key": bool(settings.xai_api_key),
        "sample_rate": settings.audio_sample_rate,
    }


@app.get("/api/voices")
async def voices():
    return list_voices()


@app.get("/api/schema")
async def schema(table_name: str | None = None):
    return await inspect_schema(table_name)


@app.get("/api/preview/{table_name}")
async def preview(table_name: str):
    try:
        ident = quote_ident(table_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return await query_database(f"SELECT * FROM {ident}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws")
async def websocket_voice(ws: WebSocket):
    await ws.accept()
    bridge = VoiceBridge(ws)
    try:
        await bridge.run()
    except WebSocketDisconnect:
        log.info("Browser disconnected")
    except Exception:
        log.exception("Voice session failed")
        try:
            await ws.send_json(
                {
                    "type": "error",
                    "error": {"message": "Voice session failed. Check server logs and XAI_API_KEY."},
                }
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


@app.get("/")
async def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "voice_postgres.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
