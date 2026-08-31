#!/usr/bin/env python3
"""Build docs/harbor-and-bean-database.pdf — Harbor & Bean schema reference."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "harbor-and-bean-database.pdf"

INK = colors.HexColor("#1c1410")
COPPER = colors.HexColor("#c45c26")
CREAM = colors.HexColor("#f3ead8")
MUTED = colors.HexColor("#6b5a4a")
LINE = colors.HexColor("#d9cbb8")
HEADER_BG = colors.HexColor("#2a1c16")
ROW_ALT = colors.HexColor("#f7f1e6")
WHITE = colors.white


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover": ParagraphStyle(
            "cover",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=26,
            leading=30,
            textColor=CREAM,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=12,
            leading=16,
            textColor=CREAM,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=16,
            leading=20,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=8,
            borderPadding=0,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=12,
            leading=15,
            textColor=COPPER,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=8.5,
            leading=11,
            textColor=INK,
        ),
        "th": ParagraphStyle(
            "th",
            parent=base["BodyText"],
            fontName="Times-Bold",
            fontSize=8.5,
            leading=11,
            textColor=CREAM,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=8.5,
            leading=11,
            textColor=INK,
        ),
        "mono": ParagraphStyle(
            "mono",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=8,
            leading=11,
            textColor=INK,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=8,
        ),
    }
    return s


S = styles()


def P(text: str, style="cell") -> Paragraph:
    return Paragraph(text, S[style])


def grid(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    head = [P(h, "th") for h in headers]
    body = [[P(c, "cell") for c in row] for row in rows]
    data = [head, *body]
    tbl = Table(data, colWidths=widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 1), (-1, -1), WHITE),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    tbl.setStyle(TableStyle(cmds))
    return tbl


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = letter
    canvas.setFillColor(HEADER_BG)
    canvas.rect(0, h - 36, w, 36, fill=1, stroke=0)
    canvas.setFillColor(CREAM)
    canvas.setFont("Times-Bold", 9)
    canvas.drawString(0.75 * inch, h - 22, "voice-postgres  ·  Harbor & Bean")
    canvas.setFont("Times-Roman", 9)
    canvas.drawRightString(w - 0.75 * inch, h - 22, "Database reference")
    canvas.setFillColor(COPPER)
    canvas.rect(0, h - 38, w, 3, fill=1, stroke=0)
    canvas.setFillColor(HEADER_BG)
    canvas.rect(0, 0, w, 32, fill=1, stroke=0)
    canvas.setFillColor(CREAM)
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(0.75 * inch, 14, "postgresql://voice@127.0.0.1:55432/voice_postgres")
    canvas.drawRightString(w - 0.75 * inch, 14, f"Page {doc.page}")
    canvas.restoreState()


def cover_page(canvas, doc):
    if doc.page != 1:
        header_footer(canvas, doc)
        return
    canvas.saveState()
    w, h = letter
    canvas.setFillColor(HEADER_BG)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setFillColor(COPPER)
    canvas.rect(0, h * 0.42, w, 8, fill=1, stroke=0)
    canvas.setFillColor(CREAM)
    canvas.setFont("Times-Roman", 11)
    canvas.drawCentredString(w / 2, h * 0.62, "voice-postgres")
    canvas.setFont("Times-Bold", 28)
    canvas.drawCentredString(w / 2, h * 0.54, "Harbor & Bean")
    canvas.setFont("Times-Italic", 14)
    canvas.drawCentredString(w / 2, h * 0.48, "Cafe operations database — reference guide")
    canvas.setFont("Times-Roman", 10)
    canvas.drawCentredString(w / 2, h * 0.36, "Schema  ·  seed catalog  ·  voice tools  ·  example SQL")
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(w / 2, 0.7 * inch, "Local Postgres on 127.0.0.1:55432  ·  regenerated from sql/ and tools.py")
    canvas.restoreState()


def bullets(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(P(i, "body"), leftIndent=8, bulletColor=COPPER) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=16,
        bulletFontName="Times-Roman",
        bulletFontSize=10,
    )


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    usable = 7.5 * inch
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.55 * inch,
        title="Harbor & Bean database reference",
        author="voice-postgres",
        subject="PostgreSQL schema for the Harbor & Bean cafe voice agent",
    )

    story: list = [
        Spacer(1, 5.6 * inch),
        PageBreak(),
        P("1. Overview", "h1"),
        P(
            "Harbor &amp; Bean is a neighborhood cafe. This database is created by the "
            "voice-postgres project (<font face='Courier'>sql/01_schema.sql</font> and "
            "<font face='Courier'>sql/02_seed.sql</font>) and is what the xAI Voice Agent "
            "queries through custom function tools.",
            "body",
        ),
        P("Connect", "h2"),
        P("<font face='Courier'>postgresql://voice:voice@127.0.0.1:55432/voice_postgres</font>", "body"),
        P(
            "Docker Compose publishes that port on loopback only. The companion console is "
            "<font face='Courier'>python scripts/db_console.py</font> after <font face='Courier'>source ./env.sh</font>.",
            "body",
        ),
        P("What lives here", "h2"),
        bullets(
            [
                "7 tables: customers, employees, products, orders, order_items, shifts, inventory_adjustments",
                "3 views: v_order_totals, v_low_stock, v_daily_sales",
                "Seed: 12 guests, 6 staff, 15 SKUs, ~23 tickets, shifts for yesterday / today / tomorrow",
            ]
        ),
        P("2. Relationships", "h1"),
        P(
            "Orders belong to a customer and optionally an employee. Line items snapshot "
            "<font face='Courier'>unit_price</font> at purchase time. Inventory adjustments "
            "are an audit log; <font face='Courier'>products.stock_qty</font> is the live on-hand count.",
            "body",
        ),
        grid(
            ["From", "Column", "To", "On delete"],
            [
                ["orders", "customer_id", "customers.id", "restrict"],
                ["orders", "employee_id", "employees.id", "nullable / restrict"],
                ["order_items", "order_id", "orders.id", "CASCADE"],
                ["order_items", "product_id", "products.id", "restrict"],
                ["shifts", "employee_id", "employees.id", "restrict"],
                ["inventory_adjustments", "product_id", "products.id", "restrict"],
            ],
            [1.5 * inch, 1.5 * inch, 2.4 * inch, 2.1 * inch],
        ),
        P(
            "Ticket flow: <b>pending → preparing → ready → completed</b> (or <b>cancelled</b> from any open state).",
            "caption",
        ),
        P("3. Tables", "h1"),
    ]

    tables = [
        (
            "customers",
            "Cafe guests with loyalty accounts. Email is unique.",
            [
                ["id", "serial PK", ""],
                ["name", "text not null", ""],
                ["email", "text unique not null", "Lookup key for create_order"],
                ["phone", "text", "nullable"],
                ["loyalty_points", "int not null default 0", ""],
                ["created_at", "timestamptz default now()", ""],
            ],
        ),
        (
            "employees",
            "Staff. role ∈ barista | baker | shift_lead | manager.",
            [
                ["id", "serial PK", ""],
                ["name", "text not null", ""],
                ["role", "text not null", "checked enum"],
                ["hourly_rate", "numeric(6,2) not null", ""],
                ["hired_on", "date not null", ""],
                ["active", "boolean default true", ""],
            ],
        ),
        (
            "products",
            "Menu and merch. category ∈ coffee | tea | pastry | food | merchandise. stock_qty is on-hand.",
            [
                ["id", "serial PK", ""],
                ["sku", "text unique not null", "e.g. LAT-OAT"],
                ["name", "text not null", ""],
                ["category", "text not null", "checked enum"],
                ["unit_price", "numeric(8,2) not null", "≥ 0"],
                ["stock_qty", "int not null default 0", "≥ 0"],
                ["reorder_at", "int not null default 5", "low-stock threshold"],
                ["active", "boolean default true", ""],
            ],
        ),
        (
            "orders",
            "Customer tickets. status ∈ pending | preparing | ready | completed | cancelled.",
            [
                ["id", "serial PK", ""],
                ["customer_id", "int not null FK", "→ customers"],
                ["employee_id", "int FK", "→ employees, nullable"],
                ["status", "text not null default pending", "checked enum"],
                ["notes", "text", "nullable"],
                ["placed_at", "timestamptz default now()", "indexed"],
                ["completed_at", "timestamptz", "set on completed/cancelled"],
            ],
        ),
        (
            "order_items",
            "Line items. unit_price is copied from the product at order time.",
            [
                ["id", "serial PK", ""],
                ["order_id", "int not null FK", "→ orders CASCADE"],
                ["product_id", "int not null FK", "→ products"],
                ["quantity", "int not null", "> 0"],
                ["unit_price", "numeric(8,2) not null", "snapshot"],
            ],
        ),
        (
            "shifts",
            "Who is scheduled, on which day and station (bar, register, kitchen, floor).",
            [
                ["id", "serial PK", ""],
                ["employee_id", "int not null FK", "→ employees"],
                ["shift_date", "date not null", "indexed"],
                ["start_time", "time not null", ""],
                ["end_time", "time not null", ""],
                ["station", "text not null default bar", ""],
            ],
        ),
        (
            "inventory_adjustments",
            "Audit log of stock changes (receiving, waste, voice-agent edits and sales).",
            [
                ["id", "serial PK", ""],
                ["product_id", "int not null FK", "→ products"],
                ["delta", "int not null", "signed quantity"],
                ["reason", "text not null", ""],
                ["created_at", "timestamptz default now()", ""],
            ],
        ),
    ]

    col_w = [1.6 * inch, 2.4 * inch, 3.5 * inch]
    for name, comment, cols in tables:
        block = [
            P(f"<font face='Courier'>{name}</font>", "h2"),
            P(comment, "caption"),
            grid(["Column", "Type", "Notes"], cols, col_w),
            Spacer(1, 8),
        ]
        story.append(KeepTogether(block))

    story += [
        P("4. Views", "h1"),
        P("<font face='Courier'>v_order_totals</font>", "h2"),
        P(
            "One row per order: order_id, customer_id, status, placed_at, "
            "<b>total</b> (sum of quantity × unit_price), <b>item_count</b>. "
            "Use this instead of re-aggregating order_items.",
            "body",
        ),
        P("<font face='Courier'>v_low_stock</font>", "h2"),
        P(
            "Active products where stock_qty ≤ reorder_at, ordered by stock then name. "
            "Columns: id, sku, name, category, stock_qty, reorder_at.",
            "body",
        ),
        P("<font face='Courier'>v_daily_sales</font>", "h2"),
        P(
            "Orders and revenue by UTC calendar day, excluding cancelled tickets. "
            "Columns: sale_date, orders, revenue.",
            "body",
        ),
        P("5. Seed catalog", "h1"),
        P("Products (SKU is the voice-agent lookup key)", "h2"),
        grid(
            ["SKU", "Name", "Category", "Price", "Reorder"],
            [
                ["ESP-HOT", "Espresso", "coffee", "3.50", "20"],
                ["LAT-OAT", "Oat Latte", "coffee", "5.75", "15"],
                ["CAP-CLS", "Cappuccino", "coffee", "4.75", "15"],
                ["DRP-ETH", "Ethiopia Pour Over", "coffee", "5.50", "10"],
                ["CLD-BRW", "Cold Brew", "coffee", "5.00", "12"],
                ["TEA-EAR", "Earl Grey", "tea", "3.75", "8"],
                ["TEA-JAS", "Jasmine Green", "tea", "3.75", "8"],
                ["PST-CRO", "Butter Croissant", "pastry", "4.25", "8"],
                ["PST-ALM", "Almond Croissant", "pastry", "4.75", "6"],
                ["PST-MUF", "Blueberry Muffin", "pastry", "3.50", "6"],
                ["FOD-BLT", "BLT on Focaccia", "food", "9.50", "5"],
                ["FOD-AVO", "Avocado Toast", "food", "8.75", "5"],
                ["MER-MUG", "Harbor Mug", "merchandise", "18.00", "4"],
                ["MER-BGS", "House Blend 12oz Beans", "merchandise", "16.00", "6"],
                ["MER-TEE", "Harbor &amp; Bean Tee", "merchandise", "28.00", "3"],
            ],
            [1.15 * inch, 2.35 * inch, 1.45 * inch, 1.0 * inch, 1.55 * inch],
        ),
        P("On-hand stock in seed data varies; several pastries and beans start at or below reorder_at.", "caption"),
        P("Customers (email is the order lookup key)", "h2"),
        grid(
            ["Name", "Email", "Phone"],
            [
                ["Maya Alvarez", "maya@example.com", "415-555-0101"],
                ["Jonah Park", "jonah@example.com", "415-555-0102"],
                ["Priya Shah", "priya@example.com", "415-555-0103"],
                ["Eli Nguyen", "eli@example.com", "415-555-0104"],
                ["Sofia Rossi", "sofia@example.com", "415-555-0105"],
                ["Avery Cole", "avery@example.com", "415-555-0106"],
                ["Kenji Watanabe", "kenji@example.com", "415-555-0107"],
                ["Lila Brooks", "lila@example.com", "415-555-0108"],
                ["Omar Haddad", "omar@example.com", "415-555-0109"],
                ["Nina Volkov", "nina@example.com", "415-555-0110"],
                ["Theo Marin", "theo@example.com", "415-555-0111"],
                ["Harper Quinn", "harper@example.com", "415-555-0112"],
            ],
            [2.2 * inch, 2.6 * inch, 2.7 * inch],
        ),
        P("Employees", "h2"),
        grid(
            ["Name", "Role", "Rate"],
            [
                ["Sam Ortiz", "manager", "28.00"],
                ["Riley Chen", "shift_lead", "22.50"],
                ["Jordan Blake", "barista", "19.00"],
                ["Amelia Diaz", "barista", "19.50"],
                ["Noah Kim", "baker", "21.00"],
                ["Casey Bell", "barista", "18.50"],
            ],
            [2.5 * inch, 2.5 * inch, 2.5 * inch],
        ),
        P(
            "Shifts are relative to CURRENT_DATE (two days back through tomorrow). "
            "Stations: bar, register, kitchen, floor.",
            "caption",
        ),
        P("6. Voice agent tools", "h1"),
        P(
            "The Speech to Speech session exposes these functions. "
            "<font face='Courier'>query_database</font> is SELECT/WITH only, 4s timeout, max 50 rows. "
            "Writes always confirm with the operator first.",
            "body",
        ),
        grid(
            ["Tool", "Purpose", "Key arguments"],
            [
                ["inspect_schema", "List tables/views and columns", "optional table_name"],
                ["query_database", "Read-only SQL", "sql"],
                ["create_customer", "Insert a loyalty guest", "name, email, phone?"],
                ["create_order", "New ticket; decrements stock", "customer_email, items[{product, quantity}], notes?, employee_name?"],
                ["update_order_status", "Move a ticket", "order_id, status"],
                ["adjust_inventory", "Signed stock change + audit row", "product, delta, reason"],
            ],
            [1.7 * inch, 2.4 * inch, 3.4 * inch],
        ),
        P("7. Example SQL", "h1"),
        P(
            "<font face='Courier'>SELECT * FROM v_low_stock;</font><br/>"
            "<font face='Courier'>SELECT e.name, s.station, s.start_time, s.end_time FROM shifts s JOIN employees e ON e.id = s.employee_id WHERE s.shift_date = CURRENT_DATE ORDER BY s.start_time;</font><br/>"
            "<font face='Courier'>SELECT c.name, SUM(t.total) AS spend FROM v_order_totals t JOIN customers c ON c.id = t.customer_id WHERE t.status &lt;&gt; 'cancelled' AND t.placed_at &gt;= NOW() - INTERVAL '30 days' GROUP BY c.name ORDER BY spend DESC;</font><br/>"
            "<font face='Courier'>SELECT o.id, c.name, o.status, o.notes, t.total FROM orders o JOIN customers c ON c.id = o.customer_id JOIN v_order_totals t ON t.order_id = o.id WHERE o.status NOT IN ('completed','cancelled') ORDER BY o.placed_at;</font>",
            "body",
        ),
        P("Console shortcuts (after <font face='Courier'>source ./env.sh</font>)", "h2"),
        grid(
            ["Command", "Meaning"],
            [
                ["python scripts/db_console.py", "Interactive voice=&gt; prompt"],
                ["\\tables  /  \\views  /  \\d products", "Catalog"],
                ["\\preview orders", "First 20 rows"],
                ["\\low  \\open  \\shift  \\sales", "Stock, open tickets, today’s shifts, daily sales"],
                ["python scripts/db_console.py -c \"SQL\"", "One-shot query"],
            ],
            [3.4 * inch, 4.1 * inch],
        ),
        P("Things to ask the voice agent", "h2"),
        bullets(
            [
                "What’s low in stock?",
                "Who’s on the bar today?",
                "What’s revenue for the last seven days?",
                "Which tickets are still open?",
                "Who is the top customer by spend?",
                "Create an order for Maya: two oat lattes and a croissant.",
                "Mark the pending cold brew as ready.",
                "We wasted three almond croissants — take them off the shelf.",
            ]
        ),
        Spacer(1, 16),
        P(
            "Regenerate this PDF: <font face='Courier'>python scripts/make_db_guide.py</font> "
            "(requires reportlab).",
            "caption",
        ),
    ]

    doc.build(story, onFirstPage=cover_page, onLaterPages=header_footer)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
