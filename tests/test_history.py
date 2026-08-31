import json

from voice_postgres import history
from voice_postgres.history import new_session, parse_user_text, record


def test_record_writes_daily_and_session_files(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_DIR", tmp_path)
    sid = new_session("voice")
    record("voice.user", via="text", text="what's low in stock?")
    record("sql", source="tool", sql="SELECT 1", row_count=1)
    record("tool", name="query_database", arguments={"sql": "SELECT 1"}, output={"row_count": 1})

    day_files = list(tmp_path.glob("????-??-??.jsonl"))
    assert len(day_files) == 1
    session_file = tmp_path / "sessions" / f"{sid}.jsonl"
    assert session_file.exists()
    events = [json.loads(line) for line in session_file.read_text().splitlines()]
    kinds = [e["kind"] for e in events]
    assert kinds == ["voice.user", "sql", "tool"]
    assert events[0]["session"] == sid
    assert events[1]["sql"] == "SELECT 1"


def test_parse_user_text_audio_and_typed():
    audio = parse_user_text(
        {
            "type": "conversation.item.created",
            "item": {
                "role": "user",
                "content": [{"type": "input_audio", "transcript": "who is on shift"}],
            },
        }
    )
    assert audio == ("who is on shift", "audio")
    typed = parse_user_text(
        {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "show open tickets"}],
            },
        }
    )
    assert typed == ("show open tickets", "text")
    assert parse_user_text({"type": "response.done"}) is None
