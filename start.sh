#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your XAI_API_KEY before talking."
fi

echo "Starting Postgres on localhost:55432…"
docker compose up -d

echo "Waiting for Postgres…"
for _ in $(seq 1 40); do
  if docker compose exec -T postgres pg_isready -U voice -d voice_postgres >/dev/null 2>&1; then
    break
  fi
  sleep 0.4
done
docker compose exec -T postgres pg_isready -U voice -d voice_postgres

if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev
  echo "Open http://127.0.0.1:8765"
  exec uv run voice-postgres
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -e ".[dev]"
echo "Open http://127.0.0.1:8765"
exec python -m voice_postgres
