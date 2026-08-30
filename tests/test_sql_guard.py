import pytest

from voice_postgres.sql_guard import sanitize_select


def test_allows_simple_select():
    assert sanitize_select("SELECT * FROM orders") == "SELECT * FROM orders"


def test_allows_with_cte():
    sql = "WITH x AS (SELECT 1 AS n) SELECT n FROM x"
    assert sanitize_select(sql) == sql


def test_strips_trailing_semicolon_and_comments():
    cleaned = sanitize_select("SELECT id FROM customers -- names\n;")
    assert cleaned == "SELECT id FROM customers"


def test_rejects_empty():
    with pytest.raises(ValueError):
        sanitize_select("   ")


def test_rejects_insert():
    with pytest.raises(ValueError):
        sanitize_select("INSERT INTO customers (name, email) VALUES ('a', 'b')")


def test_rejects_drop_hidden_in_select():
    with pytest.raises(ValueError):
        sanitize_select("SELECT 1; DROP TABLE customers")


def test_rejects_select_into():
    with pytest.raises(ValueError):
        sanitize_select("SELECT * INTO tmp FROM orders")


def test_rejects_for_update():
    with pytest.raises(ValueError):
        sanitize_select("SELECT * FROM orders FOR UPDATE")


def test_rejects_update():
    with pytest.raises(ValueError):
        sanitize_select("UPDATE products SET stock_qty = 0")


def test_rejects_multiple_statements():
    with pytest.raises(ValueError, match="single"):
        sanitize_select("SELECT 1; SELECT 2")
