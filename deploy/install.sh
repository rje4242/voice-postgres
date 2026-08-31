#!/usr/bin/env bash
# Install or refresh the systemd unit on this machine.
# Run from the repo as the user who should own the service, with sudo for the copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="${SUDO_USER:-$USER}"
APP_DIR="${APP_DIR:-$ROOT}"
UNIT_SRC="$ROOT/deploy/voice-postgres.service"
UNIT_DST=/etc/systemd/system/voice-postgres.service

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-run with sudo:  sudo APP_DIR=$APP_DIR $0"
  exit 1
fi

tmp="$(mktemp)"
sed \
  -e "s|DEPLOY_USER|$APP_USER|g" \
  -e "s|/opt/voice-postgres|$APP_DIR|g" \
  "$UNIT_SRC" >"$tmp"
install -m 644 "$tmp" "$UNIT_DST"
rm -f "$tmp"

systemctl daemon-reload
systemctl enable voice-postgres.service
systemctl restart voice-postgres.service
systemctl --no-pager --full status voice-postgres.service
echo
echo "Enabled voice-postgres as $APP_USER from $APP_DIR"
echo "Logs: journalctl -u voice-postgres -f"
