#!/usr/bin/env bash
# One-time root steps on agenticedge. Run: sudo ./deploy/vps-sudo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE=assistant.agenticedge.us
AVAIL=/etc/nginx/sites-available/$SITE
ENABLED=/etc/nginx/sites-enabled/$SITE

install -m 644 "$ROOT/deploy/nginx-assistant.agenticedge.us.conf" "$AVAIL"
ln -sfn "$AVAIL" "$ENABLED"

nginx -t
systemctl reload nginx

if command -v certbot >/dev/null; then
  certbot --nginx -d "$SITE" --non-interactive --agree-tos --redirect \
    --keep-until-expiring || certbot --nginx -d agenticedge.us -d www.agenticedge.us -d "$SITE" --expand --non-interactive --agree-tos
fi

nginx -t
systemctl reload nginx

# Docker socket so the same user can `docker compose up -d` next time
if getent group docker >/dev/null; then
  usermod -aG docker "${SUDO_USER:-rob}"
fi

loginctl enable-linger "${SUDO_USER:-rob}" || true

echo "Nginx site $SITE enabled. Open https://$SITE"
echo "If you were added to docker, log out and back in."
