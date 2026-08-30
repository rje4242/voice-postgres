-- Demo data for Harbor & Bean. Safe to re-run: unique keys skip duplicates.

INSERT INTO customers (name, email, phone, loyalty_points, created_at) VALUES
    ('Maya Alvarez',  'maya@example.com',   '415-555-0101', 240, NOW() - INTERVAL '14 months'),
    ('Jonah Park',    'jonah@example.com',  '415-555-0102',  80, NOW() - INTERVAL '11 months'),
    ('Priya Shah',    'priya@example.com',  '415-555-0103', 410, NOW() - INTERVAL '9 months'),
    ('Eli Nguyen',    'eli@example.com',    '415-555-0104',  25, NOW() - INTERVAL '7 months'),
    ('Sofia Rossi',   'sofia@example.com',  '415-555-0105', 175, NOW() - INTERVAL '6 months'),
    ('Avery Cole',    'avery@example.com',  '415-555-0106',  60, NOW() - INTERVAL '5 months'),
    ('Kenji Watanabe','kenji@example.com',  '415-555-0107', 320, NOW() - INTERVAL '4 months'),
    ('Lila Brooks',   'lila@example.com',   '415-555-0108',  15, NOW() - INTERVAL '3 months'),
    ('Omar Haddad',   'omar@example.com',   '415-555-0109',  90, NOW() - INTERVAL '2 months'),
    ('Nina Volkov',   'nina@example.com',   '415-555-0110', 205, NOW() - INTERVAL '6 weeks'),
    ('Theo Marin',    'theo@example.com',   '415-555-0111',  40, NOW() - INTERVAL '3 weeks'),
    ('Harper Quinn',  'harper@example.com', '415-555-0112',  10, NOW() - INTERVAL '8 days')
ON CONFLICT (email) DO NOTHING;

INSERT INTO employees (name, role, hourly_rate, hired_on, active)
SELECT v.name, v.role, v.hourly_rate, v.hired_on, v.active
FROM (VALUES
    ('Sam Ortiz',     'manager',    28.00, DATE '2022-03-01', TRUE),
    ('Riley Chen',    'shift_lead', 22.50, DATE '2023-01-15', TRUE),
    ('Jordan Blake',  'barista',    19.00, DATE '2023-06-01', TRUE),
    ('Amelia Diaz',   'barista',    19.50, DATE '2024-02-12', TRUE),
    ('Noah Kim',      'baker',      21.00, DATE '2023-11-04', TRUE),
    ('Casey Bell',    'barista',    18.50, DATE '2025-04-20', TRUE)
) AS v(name, role, hourly_rate, hired_on, active)
WHERE NOT EXISTS (SELECT 1 FROM employees e WHERE e.name = v.name);

INSERT INTO products (sku, name, category, unit_price, stock_qty, reorder_at, active) VALUES
    ('ESP-HOT',  'Espresso',                 'coffee',      3.50,  80, 20, TRUE),
    ('LAT-OAT',  'Oat Latte',                'coffee',      5.75,  60, 15, TRUE),
    ('CAP-CLS',  'Cappuccino',               'coffee',      4.75,  55, 15, TRUE),
    ('DRP-ETH',  'Ethiopia Pour Over',       'coffee',      5.50,   8, 10, TRUE),
    ('CLD-BRW',  'Cold Brew',                'coffee',      5.00,  24, 12, TRUE),
    ('TEA-EAR',  'Earl Grey',                'tea',         3.75,  30,  8, TRUE),
    ('TEA-JAS',  'Jasmine Green',            'tea',         3.75,  18,  8, TRUE),
    ('PST-CRO',  'Butter Croissant',         'pastry',      4.25,   6,  8, TRUE),
    ('PST-ALM',  'Almond Croissant',         'pastry',      4.75,   4,  6, TRUE),
    ('PST-MUF',  'Blueberry Muffin',         'pastry',      3.50,  12,  6, TRUE),
    ('FOD-BLT',  'BLT on Focaccia',          'food',        9.50,   9,  5, TRUE),
    ('FOD-AVO',  'Avocado Toast',            'food',        8.75,  11,  5, TRUE),
    ('MER-MUG',  'Harbor Mug',               'merchandise', 18.00, 14,  4, TRUE),
    ('MER-BGS',  'House Blend 12oz Beans',   'merchandise', 16.00,  3,  6, TRUE),
    ('MER-TEE',  'Harbor & Bean Tee',        'merchandise', 28.00,  7,  3, TRUE)
