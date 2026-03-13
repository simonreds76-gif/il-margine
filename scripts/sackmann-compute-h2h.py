"""
Compute H2H from Sackmann (all atp_matches*.csv) + TML (year >= 2025),
map IDs to OnCourt IDs, and upsert to player_h2h.

Run:
  python scripts/sackmann-compute-h2h.py [--dry-run]
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import requests

# Allow importing sackmann_tml_id_map when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sackmann_tml_id_map import (
    build_player_id_map,
    canonical_surface,
    discover_match_files,
    get_supabase_rest,
    iter_match_rows,
    load_env,
    parse_tourney_date,
)


def _upsert_rows(base, headers, rows, batch_size=1000):
    post_headers = {
        **headers,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    total = len(rows)
    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        r = requests.post(
            f"{base}/player_h2h",
            headers=post_headers,
            params={"on_conflict": "player_a_id,player_b_id,surface"},
            json=batch,
            timeout=120,
        )
        r.raise_for_status()
        print(f"  upserted {min(i + batch_size, total):,}/{total:,}")


def _dedupe_key(source, row):
    return (
        source,
        (row.get("tourney_id") or "").strip(),
        (row.get("match_num") or "").strip(),
        (row.get("round") or "").strip(),
        (row.get("winner_id") or "").strip(),
        (row.get("loser_id") or "").strip(),
        parse_tourney_date(row.get("tourney_date")) or "",
        (row.get("score") or "").strip(),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--tml-min-year", type=int, default=2025)
    parser.add_argument("--tml-max-year", type=int, default=None)
    args = parser.parse_args()

    load_env()
    base, headers = get_supabase_rest()

    sackmann_files, tml_files = discover_match_files(args.tml_min_year, args.tml_max_year)
    print(f"Sackmann files: {len(sackmann_files)}")
    print(f"TML files (>= {args.tml_min_year}): {len(tml_files)}")

    id_map, report = build_player_id_map(base, headers, sackmann_files, tml_files)
    print(f"Mapped IDs: {report['mapped_ids']:,} / {report['source_ids_total']:,}")

    agg = defaultdict(lambda: {"wins_a": 0, "wins_b": 0, "match_count": 0, "last_match_date": None})

    seen_rows = set()
    total_rows = 0
    skipped_duplicate_row = 0
    skipped_missing_cols = 0
    skipped_missing_map = 0
    skipped_same_player = 0

    for source, _path, row in iter_match_rows(sackmann_files, tml_files):
        total_rows += 1

        dkey = _dedupe_key(source, row)
        if dkey in seen_rows:
            skipped_duplicate_row += 1
            continue
        seen_rows.add(dkey)

        w_src = (row.get("winner_id") or "").strip()
        l_src = (row.get("loser_id") or "").strip()
        if not w_src or not l_src:
            skipped_missing_cols += 1
            continue

        surface = canonical_surface(row.get("surface"), row.get("indoor"))
        if surface == "N/A":
            skipped_missing_cols += 1
            continue

        w_oncourt = id_map.get((source, w_src))
        l_oncourt = id_map.get((source, l_src))
        if w_oncourt is None or l_oncourt is None:
            skipped_missing_map += 1
            continue

        if w_oncourt == l_oncourt:
            skipped_same_player += 1
            continue

        if w_oncourt < l_oncourt:
            a, b = w_oncourt, l_oncourt
            winner_is_a = True
        else:
            a, b = l_oncourt, w_oncourt
            winner_is_a = False

        key = (a, b, surface)
        rec = agg[key]
        if winner_is_a:
            rec["wins_a"] += 1
        else:
            rec["wins_b"] += 1
        rec["match_count"] += 1

        dt = parse_tourney_date(row.get("tourney_date"))
        if dt and (rec["last_match_date"] is None or dt > rec["last_match_date"]):
            rec["last_match_date"] = dt

    rows = []
    for (a, b, surface), rec in agg.items():
        rows.append(
            {
                "player_a_id": a,
                "player_b_id": b,
                "surface": surface,
                "wins_a": rec["wins_a"],
                "wins_b": rec["wins_b"],
                "match_count": rec["match_count"],
                "last_match_date": rec["last_match_date"],
            }
        )
    rows.sort(key=lambda x: (x["player_a_id"], x["player_b_id"], x["surface"]))

    print(f"Raw match rows scanned: {total_rows:,}")
    print(f"H2H rows computed: {len(rows):,}")
    print(f"Skipped duplicate rows: {skipped_duplicate_row:,}")
    print(f"Skipped missing cols/surface: {skipped_missing_cols:,}")
    print(f"Skipped missing ID map: {skipped_missing_map:,}")
    print(f"Skipped same player after mapping: {skipped_same_player:,}")

    if args.dry_run:
        print("\nDry run sample:")
        for r in rows[:10]:
            print(r)
        return

    _upsert_rows(base, headers, rows, batch_size=args.batch_size)
    print("Done.")


if __name__ == "__main__":
    main()
