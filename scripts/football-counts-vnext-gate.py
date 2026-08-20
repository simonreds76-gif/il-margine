#!/usr/bin/env python3
"""Build the single weekly gate snapshot for football count-model experiments."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEAM_RESULTS = ROOT / "data" / "team-shots" / "team-shots-v4-fold-results.csv"
DEFAULT_TEAM_REPORT = ROOT / "data" / "team-shots" / "team-shots-v4-fold-report.md"
DEFAULT_CORNERS_RESULTS = ROOT / "data" / "corners-ou" / "corners-v3-fold-results.csv"
DEFAULT_CORNERS_REPORT = ROOT / "data" / "corners-ou" / "corners-v3-fold-report.md"
DEFAULT_TEAM_LIVE = ROOT / "data" / "football-form" / "team-shots-v4-shadow-clv.csv"
DEFAULT_CORNERS_LIVE = ROOT / "data" / "football-form" / "corners-v3-shadow-clv.csv"
DEFAULT_CANDIDATES = ROOT / "data" / "football-form" / "football-counts-vnext-candidates.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "football-counts-vnext-gate.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "football-counts-vnext-gate.md"


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(row: dict[str, str], field: str) -> float | None:
    try:
        return float(row[field])
    except (KeyError, TypeError, ValueError):
        return None


def team_count_gate(rows: list[dict[str, str]], report: str) -> bool:
    return len(rows) == 2 and "Count-distribution gate: **PASS**" in report and all(
        row.get("status") == "OK"
        and (as_float(row, "hierarchical_mle_brier") or 1.0) < (as_float(row, "fixed_alpha_025_brier") or 0.0)
        and (as_float(row, "hierarchical_mle_log_loss") or 1.0) <= (as_float(row, "fixed_alpha_025_log_loss") or 0.0)
        for row in rows
    )


def corners_count_gate(rows: list[dict[str, str]], report: str) -> bool:
    return len(rows) == 2 and "Count-model gate: **PASS**" in report and all(
        row.get("status") == "OK"
        and (as_float(row, "v3_mae") or 1.0) < (as_float(row, "baseline_mae") or 0.0)
        and (as_float(row, "v3_brier") or 1.0) < (as_float(row, "baseline_brier") or 0.0)
        and (as_float(row, "v3_log_loss") or 1.0) < (as_float(row, "baseline_log_loss") or 0.0)
        for row in rows
    )


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def live_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    active = [
        row for row in rows
        if not str(row.get("blocked_reason") or "").strip()
        and not truthy(row.get("confidence_guard_applied"))
    ]
    settled = [row for row in active if str(row.get("result") or "").strip().lower() in {"won", "lost", "push"}]
    true_close = [row for row in settled if truthy(row.get("true_close"))]
    pnl = sum(as_float(row, "pnl_units") or 0.0 for row in settled)
    clv_values = [
        value for row in true_close
        if (value := as_float(row, "published_to_close_clv")) is not None
    ]
    side_counts: dict[str, int] = {}
    for row in active:
        side = str(row.get("side") or "unknown").strip().lower()
        side_counts[side] = side_counts.get(side, 0) + 1
    dominant_side_share = max(side_counts.values(), default=0) / len(active) if active else 0.0
    return {
        "signals": len(active),
        "settled": len(settled),
        "pending": len(active) - len(settled),
        "pnl_units": round(pnl, 4),
        "roi": round(pnl / len(settled), 6) if settled else None,
        "true_close_n": len(true_close),
        "true_close_coverage": round(len(true_close) / len(settled), 6) if settled else None,
        "mean_true_close_clv": round(sum(clv_values) / len(clv_values), 6) if clv_values else None,
        "side_counts": side_counts,
        "dominant_side_share": round(dominant_side_share, 6),
    }


def candidate_diagnostics(rows: list[dict[str, str]], model: str) -> dict[str, Any]:
    model_rows = [row for row in rows if str(row.get("model") or "").strip() == model]
    fixtures = {str(row.get("match_id") or "").strip() for row in model_rows if row.get("match_id")}
    eligible = [row for row in model_rows if str(row.get("signal_status") or "").lower() == "eligible"]
    blocked = [row for row in model_rows if row not in eligible]
    blocker_rows: dict[str, int] = {}
    matchdays: list[int] = []
    warmup_only_fixtures: set[str] = set()
    all_rows_warmup_blocked = bool(blocked)
    for row in blocked:
        reasons = {
            reason.strip()
            for reason in str(row.get("blocked_reason") or "").split(";")
            if reason.strip()
        }
        if "matchdays_1_to_3" not in reasons:
            all_rows_warmup_blocked = False
        for reason in reasons:
            blocker_rows[reason] = blocker_rows.get(reason, 0) + 1
        if reasons == {"matchdays_1_to_3"}:
            warmup_only_fixtures.add(str(row.get("match_id") or "").strip())
        try:
            matchdays.append(int(float(str(row.get("matchday") or "0"))))
        except ValueError:
            pass

    matchday_max = max(matchdays) if matchdays else None
    if not model_rows:
        state = "NO_SCORED_CANDIDATES"
        explanation = "No paired current market rows reached model scoring. Check capture coverage and fixture joins."
    elif eligible:
        state = "ELIGIBLE_CANDIDATES_PRESENT"
        explanation = "At least one candidate passed every locked shadow gate."
    elif all_rows_warmup_blocked:
        state = "EXPECTED_WARMUP_BLOCK"
        explanation = "Candidates were scored, but the registered matchdays 1-3 safety lock blocked publication."
    elif matchday_max is not None and matchday_max >= 4:
        state = "NO_EDGE_AFTER_UNLOCK"
        explanation = "Current market rows were scored after the warm-up window, but no candidate passed every selection gate."
    else:
        state = "ALL_CANDIDATES_FAILED_GATES"
        explanation = "Candidates were scored, but none passed every locked selection gate."

    return {
        "state": state,
        "explanation": explanation,
        "scored_rows": len(model_rows),
        "scored_fixtures": len(fixtures),
        "eligible_rows": len(eligible),
        "eligible_fixtures": len({str(row.get("match_id") or "") for row in eligible} - {""}),
        "blocked_rows": len(blocked),
        "blocker_rows": dict(sorted(blocker_rows.items())),
        "edge_pass_but_warmup_blocked_fixtures": len(warmup_only_fixtures - {""}),
        "matchday_min": min(matchdays) if matchdays else None,
        "matchday_max": matchday_max,
        "next_unlock": "matchday_4" if state == "EXPECTED_WARMUP_BLOCK" else None,
        "operational_alert_required": False,
        "operational_alert_code": None,
    }


def reconcile_cross_model_alert(current: dict[str, Any], peer: dict[str, Any]) -> None:
    """Use the peer lane as a matchday clock when one market produces no rows."""
    peer_matchday = peer.get("matchday_max")
    if current.get("state") != "NO_SCORED_CANDIDATES" or not isinstance(peer_matchday, int) or peer_matchday < 4:
        return
    current.update(
        {
            "state": "POST_UNLOCK_NO_SCORED_CANDIDATES",
            "explanation": "The peer football-count lane reached matchday 4+, but this lane produced no scored candidates. Check current price capture and fixture joins.",
            "operational_alert_required": True,
            "operational_alert_code": "POST_UNLOCK_NO_SCORED_CANDIDATES",
        }
    )


def build_payload(
    team_rows: list[dict[str, str]],
    team_report: str,
    corners_rows: list[dict[str, str]],
    corners_report: str,
    team_live_rows: list[dict[str, str]] | None = None,
    corners_live_rows: list[dict[str, str]] | None = None,
    candidate_rows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    team_pass = team_count_gate(team_rows, team_report)
    corners_pass = corners_count_gate(corners_rows, corners_report)
    team_live = live_summary(team_live_rows or [])
    corners_live = live_summary(corners_live_rows or [])
    candidates = candidate_rows or []
    team_scan = candidate_diagnostics(candidates, "team_shots_v4")
    corners_scan = candidate_diagnostics(candidates, "corners_v3")
    reconcile_cross_model_alert(team_scan, corners_scan)
    reconcile_cross_model_alert(corners_scan, team_scan)
    team_close_coverage = team_live["true_close_coverage"]
    team_mean_clv = team_live["mean_true_close_clv"]
    team_roi = team_live["roi"]
    corners_close_coverage = corners_live["true_close_coverage"]
    corners_mean_clv = corners_live["mean_true_close_clv"]
    team_promotable = (
        team_live["settled"] >= 150
        and team_close_coverage is not None
        and team_close_coverage >= 0.70
        and team_mean_clv is not None
        and team_mean_clv >= 0.005
        and team_roi is not None
        and team_roi > 0.0
    )
    corners_promotable = (
        corners_live["settled"] >= 100
        and corners_close_coverage is not None
        and corners_close_coverage >= 0.50
        and corners_mean_clv is not None
        and corners_mean_clv >= 0.0
        and corners_live["dominant_side_share"] <= 0.80
    )
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "team_shots_v4": {
            "count_gate": "PASS" if team_pass else "FAIL",
            "prospective_status": "AUTHORIZED_SHADOW" if team_pass else "BLOCKED",
            "market_gate": "BLOCKED_PENDING_2026_27_TRUE_CLOSE_SAMPLE",
            "live_routing": False,
            "prospective": team_live,
            "latest_scan": team_scan,
            "promotion_gate": "PASS" if team_promotable else "BLOCKED",
        },
        "corners_v3": {
            "count_gate": "PASS" if corners_pass else "FAIL",
            "prospective_status": "AUTHORIZED_SHADOW" if corners_pass else "BLOCKED",
            "market_gate": "BLOCKED_PENDING_2026_27_PINNACLE_SAMPLE",
            "live_routing": False,
            "prospective": corners_live,
            "latest_scan": corners_scan,
            "promotion_gate": "PASS" if corners_promotable else "BLOCKED",
        },
    }


def render(payload: dict[str, Any]) -> str:
    team = payload["team_shots_v4"]
    corners = payload["corners_v3"]
    return "\n".join(
        [
            "# Football Counts vNext Gate",
            "",
            f"- Generated: {payload['generated_at']}",
            "- This snapshot cannot promote or route bets.",
            "",
            "## Team Shots v4",
            f"- Count gate: **{team['count_gate']}**",
            f"- Prospective status: **{team['prospective_status']}**",
            f"- Market gate: **{team['market_gate']}**",
            f"- Promotion gate: **{team['promotion_gate']}**",
            f"- Prospective signals: {team['prospective']['signals']} ({team['prospective']['settled']} settled / {team['prospective']['pending']} pending)",
            f"- Latest scan: **{team['latest_scan']['state']}**; {team['latest_scan']['scored_rows']} rows / {team['latest_scan']['scored_fixtures']} fixtures scored; {team['latest_scan']['edge_pass_but_warmup_blocked_fixtures']} fixtures passed edge but were held only by the warm-up lock.",
            f"- Blockers: {team['latest_scan']['blocker_rows'] or '-'}",
            f"- P/L / ROI: {team['prospective']['pnl_units']:+.2f}u / {team['prospective']['roi']:+.1%}" if team['prospective']['roi'] is not None else "- P/L / ROI: -",
            f"- True-close coverage: {team['prospective']['true_close_n']}/{team['prospective']['settled']} ({team['prospective']['true_close_coverage']:.1%})" if team['prospective']['true_close_coverage'] is not None else "- True-close coverage: -",
            f"- Mean true-close CLV: {team['prospective']['mean_true_close_clv']:+.2%}" if team['prospective']['mean_true_close_clv'] is not None else "- Mean true-close CLV: -",
            "- Live routing: unchanged / disabled",
            "",
            "## Corners v3",
            f"- Count gate: **{corners['count_gate']}**",
            f"- Prospective status: **{corners['prospective_status']}**",
            f"- Market gate: **{corners['market_gate']}**",
            f"- Promotion gate: **{corners['promotion_gate']}**",
            f"- Prospective signals: {corners['prospective']['signals']} ({corners['prospective']['settled']} settled / {corners['prospective']['pending']} pending)",
            f"- Latest scan: **{corners['latest_scan']['state']}**; {corners['latest_scan']['scored_rows']} rows / {corners['latest_scan']['scored_fixtures']} fixtures scored; {corners['latest_scan']['edge_pass_but_warmup_blocked_fixtures']} fixtures passed edge but were held only by the warm-up lock.",
            f"- Blockers: {corners['latest_scan']['blocker_rows'] or '-'}",
            f"- P/L / ROI: {corners['prospective']['pnl_units']:+.2f}u / {corners['prospective']['roi']:+.1%}" if corners['prospective']['roi'] is not None else "- P/L / ROI: -",
            f"- True-close coverage: {corners['prospective']['true_close_n']}/{corners['prospective']['settled']} ({corners['prospective']['true_close_coverage']:.1%})" if corners['prospective']['true_close_coverage'] is not None else "- True-close coverage: -",
            f"- Mean true-close CLV: {corners['prospective']['mean_true_close_clv']:+.2%}" if corners['prospective']['mean_true_close_clv'] is not None else "- Mean true-close CLV: -",
            f"- Side mix: {corners['prospective']['side_counts'] or '-'} (dominant {corners['prospective']['dominant_side_share']:.1%})",
            "- Live routing: unchanged / disabled",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-results", type=Path, default=DEFAULT_TEAM_RESULTS)
    parser.add_argument("--team-report", type=Path, default=DEFAULT_TEAM_REPORT)
    parser.add_argument("--corners-results", type=Path, default=DEFAULT_CORNERS_RESULTS)
    parser.add_argument("--corners-report", type=Path, default=DEFAULT_CORNERS_REPORT)
    parser.add_argument("--team-live", type=Path, default=DEFAULT_TEAM_LIVE)
    parser.add_argument("--corners-live", type=Path, default=DEFAULT_CORNERS_LIVE)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    payload = build_payload(
        load_csv(args.team_results),
        args.team_report.read_text(encoding="utf-8") if args.team_report.exists() else "",
        load_csv(args.corners_results),
        args.corners_report.read_text(encoding="utf-8") if args.corners_report.exists() else "",
        load_csv(args.team_live),
        load_csv(args.corners_live),
        load_csv(args.candidates),
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render(payload), encoding="utf-8")
    print(f"Wrote {args.json.relative_to(ROOT)}")
    print(f"Wrote {args.report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
