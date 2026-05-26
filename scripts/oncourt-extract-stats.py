"""
Extract ATP match stat rows from OnCourt.mdb to data/oncourt/stat_atp.csv.

Run:
  C:\\Python312-32\\python.exe scripts\\oncourt-extract-stats.py

The downstream player-surface model expects the legacy compact columns
(`w_fs`, `w_fsof`, etc.) and can also consume optional decomposition columns
(`w_ace`, `w_df`, `w_bpw`, ...). This extractor writes both so serve/return
features stay current and richer than the old static CSV.
"""

import csv
import os
import sys
import tempfile

try:
    import pyodbc
except ImportError:
    print("Install pyodbc: C:\\Python312-32\\python.exe -m pip install pyodbc")
    sys.exit(1)

MDB_PATH = r"C:\Program Files (x86)\OnCourt\OnCourt.mdb"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "oncourt")

FIELDNAMES = [
    "winner_id",
    "loser_id",
    "tour_id",
    "round_id",
    "w_fs",
    "w_fsof",
    "w_w1s",
    "w_w1sof",
    "w_w2s",
    "w_w2sof",
    "w_rpw",
    "w_rpwof",
    "l_fs",
    "l_fsof",
    "l_w1s",
    "l_w1sof",
    "l_w2s",
    "l_w2sof",
    "l_rpw",
    "l_rpwof",
    # Optional richer columns consumed by oncourt-compute-player-stats-extended.py
    "w_ace",
    "w_df",
    "w_bpw",
    "w_bpof",
    "w_bpsaved",
    "w_bpfaced",
    "w_svpt",
    "l_ace",
    "l_df",
    "l_bpw",
    "l_bpof",
    "l_bpsaved",
    "l_bpfaced",
    "l_svpt",
]


def _value(row, key, default=""):
    value = row.get(key)
    return default if value is None else value


def _int_value(row, key, default=0):
    value = row.get(key)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _connect():
    pwd = os.environ.get("ONCOURT_PWD", "")
    if not pwd:
        print("Set ONCOURT_PWD environment variable")
        sys.exit(1)

    drivers = [
        d for d in pyodbc.drivers()
        if "Access" in d and "Text" not in d and "Excel" not in d
    ]
    for drv in drivers:
        try:
            return pyodbc.connect(f"DRIVER={{{drv}}};DBQ={MDB_PATH};PWD={pwd};")
        except Exception:
            continue
    print("Could not connect to OnCourt.mdb")
    sys.exit(1)


def _list_columns(conn, table):
    crsr = conn.cursor()
    cols = [row.column_name for row in crsr.columns(table=table)]
    print(f"{table} columns:")
    for col in cols:
        print(f"  {col}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = _connect()

    if "--list-columns" in sys.argv:
        _list_columns(conn, "stat_atp")
        conn.close()
        return 0

    crsr = conn.cursor()
    try:
        crsr.execute("SELECT * FROM [stat_atp]")
    except Exception as exc:
        print(f"Could not read stat_atp: {exc}")
        conn.close()
        return 1

    cols = [str(d[0]).upper() for d in crsr.description]
    required = {
        "ID1", "ID2", "ID_T", "ID_R",
        "FS_1", "FSOF_1", "W1S_1", "W1SOF_1", "W2S_1", "W2SOF_1", "RPW_1", "RPWOF_1",
        "FS_2", "FSOF_2", "W1S_2", "W1SOF_2", "W2S_2", "W2SOF_2", "RPW_2", "RPWOF_2",
    }
    missing = sorted(required - set(cols))
    if missing:
        print(f"Unknown stat_atp schema. Missing columns: {', '.join(missing)}")
        print(f"Available columns: {', '.join(cols)}")
        conn.close()
        return 1

    out_path = os.path.join(OUT_DIR, "stat_atp.csv")
    total = 0
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="stat_atp.", suffix=".tmp", dir=OUT_DIR, text=True)
    try:
        f = os.fdopen(tmp_fd, "w", newline="", encoding="utf-8")
    except Exception:
        os.close(tmp_fd)
        raise

    try:
        with f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            while True:
                batch = crsr.fetchmany(5000)
                if not batch:
                    break
                for raw in batch:
                    row = dict(zip(cols, raw))

                    w_bp_won = _int_value(row, "BP_1")
                    w_bp_of = _int_value(row, "BPOF_1")
                    l_bp_won = _int_value(row, "BP_2")
                    l_bp_of = _int_value(row, "BPOF_2")

                    writer.writerow({
                        "winner_id": _value(row, "ID1"),
                        "loser_id": _value(row, "ID2"),
                        "tour_id": _value(row, "ID_T"),
                        "round_id": _value(row, "ID_R"),
                        "w_fs": _value(row, "FS_1"),
                        "w_fsof": _value(row, "FSOF_1"),
                        "w_w1s": _value(row, "W1S_1"),
                        "w_w1sof": _value(row, "W1SOF_1"),
                        "w_w2s": _value(row, "W2S_1"),
                        "w_w2sof": _value(row, "W2SOF_1"),
                        "w_rpw": _value(row, "RPW_1"),
                        "w_rpwof": _value(row, "RPWOF_1"),
                        "l_fs": _value(row, "FS_2"),
                        "l_fsof": _value(row, "FSOF_2"),
                        "l_w1s": _value(row, "W1S_2"),
                        "l_w1sof": _value(row, "W1SOF_2"),
                        "l_w2s": _value(row, "W2S_2"),
                        "l_w2sof": _value(row, "W2SOF_2"),
                        "l_rpw": _value(row, "RPW_2"),
                        "l_rpwof": _value(row, "RPWOF_2"),
                        "w_ace": _value(row, "ACES_1"),
                        "w_df": _value(row, "DF_1"),
                        "w_bpw": w_bp_won,
                        "w_bpof": w_bp_of,
                        "w_bpsaved": max(0, l_bp_of - l_bp_won),
                        "w_bpfaced": l_bp_of,
                        "w_svpt": _int_value(row, "FSOF_1") + _int_value(row, "W2SOF_1"),
                        "l_ace": _value(row, "ACES_2"),
                        "l_df": _value(row, "DF_2"),
                        "l_bpw": l_bp_won,
                        "l_bpof": l_bp_of,
                        "l_bpsaved": max(0, w_bp_of - w_bp_won),
                        "l_bpfaced": w_bp_of,
                        "l_svpt": _int_value(row, "FSOF_2") + _int_value(row, "W2SOF_2"),
                    })
                    total += 1

        os.replace(tmp_path, out_path)
        tmp_path = ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    conn.close()
    print(f"  stat_atp: {total:,} rows -> stat_atp.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
