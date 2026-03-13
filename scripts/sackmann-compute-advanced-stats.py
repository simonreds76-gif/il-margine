"""
Compute advanced serve/return stats from Sackmann + TML, map IDs to OnCourt IDs,
and upsert to player_advanced_stats.

Run:
  python scripts/sackmann-compute-advanced-stats.py [--dry-run]
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import requests

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


def _to_int(v):
    if v is None or v == "":
        return 0
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def _safe_div(n, d):
    return None if d <= 0 else n / d


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


def _add_player_stats(
    agg,
    player_id,
    surface,
    svpt,
    first_in,
    first_won,
    second_won,
    ace,
    df,
    sv_gms,
    bp_saved,
    bp_faced,
    return_bp_converted,
    return_bp_chances,
):
    key = (player_id, surface)
    rec = agg[key]

    # Count match only when we have at least some serve/return stat signal.
    if svpt > 0 or sv_gms > 0 or bp_faced > 0 or return_bp_chances > 0:
        rec["match_count"] += 1

    rec["service_points"] += max(0, svpt)
    rec["service_games"] += max(0, sv_gms)

    rec["first_serves_in"] += max(0, first_in)
    rec["first_serve_points_won"] += max(0, first_won)

    second_points = max(0, svpt - first_in)
    rec["second_serve_points"] += second_points
    rec["second_serve_points_won"] += max(0, second_won)

    rec["aces"] += max(0, ace)
    rec["double_faults"] += max(0, df)

    rec["break_points_saved"] += max(0, bp_saved)
    rec["break_points_faced"] += max(0, bp_faced)

    rec["return_break_points_converted"] += max(0, return_bp_converted)
    rec["return_break_points_chances"] += max(0, return_bp_chances)


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
            f"{base}/player_advanced_stats",
            headers=post_headers,
            params={"on_conflict": "player_id,surface"},
            json=batch,
            timeout=120,
        )
        r.raise_for_status()
        print(f"  upserted {min(i + batch_size, total):,}/{total:,}")


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

    agg = defaultdict(
        lambda: {
            "match_count": 0,
            "service_points": 0,
            "service_games": 0,
            "first_serves_in": 0,
            "first_serve_points_won": 0,
            "second_serve_points": 0,
            "second_serve_points_won": 0,
            "aces": 0,
            "double_faults": 0,
            "break_points_saved": 0,
            "break_points_faced": 0,
            "return_break_points_converted": 0,
            "return_break_points_chances": 0,
        }
    )

    seen_rows = set()
    total_rows = 0
    skipped_duplicate_row = 0
    skipped_missing_cols = 0
    skipped_missing_map = 0

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

        w_svpt = _to_int(row.get("w_svpt"))
        w_1stin = _to_int(row.get("w_1stIn"))
        w_1stwon = _to_int(row.get("w_1stWon"))
        w_2ndwon = _to_int(row.get("w_2ndWon"))
        w_ace = _to_int(row.get("w_ace"))
        w_df = _to_int(row.get("w_df"))
        w_svgms = _to_int(row.get("w_SvGms"))
        w_bp_saved = _to_int(row.get("w_bpSaved"))
        w_bp_faced = _to_int(row.get("w_bpFaced"))

        l_svpt = _to_int(row.get("l_svpt"))
        l_1stin = _to_int(row.get("l_1stIn"))
        l_1stwon = _to_int(row.get("l_1stWon"))
        l_2ndwon = _to_int(row.get("l_2ndWon"))
        l_ace = _to_int(row.get("l_ace"))
        l_df = _to_int(row.get("l_df"))
        l_svgms = _to_int(row.get("l_SvGms"))
        l_bp_saved = _to_int(row.get("l_bpSaved"))
        l_bp_faced = _to_int(row.get("l_bpFaced"))

        # Winner return BP conversion comes from loser's BP faced/saved.
        w_return_bp_chances = l_bp_faced
        w_return_bp_converted = max(0, l_bp_faced - l_bp_saved)

        # Loser return BP conversion comes from winner's BP faced/saved.
        l_return_bp_chances = w_bp_faced
        l_return_bp_converted = max(0, w_bp_faced - w_bp_saved)

        _add_player_stats(
            agg,
            w_oncourt,
            surface,
            w_svpt,
            w_1stin,
            w_1stwon,
            w_2ndwon,
            w_ace,
            w_df,
            w_svgms,
            w_bp_saved,
            w_bp_faced,
            w_return_bp_converted,
            w_return_bp_chances,
        )

        _add_player_stats(
            agg,
            l_oncourt,
            surface,
            l_svpt,
            l_1stin,
            l_1stwon,
            l_2ndwon,
            l_ace,
            l_df,
            l_svgms,
            l_bp_saved,
            l_bp_faced,
            l_return_bp_converted,
            l_return_bp_chances,
        )

    rows = []
    for (player_id, surface), rec in agg.items():
        first_serve_pct = _safe_div(rec["first_serves_in"], rec["service_points"])
        first_serve_win_pct = _safe_div(rec["first_serve_points_won"], rec["first_serves_in"])
        second_serve_win_pct = _safe_div(rec["second_serve_points_won"], rec["second_serve_points"])
        ace_rate = _safe_div(rec["aces"], rec["service_points"])
        df_rate = _safe_div(rec["double_faults"], rec["service_points"])
        bp_save_pct = _safe_div(rec["break_points_saved"], rec["break_points_faced"])
        bp_convert_pct = _safe_div(rec["return_break_points_converted"], rec["return_break_points_chances"])

        rows.append(
            {
                "player_id": player_id,
                "surface": surface,
                "first_serve_pct": round(first_serve_pct, 4) if first_serve_pct is not None else None,
                "first_serve_win_pct": round(first_serve_win_pct, 4) if first_serve_win_pct is not None else None,
                "second_serve_win_pct": round(second_serve_win_pct, 4) if second_serve_win_pct is not None else None,
                "ace_rate": round(ace_rate, 4) if ace_rate is not None else None,
                "df_rate": round(df_rate, 4) if df_rate is not None else None,
                "bp_save_pct": round(bp_save_pct, 4) if bp_save_pct is not None else None,
                "bp_convert_pct": round(bp_convert_pct, 4) if bp_convert_pct is not None else None,
                "match_count": rec["match_count"],
                "service_points": rec["service_points"],
                "service_games": rec["service_games"],
                "first_serves_in": rec["first_serves_in"],
                "first_serve_points_won": rec["first_serve_points_won"],
                "second_serve_points": rec["second_serve_points"],
                "second_serve_points_won": rec["second_serve_points_won"],
                "aces": rec["aces"],
                "double_faults": rec["double_faults"],
                "break_points_saved": rec["break_points_saved"],
                "break_points_faced": rec["break_points_faced"],
                "return_break_points_converted": rec["return_break_points_converted"],
                "return_break_points_chances": rec["return_break_points_chances"],
            }
        )

    rows.sort(key=lambda x: (x["player_id"], x["surface"]))

    print(f"Raw match rows scanned: {total_rows:,}")
    print(f"Advanced stat rows computed: {len(rows):,}")
    print(f"Skipped duplicate rows: {skipped_duplicate_row:,}")
    print(f"Skipped missing cols/surface: {skipped_missing_cols:,}")
    print(f"Skipped missing ID map: {skipped_missing_map:,}")

    if args.dry_run:
        print("\nDry run sample:")
        for r in rows[:10]:
            print(r)
        return

    _upsert_rows(base, headers, rows, batch_size=args.batch_size)
    print("Done.")


if __name__ == "__main__":
    main()
