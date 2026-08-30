# voice-postgres

Talk to a **local PostgreSQL** database using [xAI’s Speech to Speech / Voice Agent API](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech).

You speak in the browser. Grok Voice calls tools. Those tools run SQL (and a few structured writes) against a cafe-operations database this project starts for you.

```
Browser  ──WebSocket──►  FastAPI
                         ├─ proxies audio to  wss://api.x.ai/v1/realtime
                         ├─ intercepts function calls
                         └─ Postgres  (Docker, port 55432)
```

The API key never leaves the server. Custom tools are executed next to the database, not in the browser.

## What you get

- Docker Compose Postgres **initialized by this repo** (`sql/01_schema.sql` + `sql/02_seed.sql`)
- A Voice Agent session on `grok-voice-latest` with server VAD
- Read-only `query_database` (SELECT / WITH only, timeout + row cap)
- Write tools for tickets, customers, and inventory
- A small web UI: schema browser, live transcript, tool-call inspector

The seed shop is **Harbor & Bean**, a neighborhood cafe: customers, products, tickets, staff, and shifts.

## Prerequisites

- Docker
- Python 3.11+
- An xAI API key from [console.x.ai](https://console.x.ai)
- A Chromium-based browser (microphone + Web Audio)

## Quick start

```bash
git clone git@github.com:rje4242/voice-postgres.git
cd voice-postgres
cp .env.example .env
# put your key in .env:
# XAI_API_KEY=xai-...

chmod +x start.sh
./start.sh
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), click **Talk**, allow the microphone.

`start.sh` brings up Postgres on **localhost:55432** (so it does not collide with a local server on 5432), waits until it is ready, installs the Python package, and serves the app.

Manual equivalent:

```bash
docker compose up -d
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m voice_postgres
```

## Things to ask

- What’s low in stock?
- Who’s on the bar today?
- What’s revenue for the last seven days?
- Which tickets are still open?
- Who is the top customer by spend?
- Create an order for Maya: two oat lattes and a croissant.
- Mark the pending cold brew as ready.
- We wasted three almond croissants — take them off the shelf.

Writes always ask for confirmation first (that rule is in the voice prompt).

## Database

| Relation | Kind | Point of it |
|---|---|---|
| `customers` | table | Loyalty guests |
| `employees` | table | Baristas, baker, leads, manager |
| `products` | table | Menu + merch, with `stock_qty` |
| `orders` / `order_items` | tables | Tickets and line items |
| `shifts` | table | Who is scheduled, including today |
| `inventory_adjustments` | table | Stock audit log |
| `v_order_totals` | view | Per-order totals |
| `v_low_stock` | view | At or below reorder point |
| `v_daily_sales` | view | Orders and revenue by day |

Connect with any client:

```text
postgresql://voice:voice@127.0.0.1:55432/voice_postgres
```

Schema is applied on first `docker compose up` **and** again (idempotently) when the app starts.

## Voice tools

Defined in `voice_postgres/tools.py` and attached on `session.update`:

| Tool | What it does |
|---|---|
| `inspect_schema` | Tables, views, columns, comments |
| `query_database` | One SELECT/WITH; no writes; `statement_timeout`; max 50 rows |
| `create_customer` | Insert a loyalty row |
| `create_order` | Customer email + line items by SKU or name; decrements stock |
| `update_order_status` | `pending` → `preparing` → `ready` → `completed` / `cancelled` |
| `adjust_inventory` | Signed stock change + audit row |

`query_database` is guarded in `sql_guard.py`: comments stripped, single statement, SELECT/WITH only, no `INTO`, no `FOR UPDATE`, no mutating keywords.

## Configuration

See `.env.example`.

| Variable | Default |
|---|---|
| `XAI_API_KEY` | *(required to talk)* |
| `XAI_REALTIME_URL` | `wss://api.x.ai/v1/realtime` |
| `XAI_VOICE_MODEL` | `grok-voice-latest` |
| `XAI_VOICE` | `eve` |
| `DATABASE_URL` | `postgresql://voice:voice@127.0.0.1:55432/voice_postgres` |
| `PORT` | `8765` |

Voices and session options: [Speech to Speech guide](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech).

## How the session works

1. The browser opens `ws://…/ws` and sends `{ type: "local.start", sample_rate }`.
2. The server connects to `wss://api.x.ai/v1/realtime?model=grok-voice-latest` with `Authorization: Bearer $XAI_API_KEY`.
3. It sends `session.update` (voice, instructions, PCM, server VAD, tools) and a `force_message` greeting.
4. Mic PCM16 is forwarded as `input_audio_buffer.append`. Assistant audio (`response.output_audio.delta`) is played immediately.
5. On `response.function_call_arguments.done`, the server runs the tool against Postgres, returns `function_call_output`, waits until **all** parallel calls for that turn are done, then sends `response.create`.

This follows xAI’s custom-function flow, including parallel tool calls.

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

Unit tests cover the SQL guard and identifier quoting. They do not need Postgres or an API key.

## License

MIT
