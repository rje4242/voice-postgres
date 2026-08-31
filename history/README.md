# history/

JSONL logs of Talk sessions and companion SQL.

Git ignores the log files; this folder is created automatically.

| Path | Contents |
|---|---|
| `YYYY-MM-DD.jsonl` | Every event that day (easy to `tail -f`) |
| `sessions/<id>.jsonl` | One Voice Agent or console session |

Each line is one JSON object with `ts`, `session`, `kind`, and kind-specific fields.

| `kind` | Meaning |
|---|---|
| `session.start` / `session.end` | Talk session opened or closed |
| `voice.user` | Spoken or typed user turn (`via` is `audio` or `text`) |
| `voice.assistant` | Agent spoken transcript |
| `sql` | SQL that ran (`source` is `tool` or `console`) |
| `tool` | Voice-agent function call (name, arguments, output) |
| `voice` / `speed` | Mid-session control changes |

```bash
tail -f history/$(date -u +%F).jsonl
python -c "import json,pathlib; print(*[json.loads(l)['kind'] for l in pathlib.Path('history').glob('*.jsonl') for l in open(l)], sep='\n')"
```
