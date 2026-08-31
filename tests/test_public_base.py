from voice_postgres.config import Settings, canonical_url, og_image_url, public_base_path
from voice_postgres import config as config_mod


def test_public_base_path_default(monkeypatch):
    monkeypatch.setattr(config_mod, "settings", Settings(public_base=""))
    assert public_base_path() == "/"
    monkeypatch.setattr(config_mod, "settings", Settings(public_base="/assistant"))
    assert public_base_path() == "/assistant/"
    monkeypatch.setattr(config_mod, "settings", Settings(public_base="assistant/"))
    assert public_base_path() == "/assistant/"


def test_canonical_and_og_urls(monkeypatch):
    monkeypatch.setattr(
        config_mod,
        "settings",
        Settings(public_url="https://agenticedge.us/assistant", public_base="/assistant", port=8765),
    )
    assert canonical_url() == "https://agenticedge.us/assistant/"
    assert og_image_url() == "https://agenticedge.us/assistant/static/og.png"

    monkeypatch.setattr(config_mod, "settings", Settings(public_url="", public_base="", port=8765))
    assert canonical_url() == "http://127.0.0.1:8765/"
    assert og_image_url() == "http://127.0.0.1:8765/static/og.png"
