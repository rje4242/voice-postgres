#!/usr/bin/env python3
"""Companion SQL console for the Harbor & Bean Postgres started by this repo.

    python scripts/db_console.py
    python scripts/db_console.py -c "SELECT * FROM v_low_stock"
    python scripts/db_console.py --preview products
    python scripts/db_console.py low
"""

from voice_postgres.console import main

if __name__ == "__main__":
    raise SystemExit(main())
