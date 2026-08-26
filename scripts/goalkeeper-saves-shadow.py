#!/usr/bin/env python3
"""Build the prospective Goalkeeper Saves v1 candidate and shadow ledgers."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from football_team_names import football_form_team_key
from goalkeeper_saves_live import (
    ROOT,
    build_features,
    league_key,
    load_lineup_index,
    load_team_histories,
    parse_day,
    parse_float,
    predict_mean,
    price_side,
    resolve_goalkeeper,
)


DEFAULT_HISTORY = ROOT / "data" / "goalkeeper-saves" / "gk-saves-odds-history.csv"
DEFAULT_FORM = ROOT / "data" / "football-form" / "team-match-base.csv"
DEFAULT_PARAMS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-params.json"
DEFAULT_CANDIDATES = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-candidates.csv"
DEFAULT_SIGNALS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-shadow-signals.csv"
DEFAULT_REPORT = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-shadow-report.json"
DEFAULT_REPORT_MD = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-shadow-report.md"
DEFAULT_PROVISIONAL = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-provisional.csv"

# Goalkeeper markets are materially less rotation-sensitive than outfield-player
# props. Track both expected and confirmed starting keepers in the research ledger,
# while retaining the lineup status so the two cohorts can be evaluated separately.
TRACKABLE_STARTER_STATUSES = {"confirmed_starter", "predicted_starter"}
PRIMARY_MIN_EDGE = 0.05
PRIMARY_MIN_ODDS = 1.70
PRIMARY_MAX_ODDS = 3.00
PRIMARY_SELECTION_POLICY = "near_even_value_v2"
LEGACY_SELECTION_POLICY = "max_edge_tail_v1"

CANDIDATE_FIELDS = [
    "generated_at", "event_id", "match_date", "kickoff_at", "league", "home_team", "away_team",
    "team", "opponent", "venue", "goalkeeper", "line", "side", "odds_decimal", "model_mean",
    "model_probability", "push_probability", "fair_odds", "edge", "lineup_status", "lineup_source",
    "capture_mode", "captured_at", "candidate_status", "blockers", "strongest_for_fixture",
    "selection_policy", "three_way_source",
]
PROVISIONAL_FIELDS = CANDIDATE_FIELDS + ["research_only", "not_a_signal"]
SIGNAL_FIELDS = [
    "signal_id", "created_at", "event_id", "match_date", "kickoff_at", "league", "home_team", "away_team",
    "team", "opponent", "venue", "goalkeeper", "line", "side", "odds_decimal", "model_mean",
    "model_probability", "push_probability", "fair_odds", "edge", "stake_units", "lineup_status",
    "lineup_source", "capture_mode", "captured_at", "status", "result", "actual_saves", "pnl_units",
    "settled_at", "settlement_source", "close_odds", "clv", "selection_policy",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


INFRASTRUCTURE_BLOCKERS = {
    "history_lt_6",
    "effective_history_lt_6",
    "missing_registered_feature",
    "missing_three_way_market",
}


def should_preserve_candidate_board(
    existing: list[dict[str, str]],
    scanned: list[dict[str, Any]],
    now: datetime | None = None,
) -> bool:
    if not existing:
        return False
    effective_now = now or datetime.now(UTC)
    if not board_has_current_rows(existing, effective_now):
        return False
    if not scanned:
        return True
    if any(row.get("candidate_status") == "eligible_shadow" or row.get("model_mean") for row in scanned):
        return False
    return all(
        bool(set(str(row.get("blockers") or "").split("|")) & INFRASTRUCTURE_BLOCKERS)
        for row in scanned
    )


def provisional_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in candidates:
        blockers = {item for item in str(row.get("blockers") or "").split("|") if item}
        if blockers != {"predicted_starter"} or parse_float(row.get("edge")) is None:
            continue
        rows.append({**row, "research_only": "true", "not_a_signal": "true"})
    return rows


def apply_starter_tracking_policy(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reclassify synced boards using the current GK-only shadow policy."""
    normalized: list[dict[str, Any]] = []
    for source in candidates:
        row = dict(source)
        blockers = {item for item in str(row.get("blockers") or "").split("|") if item}
        lineup_status = str(row.get("lineup_status") or "")
        if lineup_status in TRACKABLE_STARTER_STATUSES:
            blockers.discard(lineup_status)

        edge = parse_float(row.get("edge"))
        if edge is None:
            blockers.add("missing_priced_edge")
        elif edge < PRIMARY_MIN_EDGE:
            blockers.add("edge_below_5pct")
        else:
            blockers.discard("edge_below_8pct")
            blockers.discard("edge_below_5pct")

        if not blockers:
            odds = parse_float(row.get("odds_decimal"))
            if odds is not None and PRIMARY_MIN_ODDS <= odds <= PRIMARY_MAX_ODDS:
                row["candidate_status"] = "eligible_shadow"
                row["selection_policy"] = PRIMARY_SELECTION_POLICY
            else:
                row["candidate_status"] = "tail_diagnostic"
                row["selection_policy"] = "tail_diagnostic"
        elif blockers == {"edge_below_5pct"}:
            row["candidate_status"] = "no_edge"
            row["selection_policy"] = ""
        else:
            row["candidate_status"] = "blocked"
            row["selection_policy"] = ""
        row["blockers"] = "|".join(sorted(blockers))
        normalized.append(row)
    return normalized


