from voice_postgres.voices import BUILTIN, resolve_voice


def test_builtin_ids_are_unique_and_lowercase():
    ids = [v["id"] for v in BUILTIN]
    assert ids == [i.lower() for i in ids]
    assert len(ids) == len(set(ids))
    assert {"ara", "eve", "leo", "rex", "sal"} <= set(ids)


def test_resolve_voice_normalizes_and_falls_back():
    assert resolve_voice("Eve") == "eve"
    assert resolve_voice("ARA") == "ara"
    assert resolve_voice("nlbqfwie") == "nlbqfwie"
    assert resolve_voice("not-a-voice") in {v["id"] for v in BUILTIN} | {"eve"}
