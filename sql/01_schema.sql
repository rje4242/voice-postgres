-- Harbor & Bean — neighborhood cafe operations schema.
-- Applied automatically on first `docker compose up` and again (idempotently)
-- by the app on startup.

CREATE TABLE IF NOT EXISTS customers (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    phone       TEXT,
    loyalty_points INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employees (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('barista', 'baker', 'shift_lead', 'manager')),
    hourly_rate NUMERIC(6, 2) NOT NULL,
    hired_on    DATE NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    sku         TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL CHECK (category IN ('coffee', 'tea', 'pastry', 'food', 'merchandise')),
    unit_price  NUMERIC(8, 2) NOT NULL CHECK (unit_price >= 0),
    stock_qty   INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    reorder_at  INTEGER NOT NULL DEFAULT 5,
    active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS orders (
    id            SERIAL PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(id),
    employee_id   INTEGER REFERENCES employees(id),
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'preparing', 'ready', 'completed', 'cancelled')),
    notes         TEXT,
    placed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(8, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE IF NOT EXISTS shifts (
    id           SERIAL PRIMARY KEY,
    employee_id  INTEGER NOT NULL REFERENCES employees(id),
    shift_date   DATE NOT NULL,
    start_time   TIME NOT NULL,
    end_time     TIME NOT NULL,
    station      TEXT NOT NULL DEFAULT 'bar'
);

CREATE TABLE IF NOT EXISTS inventory_adjustments (
    id          SERIAL PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    delta       INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_placed_at ON orders(placed_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(shift_date);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

CREATE OR REPLACE VIEW v_order_totals AS
SELECT
    o.id AS order_id,
    o.customer_id,
    o.status,
    o.placed_at,
    COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total,
    COALESCE(SUM(oi.quantity), 0) AS item_count
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, o.customer_id, o.status, o.placed_at;

CREATE OR REPLACE VIEW v_low_stock AS
SELECT id, sku, name, category, stock_qty, reorder_at
FROM products
WHERE active AND stock_qty <= reorder_at
ORDER BY stock_qty ASC, name;

CREATE OR REPLACE VIEW v_daily_sales AS
SELECT
    (placed_at AT TIME ZONE 'UTC')::date AS sale_date,
    COUNT(*) FILTER (WHERE status <> 'cancelled') AS orders,
    COALESCE(SUM(total) FILTER (WHERE status <> 'cancelled'), 0) AS revenue
FROM v_order_totals
GROUP BY 1
ORDER BY 1 DESC;

COMMENT ON TABLE customers IS 'Cafe guests with loyalty accounts.';
COMMENT ON TABLE employees IS 'Staff: baristas, bakers, shift leads, managers.';
COMMENT ON TABLE products IS 'Menu items and merchandise. stock_qty is on-hand inventory.';
COMMENT ON TABLE orders IS 'Customer tickets. status: pending, preparing, ready, completed, cancelled.';
COMMENT ON TABLE order_items IS 'Line items on an order. unit_price is captured at purchase time.';
COMMENT ON TABLE shifts IS 'Who is scheduled on which day and station.';
COMMENT ON TABLE inventory_adjustments IS 'Audit log of stock changes (receiving, waste, voice-agent edits).';
COMMENT ON VIEW v_order_totals IS 'One row per order with computed total and item count.';
COMMENT ON VIEW v_low_stock IS 'Active products at or below reorder_at.';
COMMENT ON VIEW v_daily_sales IS 'Orders and revenue by UTC calendar day, excluding cancelled.';
