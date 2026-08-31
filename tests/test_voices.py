from voice_postgres.voices import BUILTIN, clamp_speed, resolve_voice


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


def test_clamp_speed():
    assert clamp_speed(1) == 1.0
    assert clamp_speed("1.25") == 1.25
    assert clamp_speed(0.1) == 0.7
    assert clamp_speed(3) == 1.5
    assert clamp_speed("nope") == 1.0
