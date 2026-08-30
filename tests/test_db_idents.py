import pytest

from voice_postgres.db import quote_ident


def test_quote_ident():
    assert quote_ident("orders") == '"orders"'
    assert quote_ident("v_daily_sales") == '"v_daily_sales"'


@pytest.mark.parametrize("bad", ["Orders", "orders;drop", "pg_catalog.orders", "a-b", ""])
def test_rejects_bad_idents(bad):
    with pytest.raises(ValueError):
        quote_ident(bad)
