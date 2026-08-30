#!/usr/bin/env zsh
# Configure a zsh so the companion SQL console can run.
#
# From a new terminal:
#
#   cd /home/rob/github/voice-postgres
#   source ./env.sh
#   python scripts/db_console.py
#
# If you execute it instead of sourcing (`./env.sh`), it does the same setup
# then replaces itself with an interactive zsh that already has the env.

_vp_sourced=0
if [[ -n "${ZSH_EVAL_CONTEXT:-}" && "$ZSH_EVAL_CONTEXT" == *:file* ]]; then
  _vp_sourced=1
elif [[ -n "${BASH_VERSION:-}" && "${BASH_SOURCE[0]:-}" != "$0" ]]; then
  _vp_sourced=1
fi

if [[ -n "${ZSH_VERSION:-}" ]]; then
  _vp_this="${${(%):-%N}:A}"
elif [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  _vp_this="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
else
  _vp_this="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
fi
VOICE_POSTGRES_ROOT="$(cd "$(dirname "$_vp_this")" && pwd)"
cd "$VOICE_POSTGRES_ROOT" || {
  print -u2 -- "Could not cd to $VOICE_POSTGRES_ROOT"
  if (( _vp_sourced )); then return 1; else exit 1; fi
}

_vp_fail() {
  print -u2 -- "$*"
  return 1
}

if ! command -v docker >/dev/null 2>&1; then
  _vp_fail "Docker is not on PATH. Install Docker, then source ./env.sh again."
  if (( _vp_sourced )); then return 1; else exit 1; fi
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  print -- "Created .env from .env.example — add XAI_API_KEY if you want the voice UI."
fi

# Export KEY=value pairs from .env (skip comments / blanks).
set -a
# shellcheck disable=SC1091
source "$VOICE_POSTGRES_ROOT/.env"
set +a

: "${DATABASE_URL:=postgresql://voice:voice@127.0.0.1:55432/voice_postgres}"
export DATABASE_URL
export VOICE_POSTGRES_ROOT

print -- "Starting Postgres (localhost:55432)…"
if ! docker compose up -d; then
  _vp_fail "docker compose up failed. Is Docker running?"
  if (( _vp_sourced )); then return 1; else exit 1; fi
fi

_vp_ready=0
for _ in {1..50}; do
  if docker compose exec -T postgres pg_isready -U voice -d voice_postgres >/dev/null 2>&1; then
    _vp_ready=1
    break
  fi
  sleep 0.3
done
if (( ! _vp_ready )); then
  _vp_fail "Postgres did not become ready on port 55432."
  if (( _vp_sourced )); then return 1; else exit 1; fi
fi

if [[ ! -d .venv ]]; then
  print -- "Creating .venv…"
  python3 -m venv .venv || {
    _vp_fail "python3 -m venv failed."
    if (( _vp_sourced )); then return 1; else exit 1; fi
  }
fi

export VIRTUAL_ENV="$VOICE_POSTGRES_ROOT/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
unset PYTHONHOME
hash -r 2>/dev/null || true

if ! python -c "import voice_postgres.console" >/dev/null 2>&1; then
  print -- "Installing voice-postgres into .venv…"
  pip install -e ".[dev]" || {
    _vp_fail "pip install failed."
    if (( _vp_sourced )); then return 1; else exit 1; fi
  }
fi

# Handy names in a sourced shell (aliases do not survive `exec zsh`).
if (( _vp_sourced )); then
  alias db-console='python "$VOICE_POSTGRES_ROOT/scripts/db_console.py"'
  alias voice-pg-db='python "$VOICE_POSTGRES_ROOT/scripts/db_console.py"'
fi

print -- "voice-postgres env ready"
print -- "  root   $VOICE_POSTGRES_ROOT"
print -- "  db     $DATABASE_URL"
print -- "  python $(command -v python)"
print -- ""
print -- "Companion console:"
print -- "  python scripts/db_console.py"
print -- "  python scripts/db_console.py --tables"
print -- "  voice-pg"

if (( ! _vp_sourced )); then
  if [[ -n "${VOICE_POSTGRES_NESTED:-}" ]]; then
    return 0 2>/dev/null || exit 0
  fi
  print -- ""
  print -- "Not sourced — opening an interactive zsh with this env."
  print -- "(Next time:  source ./env.sh)"
  export VOICE_POSTGRES_NESTED=1
  exec zsh -i -c "source '$VOICE_POSTGRES_ROOT/env.sh'; unset VOICE_POSTGRES_NESTED; exec zsh -i"
fi
