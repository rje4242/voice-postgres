# Deploy on a VPS with systemd

Easiest path: **Docker Postgres + systemd for FastAPI + Caddy for HTTPS**.

The microphone will **not** work on `http://your-vps:8765`. Browsers only allow `getUserMedia` on localhost or **HTTPS**. Put a TLS reverse proxy in front and keep FastAPI bound to `127.0.0.1`.

```
Internet  --HTTPS-->  Caddy :443  -->  127.0.0.1:8765  FastAPI (systemd)
                                          |
                                          +--> 127.0.0.1:55432  Postgres (Docker)
```

## 1. One-time on the VPS

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip docker.io docker-compose-v2 caddy
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# log out and back in so docker works without sudo
```

Point DNS `A`/`AAAA` at the VPS. Open **80** and **443**. Do **not** publish 8765 or 55432.

## 2. App checkout

```bash
sudo mkdir -p /opt/voice-postgres
sudo chown "$USER:$USER" /opt/voice-postgres
git clone git@github.com:rje4242/voice-postgres.git /opt/voice-postgres
cd /opt/voice-postgres
cp .env.example .env
```

Edit `.env`:

```bash
XAI_API_KEY=xai-...
HOST=127.0.0.1
PORT=8765
DATABASE_URL=postgresql://voice:voice@127.0.0.1:55432/voice_postgres
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
docker compose up -d
```

`docker compose` already uses `restart: unless-stopped` and binds Postgres only on loopback.

## 3. systemd

```bash
sudo ./deploy/install.sh
```

That writes `/etc/systemd/system/voice-postgres.service` with your user and this directory, then enables and starts it.

```bash
sudo systemctl status voice-postgres
journalctl -u voice-postgres -f
```

Useful later:

```bash
cd /opt/voice-postgres
git pull
source .venv/bin/activate && pip install -e .
sudo systemctl restart voice-postgres
```

## 4. HTTPS (Caddy)

Do **not** replace `/etc/caddy/Caddyfile` if other sites already live there. Add a site block.

**Option A — edit the existing file** (simplest if you only have a few sites):

```caddy
voice.example.com {
	reverse_proxy 127.0.0.1:8765
}
```

Then `sudo systemctl reload caddy`.

**Option B — import a snippet** so each app has its own file:

```bash
# once, if the main Caddyfile does not already import extras:
# add a line:  import /etc/caddy/sites/*
sudo mkdir -p /etc/caddy/sites
sudo cp /opt/voice-postgres/deploy/Caddyfile /etc/caddy/sites/voice-postgres.caddy
sudo nano /etc/caddy/sites/voice-postgres.caddy   # set the hostname
sudo systemctl reload caddy
```

Caddy proxies WebSockets for `/ws` with no extra config. Open `https://voice.example.com`.

## If you skip Caddy

You can still run the unit and `curl http://127.0.0.1:8765/api/health` on the box. Talking from a laptop over plain HTTP to a public IP will fail at `getUserMedia` the same way `http://0.0.0.0:8765` did locally.

## History logs

JSONL under `/opt/voice-postgres/history/` (same as local). Rotate or truncate if the disk is small:

```bash
find /opt/voice-postgres/history -name '*.jsonl' -mtime +30 -delete
```