def board_has_current_rows(rows: list[dict[str, Any]], now: datetime) -> bool:
    for row in rows:
        try:
            kickoff = datetime.fromisoformat(str(row.get("kickoff_at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if kickoff >= now - timedelta(minutes=15):
            return True
    return False


def latest_price_rows(rows: list[dict[str, str]], now: datetime) -> list[dict[str, str]]:
    latest: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        kickoff_text = str(row.get("kickoff_at") or "")
        try:
            kickoff = datetime.fromisoformat(kickoff_text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if kickoff < now - timedelta(minutes=15):
            continue
        key = (
            str(row.get("event_id") or ""),
            str(row.get("player") or "").casefold(),
            str(row.get("line") or ""),
            str(row.get("side") or "").casefold(),
        )
        if key not in latest or str(row.get("captured_at") or "") > str(latest[key].get("captured_at") or ""):
            latest[key] = row
    return list(latest.values())


def lineup_paths() -> list[Path]:
    paths = list((ROOT / "data" / "goalscorer").glob("*-confirmed-lineups.json"))
    serie_a = ROOT / "data" / "goalscorer" / "confirmed-lineups.json"
    if serie_a.exists():
        paths.append(serie_a)
    return paths


def build_candidates(
    prices: list[dict[str, str]],
    histories: dict[str, list[dict[str, str]]],
    params: dict[str, Any],
    lineup_index: dict[tuple[str, str, str], dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for price_row in prices:
        match_day = parse_day(price_row.get("match_date"))
        if match_day is None:
            continue
        home = str(price_row.get("home_team") or "").strip()
        away = str(price_row.get("away_team") or "").strip()
        fixture = lineup_index.get(
            (match_day.isoformat(), football_form_team_key(home), football_form_team_key(away))
        )
        player = str(price_row.get("player") or "").strip()
        side, lineup_status, canonical_player = resolve_goalkeeper(fixture, player)
        blockers: list[str] = []
        if lineup_status not in TRACKABLE_STARTER_STATUSES:
            blockers.append(lineup_status)

        team = home if side == "home" else away if side == "away" else ""
        opponent = away if side == "home" else home if side == "away" else ""
        venue = side
        model_mean = None
        priced: dict[str, float] = {}
        if not team:
            blockers.append("goalkeeper_team_unresolved")
        else:
            features, feature_blockers = build_features(
                histories=histories,
                team=team,
                opponent=opponent,
                venue=venue,
                kickoff_day=match_day,
                home_price=parse_float(price_row.get("home_price")) or 0.0,
                draw_price=parse_float(price_row.get("draw_price")) or 0.0,
                away_price=parse_float(price_row.get("away_price")) or 0.0,
            )
            blockers.extend(feature_blockers)
            if features is not None:
                league = str(price_row.get("league") or "") or league_key(price_row.get("competition"))
                model_mean = predict_mean(params, features, league, venue)
                priced = price_side(
                    str(price_row.get("side") or "over"),
                    parse_float(price_row.get("line")) or 0.0,
                    parse_float(price_row.get("odds_decimal")) or 0.0,
                    model_mean,
                    float(params["alpha"]),
                )

        edge = priced.get("edge")
        if edge is not None and edge < PRIMARY_MIN_EDGE:
            blockers.append("edge_below_5pct")
        if not blockers:
            odds = parse_float(price_row.get("odds_decimal"))
            status = (
                "eligible_shadow"
                if odds is not None and PRIMARY_MIN_ODDS <= odds <= PRIMARY_MAX_ODDS
                else "tail_diagnostic"
            )
        elif set(blockers) == {"edge_below_5pct"}:
            status = "no_edge"
        else:
            status = "blocked"
        rows.append(
            {
                "generated_at": generated_at,
                "event_id": price_row.get("event_id", ""),
                "match_date": match_day.isoformat(),
                "kickoff_at": price_row.get("kickoff_at", ""),
                "league": price_row.get("league", "") or league_key(price_row.get("competition")),
                "home_team": home,
                "away_team": away,
                "team": team,
                "opponent": opponent,
                "venue": venue,
                "goalkeeper": canonical_player or player,
                "line": price_row.get("line", ""),
                "side": str(price_row.get("side") or "over").casefold(),
                "odds_decimal": price_row.get("odds_decimal", ""),
                "model_mean": f"{model_mean:.4f}" if model_mean is not None else "",
                "model_probability": f"{priced['model_probability']:.6f}" if priced else "",
                "push_probability": f"{priced['push_probability']:.6f}" if priced else "",
                "fair_odds": f"{priced['fair_odds']:.3f}" if priced else "",
                "edge": f"{edge:.6f}" if edge is not None else "",
                "lineup_status": lineup_status,
                "lineup_source": "fotmob_confirmed_lineups" if fixture else "",
                "capture_mode": price_row.get("capture_mode", ""),
                "captured_at": price_row.get("captured_at", ""),
                "three_way_source": str(price_row.get("source") or "").split(":")[-1],
                "candidate_status": status,
                "blockers": "|".join(sorted(set(blockers))),
                "strongest_for_fixture": "no",
                "selection_policy": PRIMARY_SELECTION_POLICY if status == "eligible_shadow" else "tail_diagnostic" if status == "tail_diagnostic" else "",
            }
        )

    mark_primary_selections(rows)
    return sorted(rows, key=lambda row: (row["kickoff_at"], row["home_team"], -float(row["edge"] or -999)))


def mark_primary_selections(rows: list[dict[str, Any]]) -> None:
    """Choose one robust, near-even value line per fixture."""
    by_fixture: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        row["strongest_for_fixture"] = "no"
        by_fixture.setdefault(str(row["event_id"]), []).append(row)
    for fixture_rows in by_fixture.values():
        eligible = [row for row in fixture_rows if row.get("candidate_status") == "eligible_shadow"]
        if not eligible:
            continue
        primary = min(
            eligible,
            key=lambda row: (
                abs((parse_float(row.get("odds_decimal")) or 999.0) - 2.0),
                -(parse_float(row.get("model_probability")) or 0.0),
                -(parse_float(row.get("edge")) or 0.0),
            ),
        )
        primary["strongest_for_fixture"] = "yes"


def append_signals(path: Path, candidates: list[dict[str, Any]], generated_at: str) -> tuple[int, list[dict[str, str]]]:
    existing = read_csv(path)
    for row in existing:
        if not str(row.get("selection_policy") or "").strip():
            row["selection_policy"] = LEGACY_SELECTION_POLICY
    keys = {str(row.get("signal_id") or "") for row in existing}
    added = 0
    for row in candidates:
        if row["candidate_status"] != "eligible_shadow" or row["strongest_for_fixture"] != "yes":
            continue
        signal_id = "|".join(
            (str(row["event_id"]), str(row["goalkeeper"]).casefold(), str(row["line"]), str(row["side"]))
        )
        if signal_id in keys:
            continue
        signal = {field: "" for field in SIGNAL_FIELDS}
        signal.update(row)
        signal.update(
            {
                "signal_id": signal_id,
                "created_at": generated_at,
                "stake_units": "0.5",
                "status": "pending",
                "selection_policy": PRIMARY_SELECTION_POLICY,
            }
        )
        existing.append({field: str(signal.get(field, "")) for field in SIGNAL_FIELDS})
        keys.add(signal_id)
        added += 1
    write_csv(path, existing, SIGNAL_FIELDS)
    return added, existing


def report_payload(
    candidates: list[dict[str, Any]],
    signals: list[dict[str, str]],
    generated_at: str,
    added: int,
    *,
    board_preserved: bool = False,
    provisional_count: int = 0,
) -> dict[str, Any]:
    settled = [row for row in signals if str(row.get("status") or "").lower() in {"won", "lost", "push", "void"}]
    pending = [row for row in signals if str(row.get("status") or "").lower() == "pending"]
    pnl = sum(parse_float(row.get("pnl_units")) or 0.0 for row in settled)
    staked = sum(parse_float(row.get("stake_units")) or 0.0 for row in settled if row.get("status") not in {"push", "void"})
    clv_values = [value for row in settled if (value := parse_float(row.get("clv"))) is not None]
    close_coverage = len(clv_values) / len(settled) if settled else None
    eligible = [row for row in candidates if row.get("candidate_status") == "eligible_shadow"]
    tail_diagnostics = [row for row in candidates if row.get("candidate_status") == "tail_diagnostic"]
    blocked = [row for row in candidates if row.get("candidate_status") == "blocked"]
    blocker_counts = Counter(
        blocker
        for row in candidates
        for blocker in str(row.get("blockers") or "").split("|")
        if blocker
    )
    return {
        "generated_at": generated_at,
        "candidate": "goalkeeper-saves-v1-nb2-confirmed-starter",
        "status": (
            "SIGNALS_COLLECTING" if signals else
            "PROVISIONAL_ONLY" if provisional_count else
            "CANDIDATES_BLOCKED" if candidates else
            "NO_CURRENT_LINES"
        ),
        "count_model": "PASS",
        "live_routing": False,
        "sellable": False,
        "selection_rule": "one predicted/confirmed starting goalkeeper line per fixture; edge >=5%; price 1.70-3.00; closest to even money",
        "current": {
            "priced_lines": sum(1 for row in candidates if row.get("model_mean")),
            "eligible_lines": len(eligible),
            "tail_diagnostic_lines": len(tail_diagnostics),
            "blocked_lines": len(blocked),
            "signals_added": added,
            "provisional_lines": provisional_count,
            "candidate_board_preserved": board_preserved,
            "blocker_counts": dict(sorted(blocker_counts.items())),
        },
        "evidence": {
            "signals": len(signals),
            "pending": len(pending),
            "settled": len(settled),
            "pnl_units": round(pnl, 4),
            "roi": round(pnl / staked, 6) if staked else None,
            "clv_matched": len(clv_values),
            "true_close_coverage": round(close_coverage, 6) if close_coverage is not None else None,
            "clv": round(sum(clv_values) / len(clv_values), 6) if clv_values else None,
        },
        "promotion": {
            "status": "BLOCKED",
            "settled_required": 150,
            "true_close_coverage_required": 0.70,
            "mean_true_close_clv_required": 0.005,
            "settlement_integrity": "API_FOOTBALL_PLAYER_STATS",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Goalkeeper Saves v1 prospective evidence")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--params", type=Path, default=DEFAULT_PARAMS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--provisional", type=Path, default=DEFAULT_PROVISIONAL)
    args = parser.parse_args()

    if not args.form.exists() or args.form.stat().st_size == 0:
        raise SystemExit(f"FORM_LAYER_MISSING: {args.form}")

    now = datetime.now(UTC).replace(microsecond=0)
    generated_at = now.isoformat().replace("+00:00", "Z")
    params = json.loads(args.params.read_text(encoding="utf-8"))
    prices = latest_price_rows(read_csv(args.history), now)
    candidates = apply_starter_tracking_policy(build_candidates(
        prices,
        load_team_histories(args.form),
        params,
        load_lineup_index(lineup_paths()),
        generated_at,
    ))
    existing_candidates = apply_starter_tracking_policy(read_csv(args.candidates))
    board_preserved = should_preserve_candidate_board(existing_candidates, candidates, now)
    effective_candidates = existing_candidates if board_preserved else candidates
    write_csv(args.candidates, effective_candidates, CANDIDATE_FIELDS)
    provisional = provisional_rows(effective_candidates)
    write_csv(args.provisional, provisional, PROVISIONAL_FIELDS)
    added, signals = append_signals(args.signals, effective_candidates, generated_at)
    payload = report_payload(
        effective_candidates,
        signals,
        generated_at,
        added,
        board_preserved=board_preserved,
        provisional_count=len(provisional),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence = payload["evidence"]
    current = payload["current"]
    lines = [
        "# Goalkeeper Saves v1 prospective evidence",
        "",
        "**RESEARCH SHADOW ONLY. No live routing or staking authorization.**",
        "",
        f"- Generated: {generated_at}",
        f"- Status: {payload['status']}",
        f"- Current priced/eligible/blocked: {current['priced_lines']}/{current['eligible_lines']}/{current['blocked_lines']}",
        f"- Provisional research lines: {current['provisional_lines']} (never appended to the signal ledger)",
        f"- Candidate board preserved after infrastructure failure: {current['candidate_board_preserved']}",
        f"- Signals: {evidence['signals']} ({evidence['pending']} pending, {evidence['settled']} settled)",
        f"- P/L: {evidence['pnl_units']:+.2f}u; ROI: {evidence['roi'] if evidence['roi'] is not None else '-'}",
        f"- Closing evidence: {evidence['clv_matched']}/{evidence['settled']} matched; mean CLV: {evidence['clv'] if evidence['clv'] is not None else '-'}",
        "- Settlement integrity: named-player API-Football saves; promotion remains blocked until the evidence gates pass.",
    ]
    args.report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
