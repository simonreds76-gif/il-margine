"""
Phase 1.1c: Extract players/tours/today from OnCourt.mdb.
Run: C:\\Python312-32\\python.exe scripts/oncourt-extract-rest.py

Output:
  - data/oncourt/players_atp.csv (includes ATP rank + surface points)
  - data/oncourt/players_wta.csv (includes WTA rank + surface points)
  - data/oncourt/categories_atp.csv (OnCourt category flags; CAT1=True marks left-handed ATP players)
  - data/oncourt/categories_wta.csv (OnCourt category flags; extracted for diagnostics/future WTA use)
  - data/oncourt/tours_atp.csv
  - data/oncourt/tours_wta.csv
  - data/oncourt/courts.csv
  - data/oncourt/today_atp.csv
  - data/oncourt/today_wta.csv
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
    player_cols_sql = "ID_P, NAME_P, DATE_P, COUNTRY_P, RANK_P, POINT_P, HARDPOINT_P, CLAYPOINT_P, GRASSPOINT_P"
    extract_table(
        conn,
        "players_atp",
        player_cols_sql,
        ["id", "name", "birthdate", "country", "atp_rank", "points", "hard_points", "clay_points", "grass_points"],
        os.path.join(OUT_DIR, "players_atp.csv"),
    )
    extract_table(
        conn,
        "players_wta",
        player_cols_sql,
        ["id", "name", "birthdate", "country", "wta_rank", "points", "hard_points", "clay_points", "grass_points"],
        os.path.join(OUT_DIR, "players_wta.csv"),
    )
    for tour in ("atp", "wta"):
        category_cols_sql = "ID_P, " + ", ".join(f"CAT{i}" for i in range(1, 31))
        category_cols_out = ["player_id"] + [f"cat{i}" for i in range(1, 31)]
        extract_table(
            conn,
            f"categories_{tour}",
            category_cols_sql,
            category_cols_out,
            os.path.join(OUT_DIR, f"categories_{tour}.csv"),
        )

    for tour in ("atp", "wta"):
        extract_table(conn, f"tours_{tour}", "ID_T, NAME_T, ID_C_T, DATE_T, RANK_T, COUNTRY_T", ["id", "name", "court_id", "date", "rank", "country"], os.path.join(OUT_DIR, f"tours_{tour}.csv"))
    extract_table(conn, "courts", "ID_C, NAME_C", ["id", "name"], os.path.join(OUT_DIR, "courts.csv"))
    for tour in ("atp", "wta"):
        extract_table(conn, f"today_{tour}", "TOUR, DATE_GAME, ID1, ID2, ROUND, DRAW, RESULT, COMPLETE, LIVE, TIME_GAME", ["tour_id", "date", "player1_id", "player2_id", "round_id", "draw", "result", "complete", "live", "time"], os.path.join(OUT_DIR, f"today_{tour}.csv"))

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
