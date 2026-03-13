"""
List all tables and columns in OnCourt.mdb.
Run: C:\\Python312-32\\python.exe scripts/oncourt-list-tables.py

Use this to find the rankings table (e.g. rankings_atp, player_rankings) for extraction.
"""

import os
import sys

try:
    import pyodbc
except ImportError:
    print("Install pyodbc: C:\\Python312-32\\python.exe -m pip install pyodbc")
    sys.exit(1)

MDB_PATH = r"C:\Program Files (x86)\OnCourt\OnCourt.mdb"


def main():
    pwd = os.environ.get("ONCOURT_PWD", "")
    if not pwd:
        print("Set ONCOURT_PWD environment variable")
        sys.exit(1)

    drivers = [d for d in pyodbc.drivers() if "Access" in d and "Text" not in d and "Excel" not in d]
    conn = None
    for drv in drivers:
        try:
            conn = pyodbc.connect(f"DRIVER={{{drv}}};DBQ={MDB_PATH};PWD={pwd};")
            break
        except Exception as e:
            print(f"  {drv}: {e}")
            continue
    if not conn:
        print("Could not connect to OnCourt.mdb")
        sys.exit(1)

    crsr = conn.cursor()
    tables = [row[2] for row in crsr.tables() if row[3] == "TABLE"]
    tables.sort()

    print(f"OnCourt.mdb: {len(tables)} tables\n")
    print("=" * 60)

    for t in tables:
        if "rank" in t.lower() or "point" in t.lower() or "player" in t.lower():
            print(f"\n>>> {t}")
        else:
            print(f"\n{t}")
        try:
            cols = [row[3] for row in crsr.columns(table=t)]
            for c in cols[:15]:
                print(f"    {c}")
            if len(cols) > 15:
                print(f"    ... (+{len(cols) - 15} more)")
        except Exception as e:
            print(f"    (error: {e})")

    conn.close()
    print("\nDone. Look for tables with 'rank' or 'point' in the name.")


if __name__ == "__main__":
    main()
