#!/usr/bin/env bash
# Add /assistant/ to the existing agenticedge.us nginx site. Does not replace it.
# Run: sudo ./deploy/vps-sudo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNIPPET_SRC="$ROOT/deploy/nginx-assistant-path.conf"
SNIPPET_DST=/etc/nginx/snippets/voice-postgres.conf
SITE=/etc/nginx/sites-available/agenticedge.us

install -m 644 "$SNIPPET_SRC" "$SNIPPET_DST"

if [[ ! -f "$SITE" ]]; then
  echo "Expected $SITE (existing blog site). Aborting."
  exit 1
fi

if grep -q 'snippets/voice-postgres.conf' "$SITE"; then
  echo "Include already present in $SITE"
else
  python3 - <<'PY'
from pathlib import Path
p = Path("/etc/nginx/sites-available/agenticedge.us")
text = p.read_text()
needle = "    client_max_body_size 10M;\n"
insert = needle + "\n    include snippets/voice-postgres.conf;\n"
if "snippets/voice-postgres.conf" in text:
    raise SystemExit(0)
if needle not in text:
    raise SystemExit("Could not find insertion point (client_max_body_size) in nginx site")
p.write_text(text.replace(needle, insert, 1))
print("Inserted include snippets/voice-postgres.conf into", p)
PY
fi

nginx -t
systemctl reload nginx
loginctl enable-linger "${SUDO_USER:-rob}" || true
echo
echo "https://agenticedge.us/assistant/  should now proxy to 127.0.0.1:8765"
echo "Linger enabled so user systemd services survive logout."
