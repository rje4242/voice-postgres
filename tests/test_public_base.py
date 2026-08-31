from voice_postgres.config import Settings, public_base_path
from voice_postgres import config as config_mod


def test_public_base_path_default(monkeypatch):
    monkeypatch.setattr(config_mod, "settings", Settings(public_base=""))
    assert public_base_path() == "/"
    monkeypatch.setattr(config_mod, "settings", Settings(public_base="/assistant"))
    assert public_base_path() == "/assistant/"
    monkeypatch.setattr(config_mod, "settings", Settings(public_base="assistant/"))
    assert public_base_path() == "/assistant/"
