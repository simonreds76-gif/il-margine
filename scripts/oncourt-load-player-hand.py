"""
Load player_hand_reference from OnCourt categories_atp.csv.
cat1=True means left-handed (L). Populates Supabase for chat-tools and fair-odds.
Run: python scripts/oncourt-load-player-hand.py
Requires: data/oncourt/categories_atp.csv (from OnCourt)
Also runs as part of: python scripts/oncourt-load-supabase.py

The loader auto-negotiates payload format for the live table:
- tries existing source values already in DB
- tries common source candidates
- falls back to payload without "source" when needed
"""

import csv
import os
import sys
from pathlib import Path
from time import sleep as _sleep

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "oncourt"
CATEGORIES_CSV = DATA_DIR / "categories_atp.csv"
MIGRATION_SQL = ROOT / "docs" / "supabase-player-hand-reference-fix.sql"
BATCH = 5000
HAND_SOURCE_CANDIDATES = (
    "oncourt",
    "categories_atp",
    "oncourt_categories",
    "manual",
    "atp",
    "import",
    "script",
)


def _load_env():
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_known_player_ids():
    players_csv = DATA_DIR / "players_atp.csv"
    if not players_csv.exists():
        return set()
    ids = set()
    with open(players_csv, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = row.get("id")
            if not pid:
                continue
            try:
                ids.add(int(pid))
            except ValueError:
                continue
    return ids


def _headers():
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def _run_hand_reference_migration():
    """Run migration via psycopg2 if DATABASE_URL is set. Returns True if run successfully."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url or not MIGRATION_SQL.exists():
        return False
    try:
        import psycopg2

        sql = MIGRATION_SQL.read_text(encoding="utf-8")
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print("  Applied player_hand_reference fix (DATABASE_URL).")
        return True
    except Exception as e:
        print(f"  Migration failed: {e}")
        return False


def _is_source_constraint_error(text):
    if not text:
        return False
    t = text.lower()
    return (
        "player_hand_reference_source_check" in t
        or ("source" in t and "check" in t)
        or 'null value in column "source"' in t
    )


def _is_source_column_missing_error(text):
    if not text:
        return False
    return 'column "source" does not exist' in text.lower()


def _player_hand_payload(rows, source_value):
    if source_value is None:
        return [{"player_id": r["player_id"], "hand": "L"} for r in rows]
    return [{"player_id": r["player_id"], "hand": "L", "source": source_value} for r in rows]


def _post_player_hand_rows(url, headers, rows, source_value, retries=2):
    api_url = f"{url}/rest/v1/player_hand_reference?on_conflict=player_id"
    payload = _player_hand_payload(rows, source_value)
    last_status = 0
    last_text = ""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=120)
            if resp.ok:
                return True, resp.status_code, ""
            last_status = resp.status_code
            last_text = resp.text or ""
        except requests.RequestException as e:
            last_status = -1
            last_text = str(e)
        if attempt < retries:
            _sleep(2 ** attempt)
    return False, last_status, last_text


def _delete_existing_lefties(url, headers, retries=2):
    api_url = f"{url}/rest/v1/player_hand_reference"
    last_status = 0
    last_text = ""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.delete(api_url, headers=headers, params={"hand": "eq.L"}, timeout=60)
            if resp.ok:
                return True, resp.status_code, ""
            last_status = resp.status_code
            last_text = resp.text or ""
        except requests.RequestException as e:
            last_status = -1
            last_text = str(e)
        if attempt < retries:
            _sleep(2 ** attempt)
    return False, last_status, last_text


def _detect_player_hand_has_source_column(url, headers):
    api_url = f"{url}/rest/v1/player_hand_reference"
    try:
        resp = requests.get(api_url, headers=headers, params={"select": "source", "limit": 1}, timeout=30)
    except requests.RequestException:
        return None
    if resp.ok:
        return True
    if _is_source_column_missing_error(resp.text):
        return False
    return None


def _fetch_existing_player_hand_sources(url, headers):
    api_url = f"{url}/rest/v1/player_hand_reference"
    try:
        resp = requests.get(
            api_url,
            headers=headers,
            params={"select": "source", "source": "not.is.null", "limit": 2000},
            timeout=30,
        )
    except requests.RequestException:
        return []
    if not resp.ok:
        return []
    try:
        data = resp.json()
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    seen = set()
    for row in data:
        source = row.get("source")
        if not isinstance(source, str):
            continue
        source = source.strip()
        if not source or source in seen:
            continue
        seen.add(source)
        out.append(source)
    return out


def _resolve_player_hand_source_mode(url, headers, rows):
    sample = rows[: min(25, len(rows))]
    has_source_column = _detect_player_hand_has_source_column(url, headers)
    candidates = []

    if has_source_column is False:
        candidates = [None]
    else:
        for source in _fetch_existing_player_hand_sources(url, headers):
            if source not in candidates:
                candidates.append(source)
        for source in HAND_SOURCE_CANDIDATES:
            if source not in candidates:
                candidates.append(source)
        candidates.append(None)

    tried = []
    for source in candidates:
        ok, status, _ = _post_player_hand_rows(url, headers, sample, source, retries=1)
        label = source if source is not None else "<omit>"
        if ok:
            if tried:
                print(f"  player_hand_reference: source negotiation -> {label}")
            return source
        tried.append((label, status))

    if _run_hand_reference_migration():
        for source in ("oncourt", None):
            ok, status, _ = _post_player_hand_rows(url, headers, sample, source, retries=1)
            label = source if source is not None else "<omit>"
            if ok:
                print(f"  player_hand_reference: source negotiation after migration -> {label}")
                return source
            tried.append((f"{label} (post-migration)", status))

    summary = ", ".join(f"{label}:{status}" for label, status in tried[-8:])
    raise RuntimeError(f"source negotiation failed ({summary})")


def main():
    _load_env()
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

    if not url or not key:
        print("ERROR: Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local")
        sys.exit(1)

    if not CATEGORIES_CSV.exists():
        print(f"ERROR: {CATEGORIES_CSV} not found.")
        print("  Ensure categories_atp.csv exists (from OnCourt extract).")
        sys.exit(1)

    rows = []
    with open(CATEGORIES_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = row.get("player_id")
            if not pid:
                continue
            try:
                pid = int(pid)
            except ValueError:
                continue
            if str(row.get("cat1") or "").strip().lower() == "true":
                rows.append({"player_id": pid, "hand": "L"})

    if rows:
        known_player_ids = _load_known_player_ids()
        if known_player_ids:
            before = len(rows)
            rows = [r for r in rows if r["player_id"] in known_player_ids]
            skipped = before - len(rows)
            if skipped:
                print(f"  player_hand_reference: skipped {skipped:,} rows (player_id missing in players_atp.csv)")

    if not rows:
        print("WARNING: No left-handed players (cat1=True) in categories_atp.csv")
        sys.exit(0)

    hdrs = _headers()
    total = len(rows)
    try:
        source_mode = _resolve_player_hand_source_mode(url, hdrs, rows)
    except RuntimeError as e:
        print(f"ERROR: player_hand_reference: {e}")
        sys.exit(1)

    ok, status, err_text = _delete_existing_lefties(url, hdrs, retries=3)
    if not ok:
        print(f"ERROR: player_hand_reference delete existing lefties failed status={status}: {err_text[:300]}")
        sys.exit(1)

    for i in range(0, total, BATCH):
        batch = rows[i : i + BATCH]
        ok, status, err_text = _post_player_hand_rows(url, hdrs, batch, source_mode, retries=3)
        if not ok:
            print(f"ERROR: player_hand_reference batch failed status={status}: {err_text[:300]}")
            if _is_source_constraint_error(err_text):
                print("  Source constraint blocked all negotiated payloads.")
            sys.exit(1)
        print(f"  player_hand_reference: {min(i + BATCH, total):,} / {total:,}")

    mode = source_mode if source_mode is not None else "<omit>"
    print(f"Done. {total:,} left-handed players in player_hand_reference (source={mode}).")


if __name__ == "__main__":
    main()
