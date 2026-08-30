from datetime import date, datetime
from decimal import Decimal

from voice_postgres.console import _cell, format_table, masked_url


def test_format_table_empty():
    assert format_table([]) == "(0 rows)"


def test_format_table_aligns_columns():
    text = format_table(
        [
            {"sku": "LAT-OAT", "qty": 2},
            {"sku": "X", "qty": 10},
        ]
    )
    assert "sku" in text.splitlines()[0]
    assert "LAT-OAT" in text
    assert "(2 rows)" in text


def test_cell_types():
    assert _cell(None) == ""
    assert _cell(Decimal("5.50")) == "5.50"
    assert _cell(True) == "t"
    assert _cell(date(2026, 8, 30)) == "2026-08-30"
    assert "2026-08-30" in _cell(datetime(2026, 8, 30, 7, 1, 2))


def test_masked_url_hides_password():
    url = masked_url("postgresql://voice:secret@127.0.0.1:55432/voice_postgres")
    assert "secret" not in url
    assert "voice@" in url
    assert "55432" in url
    assert url.endswith("/voice_postgres")
