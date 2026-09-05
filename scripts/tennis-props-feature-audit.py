#!/usr/bin/env python3
"""Export lagged OnCourt feature candidates; never modify forecasts or gates.

Exact match dates and round IDs protect the current board from future/same-day
results and repeat opponents. This is a feature-availability audit, not a
point-in-time backtest: historical source publication timestamps are unknown.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path):
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)


def count(value: object) -> int | None:
    try:
        parsed = float(str(value))
        return int(parsed) if math.isfinite(parsed) and parsed >= 0 and parsed.is_integer() else None
    except (ValueError, TypeError):
        return None


def match_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "").strip() for field in ("winner_id", "loser_id", "tour_id", "round_id"))


def surface(name: str) -> str:
    return "Hard" if name.casefold() in {"hard", "i.hard", "acrylic"} else name


def observations(source: Path, tour: str, wanted: set[str], cutoff: date, lookback_days: int = 365) -> list[dict]:
    courts = {r["id"]: r.get("name", "") for r in rows(source / "courts.csv")}
    tournaments = {r["id"]: r for r in rows(source / f"tours_{tour.lower()}.csv")}
    games = {}
    for game in rows(source / f"games_{tour.lower()}.csv"):
        try:
            played = date.fromisoformat(game.get("date", "")[:10])
        except ValueError:
            continue
        if not cutoff - timedelta(days=lookback_days) <= played < cutoff:
            continue
        if not wanted.intersection((game.get("winner_id", ""), game.get("loser_id", ""))):
            continue
        if any(token in game.get("result", "").upper() for token in ("RET", "W/O", "WO", "DEF", "ABD")):
            continue
        games[match_key(game)] = dict(game, played=played)
    stats = {}
    conflicts = set()
    for stat in rows(source / f"stat_{tour.lower()}.csv"):
        key = match_key(stat)
        if key not in games:
            continue
        if key in stats and stats[key] != stat:
            conflicts.add(key)
        stats[key] = stat
    output = []
    for key, game in games.items():
        stat = stats.get(key) if key not in conflicts else None
        court = courts.get(tournaments.get(game.get("tour_id", ""), {}).get("court_id", ""), "")
        for prefix, other, player_id in (("w", "l", key[0]), ("l", "w", key[1])):
            if player_id not in wanted:
                continue
            record = {"player_id": player_id, "played": game["played"], "surface": surface(court), "court": court,
                      "source_key": "|".join(key), "valid": False, "reason": "conflicting_stats" if key in conflicts else "missing_stats"}
            if stat:
                values = {
                    "service_points": count(stat.get(f"{prefix}_svpt")),
                    "return_points": count(stat.get(f"{other}_svpt")),
                    "bp_faced": count(stat.get(f"{prefix}_bpfaced")),
                    "bp_saved": count(stat.get(f"{prefix}_bpsaved")),
                    "bp_created": count(stat.get(f"{other}_bpfaced")),
                    "opponent_bp_saved": count(stat.get(f"{other}_bpsaved")),
                    "double_faults": count(stat.get(f"{prefix}_df")),
                    "second_serve_attempts": count(stat.get(f"{prefix}_w2sof")),
                }
                core = [values[k] for k in ("service_points", "return_points", "bp_faced", "bp_saved", "bp_created", "opponent_bp_saved")]
                valid = (
                    all(v is not None for v in core)
                    and values["service_points"] > 0 and values["return_points"] > 0
                    and values["bp_saved"] <= values["bp_faced"] <= values["service_points"]
                    and values["opponent_bp_saved"] <= values["bp_created"] <= values["return_points"]
                )
                record.update(values, valid=valid, reason="ok" if valid else "invalid_break_stats")
            output.append(record)
    return output


def summarize(history: list[dict], player_id: str, target_surface: str, cutoff: date, days: int) -> dict:
    eligible = [r for r in history if r["player_id"] == player_id and r["surface"] == target_surface
                and cutoff - timedelta(days=days) <= r["played"] < cutoff]
    valid = [r for r in eligible if r["valid"]]
    total = lambda field: sum(r[field] for r in valid)
    ratio = lambda numerator, denominator, scale=1: round(numerator / denominator * scale, 6) if denominator else ""
    faced, created = total("bp_faced"), total("bp_created")
    dfs = [r for r in valid if r.get("double_faults") is not None and r.get("second_serve_attempts") is not None
           and 0 <= r["double_faults"] <= r["second_serve_attempts"] <= r["service_points"] and r["second_serve_attempts"] > 0]
    return {
        "eligible_matches": len(eligible), "valid_matches": len(valid),
        "coverage_pct": ratio(len(valid), len(eligible), 100),
        "latest_match_date": max((r["played"] for r in eligible), default="").isoformat() if eligible else "",
        "latest_valid_stats_date": max((r["played"] for r in valid), default="").isoformat() if valid else "",
        "days_since_valid_stats": (cutoff - max(r["played"] for r in valid)).days if valid else "",
        "service_points_sample": total("service_points"), "return_points_sample": total("return_points"),
        "bp_faced_sample": faced, "bp_created_sample": created,
        "bp_faced_per_100_service_points": ratio(faced, total("service_points"), 100),
        "bp_created_per_100_return_points": ratio(created, total("return_points"), 100),
        "bp_saved_rate": ratio(total("bp_saved"), faced),
        "bp_conversion_rate": ratio(created - total("opponent_bp_saved"), created),
        "df_second_serve_matches": len(dfs),
        "df_per_second_serve_attempt": ratio(sum(r["double_faults"] for r in dfs), sum(r["second_serve_attempts"] for r in dfs)),
    }


def build(board: list[dict[str, str]], source: Path, as_of: date) -> tuple[list[dict], dict]:
    wanted = {tour: {r.get(field, "") for r in board if r.get("tour") == tour for field in ("player_id", "opponent_id")} - {""}
              for tour in ("ATP", "WTA")}
    history = {tour: observations(source, tour, ids, as_of) for tour, ids in wanted.items() if ids}
    output = []
    for match in board:
        try:
            event_date = date.fromisoformat(match.get("date", "")[:10])
        except ValueError:
            continue
        cutoff = min(event_date, as_of)
        if cutoff != as_of:
            continue  # A current-board audit never rewrites historical features.
        row = {"date": match.get("date", ""), "as_of": as_of.isoformat(), "tour": match.get("tour", ""),
               "player": match.get("player", ""), "opponent": match.get("opponent", ""),
               "surface": match.get("surface", ""), "status": "FEATURE_AUDIT_ONLY", "model_eligible": "false",
               "source": "oncourt_exact_match_date_and_round", "source_publication_timestamps": "unavailable"}
        row["incumbent_activity_last_match_date"] = match.get("player_activity_last_match_date", "")
        for role in ("player", "opponent"):
            for days in (90, 365):
                values = summarize(history.get(row["tour"], []), match.get(f"{role}_id", ""), row["surface"], cutoff, days)
                row.update({f"{role}_l{days}d_{key}": value for key, value in values.items()})
        latest_source = row["player_l365d_latest_valid_stats_date"]
        latest_incumbent = row["incumbent_activity_last_match_date"]
        row["newer_source_stats_available"] = str(bool(latest_source and latest_incumbent and latest_source > latest_incumbent)).lower()
        output.append(row)
    reasons = Counter(r["reason"] for values in history.values() for r in values)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "as_of": as_of.isoformat(),
        "status": "FEATURE_AUDIT_ONLY", "automatic_promotion": False, "board_rows": len(output),
        "historical_player_observations": sum(reasons.values()), "source_quality": dict(reasons),
        "board_rows_with_newer_source_stats": sum(r["newer_source_stats_available"] == "true" for r in output),
        "incumbent_latest_activity_date": max((r["incumbent_activity_last_match_date"] for r in output), default=""),
        "available_source_latest_stats_date": max((r["player_l365d_latest_valid_stats_date"] for r in output), default=""),
        "feature_candidates": ["break points created per 100 return points", "break points faced per 100 service points",
                               "break-point conversion and save rates", "double faults per second-serve attempt"],
        "restrictions": ["No bookmaker break-point market definition inferred", "No live forecasts or weights changed",
                         "Only exact match dates strictly before as_of; same-day results excluded",
                         "Source publication timestamps unknown; this is not a point-in-time backtest",
                         "Service games are not exported by this OnCourt table; point denominators are explicit",
                         "Historical corrected source data requires archived vintages before promotion testing"],
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=ROOT / "data/tennis-props/player-props-board.csv")
    parser.add_argument("--oncourt-dir", type=Path, default=ROOT / "data/oncourt")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--out", type=Path, default=ROOT / "data/tennis-props/experiments/break-point-feature-audit.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "data/tennis-props/experiments/break-point-feature-audit.json")
    args = parser.parse_args()
    output, report = build(list(rows(args.board)), args.oncourt_dir, date.fromisoformat(args.as_of))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]) if output else ["status"])
        writer.writeheader()
        writer.writerows(output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