ON CONFLICT (sku) DO NOTHING;

-- Shifts: last 3 days + today + tomorrow, relative to CURRENT_DATE.
INSERT INTO shifts (employee_id, shift_date, start_time, end_time, station)
SELECT e.id, d.shift_date, d.start_time, d.end_time, d.station
FROM employees e
JOIN (VALUES
    ('Riley Chen',   CURRENT_DATE - 2, TIME '06:30', TIME '14:30', 'bar'),
    ('Jordan Blake', CURRENT_DATE - 2, TIME '06:30', TIME '14:30', 'bar'),
    ('Noah Kim',     CURRENT_DATE - 2, TIME '05:00', TIME '12:00', 'kitchen'),
    ('Amelia Diaz',  CURRENT_DATE - 2, TIME '14:00', TIME '21:00', 'bar'),
    ('Casey Bell',   CURRENT_DATE - 2, TIME '14:00', TIME '21:00', 'register'),
    ('Riley Chen',   CURRENT_DATE - 1, TIME '06:30', TIME '14:30', 'bar'),
    ('Amelia Diaz',  CURRENT_DATE - 1, TIME '06:30', TIME '14:30', 'register'),
    ('Noah Kim',     CURRENT_DATE - 1, TIME '05:00', TIME '12:00', 'kitchen'),
    ('Jordan Blake', CURRENT_DATE - 1, TIME '14:00', TIME '21:00', 'bar'),
    ('Casey Bell',   CURRENT_DATE - 1, TIME '14:00', TIME '21:00', 'bar'),
    ('Sam Ortiz',    CURRENT_DATE,     TIME '07:00', TIME '16:00', 'floor'),
    ('Riley Chen',   CURRENT_DATE,     TIME '06:30', TIME '14:30', 'bar'),
    ('Jordan Blake', CURRENT_DATE,     TIME '06:30', TIME '14:30', 'register'),
    ('Noah Kim',     CURRENT_DATE,     TIME '05:00', TIME '12:00', 'kitchen'),
    ('Amelia Diaz',  CURRENT_DATE,     TIME '14:00', TIME '21:00', 'bar'),
    ('Casey Bell',   CURRENT_DATE,     TIME '14:00', TIME '21:00', 'register'),
    ('Riley Chen',   CURRENT_DATE + 1, TIME '06:30', TIME '14:30', 'bar'),
    ('Amelia Diaz',  CURRENT_DATE + 1, TIME '06:30', TIME '14:30', 'bar'),
    ('Noah Kim',     CURRENT_DATE + 1, TIME '05:00', TIME '12:00', 'kitchen')
) AS d(emp_name, shift_date, start_time, end_time, station)
  ON e.name = d.emp_name
WHERE NOT EXISTS (
    SELECT 1 FROM shifts s
    WHERE s.employee_id = e.id
      AND s.shift_date = d.shift_date
      AND s.start_time = d.start_time
);

-- Historical + recent orders. Line items use the product's current unit_price.
DO $$
DECLARE
    rec RECORD;
    new_order_id INTEGER;
    barista_id INTEGER;
