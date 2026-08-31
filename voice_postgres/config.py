from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "sql" / "01_schema.sql").exists() and (parent / "static").is_dir():
            return parent
    return here.parents[1]


ROOT = _repo_root()
SQL_DIR = ROOT / "sql"
STATIC_DIR = ROOT / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xai_api_key: str = ""
    xai_realtime_url: str = "wss://api.x.ai/v1/realtime"
    xai_voice_model: str = "grok-voice-latest"
    xai_voice: str = "eve"

    database_url: str = "postgresql://voice:voice@127.0.0.1:55432/voice_postgres"

    host: str = "127.0.0.1"
    port: int = 8765
    # Public URL prefix when reverse-proxied, e.g. /assistant
    public_base: str = ""

    audio_sample_rate: int = 24000
    query_row_limit: int = 50
    query_timeout_ms: int = 4000


settings = Settings()


def public_base_path() -> str:
    raw = (settings.public_base or "").strip()
    if not raw or raw == "/":
        return "/"
    return "/" + raw.strip("/") + "/"
