"""
Phase 1.1c: Extract players_atp, tours_atp, courts, today_atp from OnCourt.mdb.
Run: C:\\Python312-32\\python.exe scripts/oncourt-extract-rest.py

Output: data/oncourt/players_atp.csv, tours_atp.csv, courts.csv, today_atp.csv
"""

import os
import sys
import csv

try:
    import pyodbc
except ImportError:
    print("Install pyodbc: C:\\Python312-32\\python.exe -m pip install pyodbc")
    sys.exit(1)

MDB_PATH = r"C:\Program Files (x86)\OnCourt\OnCourt.mdb"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "oncourt")


def extract_table(conn, table, cols_sql, cols_out, out_file):
    crsr = conn.cursor()
    crsr.execute(f"SELECT {cols_sql} FROM [{table}]")
    total = 0
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols_out)
        for row in crsr.fetchall():
            writer.writerow([x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else (x if x is not None else "") for x in row])
            total += 1
    print(f"  {table}: {total:,} rows -> {os.path.basename(out_file)}")


def main():
    pwd = os.environ.get("ONCOURT_PWD", "")
    if not pwd:
        print("Set ONCOURT_PWD environment variable")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)

    drivers = [d for d in pyodbc.drivers() if "Access" in d and "Text" not in d and "Excel" not in d]
    conn = None
    for drv in drivers:
        try:
            conn = pyodbc.connect(f"DRIVER={{{drv}}};DBQ={MDB_PATH};PWD={pwd};")
            break
        except Exception:
            continue
    if not conn:
        print("Could not connect to OnCourt.mdb")
        sys.exit(1)

    print("Extracting...")
    extract_table(conn, "players_atp", "ID_P, NAME_P, DATE_P, COUNTRY_P", ["id", "name", "birthdate", "country"], os.path.join(OUT_DIR, "players_atp.csv"))
    extract_table(conn, "tours_atp", "ID_T, NAME_T, ID_C_T, DATE_T, RANK_T, COUNTRY_T", ["id", "name", "court_id", "date", "rank", "country"], os.path.join(OUT_DIR, "tours_atp.csv"))
    extract_table(conn, "courts", "ID_C, NAME_C", ["id", "name"], os.path.join(OUT_DIR, "courts.csv"))
    extract_table(conn, "today_atp", "TOUR, ID1, ID2, ROUND, DRAW, RESULT", ["tour_id", "player1_id", "player2_id", "round_id", "draw", "result"], os.path.join(OUT_DIR, "today_atp.csv"))

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