BEGIN
    IF (SELECT COUNT(*) FROM orders) > 0 THEN
        RETURN;
    END IF;

    SELECT id INTO barista_id FROM employees WHERE name = 'Jordan Blake';

    FOR rec IN
        SELECT * FROM (VALUES
            -- older
            ('maya@example.com',   NOW() - INTERVAL '18 days', 'completed', 'extra hot',
                ARRAY['LAT-OAT', 'PST-CRO']),
            ('priya@example.com',  NOW() - INTERVAL '16 days', 'completed', NULL,
                ARRAY['DRP-ETH', 'PST-ALM']),
            ('kenji@example.com',  NOW() - INTERVAL '14 days', 'completed', 'oat milk',
                ARRAY['LAT-OAT', 'LAT-OAT', 'PST-MUF']),
            ('jonah@example.com',  NOW() - INTERVAL '12 days', 'completed', NULL,
                ARRAY['CLD-BRW']),
            ('sofia@example.com',  NOW() - INTERVAL '11 days', 'completed', 'no onion',
                ARRAY['FOD-BLT', 'TEA-EAR']),
            ('nina@example.com',   NOW() - INTERVAL '9 days',  'completed', NULL,
                ARRAY['CAP-CLS', 'PST-CRO', 'MER-MUG']),
            ('omar@example.com',   NOW() - INTERVAL '8 days',  'cancelled', 'changed mind',
                ARRAY['ESP-HOT']),
            ('eli@example.com',    NOW() - INTERVAL '7 days',  'completed', NULL,
                ARRAY['FOD-AVO', 'CLD-BRW']),
            ('lila@example.com',   NOW() - INTERVAL '6 days',  'completed', NULL,
                ARRAY['TEA-JAS', 'PST-MUF']),
            ('avery@example.com',  NOW() - INTERVAL '5 days',  'completed', 'decaf',
                ARRAY['LAT-OAT']),
            ('theo@example.com',   NOW() - INTERVAL '4 days',  'completed', NULL,
                ARRAY['ESP-HOT', 'ESP-HOT', 'PST-CRO']),
            ('harper@example.com', NOW() - INTERVAL '3 days',  'completed', NULL,
                ARRAY['MER-BGS', 'CLD-BRW']),
            ('priya@example.com',  NOW() - INTERVAL '2 days',  'completed', 'extra shot',
                ARRAY['LAT-OAT', 'FOD-AVO']),
            ('maya@example.com',   NOW() - INTERVAL '2 days',  'completed', NULL,
                ARRAY['DRP-ETH']),
            ('kenji@example.com',  NOW() - INTERVAL '1 day',   'completed', NULL,
                ARRAY['CAP-CLS', 'PST-ALM', 'TEA-EAR']),
            ('sofia@example.com',  NOW() - INTERVAL '22 hours','completed', NULL,
                ARRAY['FOD-BLT', 'CLD-BRW']),
            ('nina@example.com',   NOW() - INTERVAL '18 hours','completed', 'almond milk',
                ARRAY['LAT-OAT', 'PST-MUF']),
            ('jonah@example.com',  NOW() - INTERVAL '8 hours', 'completed', NULL,
                ARRAY['ESP-HOT', 'MER-TEE']),
            -- today
            ('maya@example.com',   NOW() - INTERVAL '3 hours', 'completed', 'for here',
                ARRAY['LAT-OAT', 'PST-CRO']),
            ('priya@example.com',  NOW() - INTERVAL '90 minutes','completed', NULL,
                ARRAY['DRP-ETH', 'FOD-AVO']),
            ('theo@example.com',   NOW() - INTERVAL '40 minutes','ready', 'name on cup: Theo',
                ARRAY['CLD-BRW', 'PST-MUF']),
            ('harper@example.com', NOW() - INTERVAL '12 minutes','preparing', NULL,
                ARRAY['LAT-OAT', 'LAT-OAT', 'PST-ALM']),
            ('omar@example.com',   NOW() - INTERVAL '4 minutes', 'pending', 'oat, extra ice',
                ARRAY['CLD-BRW'])
        ) AS t(email, placed_at, status, notes, skus)
    LOOP
        INSERT INTO orders (customer_id, employee_id, status, notes, placed_at, completed_at)
        SELECT c.id,
               barista_id,
               rec.status,
               rec.notes,
               rec.placed_at,
               CASE WHEN rec.status = 'completed' THEN rec.placed_at + INTERVAL '8 minutes' ELSE NULL END
        FROM customers c
        WHERE c.email = rec.email
        RETURNING id INTO new_order_id;

        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
        SELECT new_order_id, p.id, COUNT(*)::int, p.unit_price
        FROM UNNEST(rec.skus) AS line(sku)
        JOIN products p ON p.sku = line.sku
        GROUP BY p.id, p.unit_price;
    END LOOP;
END $$;
