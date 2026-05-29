"""
Phase 1.1a: Extract ATP/WTA games (match results) from OnCourt.mdb.
Run: C:\\Python312-32\\python.exe scripts/oncourt-extract-games.py

Output:
  data/oncourt/games_atp.csv
  data/oncourt/games_wta.csv

Requires: oncourt-extract-rest has run first (tours_atp.csv for tour dates).

Usage:
  C:\\Python312-32\\python.exe scripts/oncourt-extract-games.py
  C:\\Python312-32\\python.exe scripts/oncourt-extract-games.py --list-tables   # debug: show tables
"""

import csv
import os
import sys

try:
    import pyodbc
except ImportError:
    print("Install pyodbc: C:\\Python312-32\\python.exe -m pip install pyodbc")
    sys.exit(1)

MDB_PATH = r"C:\Program Files (x86)\OnCourt\OnCourt.mdb"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "oncourt")


def load_tour_dates(tour):
    """Load tour_id -> date from tours CSV for games that lack date."""
    tour_date = {}
    path = os.path.join(OUT_DIR, f"tours_{tour}.csv")
    if not os.path.exists(path):
        return tour_date
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tid = row.get("id", "").strip()
            dt = row.get("date", "").strip()
            if tid and dt:
                tour_date[tid] = dt
    return tour_date


def main():
    pwd = os.environ.get("ONCOURT_PWD", "")
    if not pwd:
        print("Set ONCOURT_PWD environment variable")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    tours = {"atp", "wta"}
    if "--tour" in sys.argv:
        idx = sys.argv.index("--tour")
        if idx + 1 >= len(sys.argv) or sys.argv[idx + 1].lower() not in tours:
            print("Usage: --tour atp|wta")
            sys.exit(1)
        tours = {sys.argv[idx + 1].lower()}

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

    if "--list-tables" in sys.argv:
        crsr = conn.cursor()
        for row in crsr.tables(tableType="TABLE"):
            print(row.table_name)
        conn.close()
        return 0

    if "--list-columns" in sys.argv:
        table = "games_atp" if "atp" in tours else "games_wta"
        crsr = conn.cursor()
        crsr.execute(f"SELECT TOP 1 * FROM [{table}]")
        print(f"{table} columns:", [d[0] for d in crsr.description])
        conn.close()
        return 0

    for tour in sorted(tours):
        tour_date = load_tour_dates(tour)
        crsr = conn.cursor()
        tables_to_try = [f"games_{tour}", f"ep_{tour}", f"matches_{tour}"]
        table_used = None

        for table in tables_to_try:
            try:
                crsr.execute(f"SELECT TOP 1 * FROM [{table}]")
                table_used = table
                break
            except Exception:
                continue

        if not table_used:
            print(f"Could not read games/ep/matches table for {tour}")
            print("Run with --list-tables to see available tables")
            conn.close()
            sys.exit(1)

        cols = [str(d[0]).lower() for d in crsr.description]

        def _pick(*names):
            for n in names:
                if n in cols:
                    return n
            return None

        w_col = _pick("winner_id", "id_winner", "id1_g", "id1", "id_1")
        l_col = _pick("loser_id", "id_loser", "id2_g", "id2", "id_2")
        t_col = _pick("tour_id", "tour", "id_t_g", "id_t")
        r_col = _pick("round_id", "round", "id_r_g", "id_r")
        res_col = _pick("result", "result_g", "score", "res")
        date_col = _pick("date", "date_g", "date_t", "match_date")

        if not w_col or not l_col or not res_col:
            print(f"Unknown {table_used} schema. Columns:", cols)
            conn.close()
            sys.exit(1)

        rows_out = []
        crsr.execute(f"SELECT * FROM [{table_used}]")
        for row in crsr.fetchall():
            row_d = dict(zip(cols, row))
            w = row_d.get(w_col)
            l = row_d.get(l_col)
            if w is None or l is None:
                continue
            res = str(row_d.get(res_col) or "").strip()
            if not res or not res[0].isdigit():
                continue
            tid = row_d.get(t_col) or 0
            rid = row_d.get(r_col) or 0
            dt = row_d.get(date_col) if date_col else None
            if not dt and tid:
                dt = tour_date.get(str(tid), "")
            if hasattr(dt, "strftime"):
                dt = dt.strftime("%Y-%m-%d") if dt else ""
            rows_out.append({
                "winner_id": w,
                "loser_id": l,
                "tour_id": tid,
                "round_id": rid,
                "result": res,
                "date": dt or "",
            })

        out_path = os.path.join(OUT_DIR, f"games_{tour}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["winner_id", "loser_id", "tour_id", "round_id", "result", "date"])
            w.writeheader()
            w.writerows(rows_out)

        print(f"  {table_used}: {len(rows_out):,} rows -> games_{tour}.csv")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
