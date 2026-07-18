#!/usr/bin/env python3
"""Audit ATP fair-odds guards without changing live routing.

The historical replay uses the identity-clean backtest result CSVs. It measures
moneyline guards that can be reconstructed exactly from those files and lists
the remaining model/spread/operational guards as separate evidence classes.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = [ROOT / "data" / "backtest" / f"backtest-results-{year}.csv" for year in range(2022, 2026)]
DEFAULT_JSON = ROOT / "data" / "backtest" / "tennis-guard-audit.json"
DEFAULT_REPORT = ROOT / "data" / "backtest" / "tennis-guard-audit-report.txt"

MODEL_FAV_ODDS_MIN = 1.25
MARKET_FAV_ODDS_MIN = 1.25
MODEL_MARKET_GAP_MAX = 0.10
SIDE_FLIP_BUFFER = 0.03
ATP500_HARD_SHORT_FAV_MAX_ODDS = 1.80
HEAVY_FAV_DOG_MIN_PROB = 0.74

GUARD_ORDER = (
    "model_favourite_below_1_25",
    "market_favourite_below_1_25",
    "model_market_side_flip",
    "model_market_gap_above_10pp",
    "atp500_hard_short_favourite",
    "masters_hard_heavy_favourite_dog",
)


@dataclass(frozen=True)
class BetRow:
    year: int
    surface: str
    series: str
    confidence: str
    value_pct: float
    selected_side: str
    selected_odds: float
    pnl_units: float
    model_winner_prob: float
    market_winner_prob: float
    model_favourite_prob: float
    market_favourite_prob: float
    model_favourite_odds: float
    market_favourite_odds: float
    model_favourite_side: str
    market_favourite_side: str


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def parse_row(raw: dict[str, str]) -> BetRow | None:
    if str(raw.get("has_pinnacle_odds", "")).strip().lower() not in {"true", "1", "yes"}:
        return None
    date_text = str(raw.get("date") or "")
    try:
        year = int(date_text[:4])
    except ValueError:
        return None

    model_winner_prob = _float(raw.get("our_prob"), -1.0)
    market_winner_prob = _float(raw.get("pinnacle_prob_novig"), -1.0)
    winner_odds = _float(raw.get("pinnacle_odds"), 0.0)
    loser_odds = _float(raw.get("pinnacle_odds_loser"), 0.0)
    if not (0 < model_winner_prob < 1 and 0 < market_winner_prob < 1 and winner_odds > 1 and loser_odds > 1):
        return None

    selected_side = str(raw.get("bet_side") or "").strip().lower()
    if selected_side not in {"winner", "loser"}:
        return None
    selected_odds = winner_odds if selected_side == "winner" else loser_odds
    pnl_units = selected_odds - 1.0 if selected_side == "winner" else -1.0
    model_favourite_prob = max(model_winner_prob, 1.0 - model_winner_prob)
    market_favourite_prob = max(market_winner_prob, 1.0 - market_winner_prob)

    return BetRow(
        year=year,
        surface=str(raw.get("surface") or "").strip().title(),
        series=str(raw.get("series") or "").strip(),
        confidence=str(raw.get("confidence") or "").strip().lower(),
        value_pct=_float(raw.get("value_pct"), -999.0),
        selected_side=selected_side,
        selected_odds=selected_odds,
        pnl_units=pnl_units,
        model_winner_prob=model_winner_prob,
        market_winner_prob=market_winner_prob,
        model_favourite_prob=model_favourite_prob,
        market_favourite_prob=market_favourite_prob,
        model_favourite_odds=1.0 / model_favourite_prob,
        market_favourite_odds=min(winner_odds, loser_odds),
        model_favourite_side="winner" if model_winner_prob >= 0.5 else "loser",
        market_favourite_side="winner" if market_winner_prob >= 0.5 else "loser",
    )


def guard_flags(row: BetRow) -> dict[str, bool]:
    side_flip = (
        row.model_favourite_side != row.market_favourite_side
        and abs(row.model_winner_prob - 0.5) >= SIDE_FLIP_BUFFER
        and abs(row.market_winner_prob - 0.5) >= SIDE_FLIP_BUFFER
    )
    return {
        "model_favourite_below_1_25": row.model_favourite_odds < MODEL_FAV_ODDS_MIN,
        "market_favourite_below_1_25": row.market_favourite_odds < MARKET_FAV_ODDS_MIN,
        "model_market_side_flip": side_flip,
        # Live code treats a side flip as part of the composite gap exclusion.
        # Keep the magnitude threshold separate here so overlap is measurable.
        "model_market_gap_above_10pp": abs(row.model_favourite_prob - row.market_favourite_prob) > MODEL_MARKET_GAP_MAX,
        "atp500_hard_short_favourite": (
            row.surface == "Hard"
            and row.series == "ATP500"
            and row.confidence == "high"
            and row.model_favourite_odds < ATP500_HARD_SHORT_FAV_MAX_ODDS
        ),
        "masters_hard_heavy_favourite_dog": (
            row.surface == "Hard"
            and row.series == "Masters 1000"
            and row.selected_side != row.model_favourite_side
            and row.model_favourite_prob >= HEAVY_FAV_DOG_MIN_PROB
        ),
    }


def _strict_candidate(row: BetRow) -> bool:
    return row.surface == "Hard" and row.series == "Masters 1000" and row.confidence == "high" and row.value_pct >= 10.0


VOLUME_200_RULES = (
    ("Hard", "Masters 1000", {"high"}, 15.0),
    ("Hard", "Masters 1000", {"medium"}, 30.0),
    ("Hard", "Grand Slam", {"high", "medium"}, 5.0),
    ("Hard", "ATP500", {"high", "medium"}, 10.0),
    ("Clay", "ATP500", {"high", "medium"}, 10.0),
)


def _volume_200_candidate(row: BetRow) -> bool:
    return any(
        row.surface == surface
        and row.series == series
        and row.confidence in confidence
        and row.value_pct >= min_value
        for surface, series, confidence, min_value in VOLUME_200_RULES
    )


PROFILES: dict[str, tuple[str, Callable[[BetRow], bool]]] = {
    "broad_value_10": ("All ATP rows with model value >=10%", lambda row: row.value_pct >= 10.0),
    "strict": ("Hard | Masters 1000 | high confidence | value >=10%", _strict_candidate),
    "volume_200_policy": ("All rows matching the registered Volume 200 segment thresholds", _volume_200_candidate),
}


def metrics(rows: Iterable[BetRow]) -> dict[str, Any]:
    selected = list(rows)
    pnl = sum(row.pnl_units for row in selected)
    wins = sum(1 for row in selected if row.pnl_units > 0)
    count = len(selected)
    return {
        "bets": count,
        "wins": wins,
        "losses": count - wins,
        "pnl_units": round(pnl, 3),
        "roi_pct": round(pnl / count * 100.0, 3) if count else None,
        "win_rate_pct": round(wins / count * 100.0, 3) if count else None,
        "avg_odds": round(sum(row.selected_odds for row in selected) / count, 3) if count else None,
    }


def _roi(rows: Iterable[BetRow]) -> float | None:
    result = metrics(rows)
    return result["roi_pct"]


def audit_profile(rows: list[BetRow], predicate: Callable[[BetRow], bool]) -> dict[str, Any]:
    candidates = [row for row in rows if predicate(row)]
    flags_by_row = [guard_flags(row) for row in candidates]
    survivors = [row for row, flags in zip(candidates, flags_by_row) if not any(flags.values())]
    first_hit_counts: Counter[str] = Counter()
    overlaps: Counter[str] = Counter()

    for flags in flags_by_row:
        hit = [name for name in GUARD_ORDER if flags[name]]
        if hit:
            first_hit_counts[hit[0]] += 1
        for index, left in enumerate(hit):
            for right in hit[index + 1 :]:
                overlaps[f"{left}|{right}"] += 1

    guard_rows: dict[str, Any] = {}
    for name in GUARD_ORDER:
        flagged = [row for row, flags in zip(candidates, flags_by_row) if flags[name]]
        unique = [
            row
            for row, flags in zip(candidates, flags_by_row)
            if flags[name] and sum(1 for value in flags.values() if value) == 1
        ]
        marginal = [
            row
            for row, flags in zip(candidates, flags_by_row)
            if flags[name] and not any(value for other, value in flags.items() if other != name)
        ]
        without_this_guard = [
            row
            for row, flags in zip(candidates, flags_by_row)
            if not any(value for other, value in flags.items() if other != name)
        ]
        guard_rows[name] = {
            "flagged": metrics(flagged),
            "unique": metrics(unique),
            "marginal_removed": metrics(marginal),
            "survivors_without_this_guard": metrics(without_this_guard),
            "first_hit_bets": first_hit_counts[name],
            "surface": {
                surface: metrics(row for row in flagged if row.surface == surface)
                for surface in ("Hard", "Clay", "Grass")
            },
            "year": {str(year): metrics(row for row in flagged if row.year == year) for year in range(2022, 2026)},
        }

    return {
        "before_guards": metrics(candidates),
        "after_all_replayable_guards": metrics(survivors),
        "blocked_by_any": metrics(
            row for row, flags in zip(candidates, flags_by_row) if any(flags.values())
        ),
        "guards": guard_rows,
        "overlap_counts": dict(sorted(overlaps.items(), key=lambda item: (-item[1], item[0]))),
    }


def evidence_inventory() -> dict[str, list[dict[str, str]]]:
    return {
        "replayable_ml_guards": [
            {
                "id": "model_favourite_below_1_25",
                "live_scope": "ML all ATP lanes",
                "evidence": "2022-2025 A/B report; improved every reported surface and series",
                "decision": "KEEP",
            },
            {
                "id": "market_favourite_below_1_25",
                "live_scope": "ML all ATP lanes",
                "evidence": "No independent registered A/B found; overlaps model/gap guards",
                "decision": "REVIEW_REDUNDANCY",
            },
            {
                "id": "model_market_side_flip",
                "live_scope": "ML all ATP lanes; folded into the 10pp composite guard",
                "evidence": "Added after mismatch incidents, not a registered threshold test; no frozen prospective promotion proof",
                "decision": "SHADOW_SEPARATELY",
            },
            {
                "id": "model_market_gap_above_10pp",
                "live_scope": "ML all ATP lanes",
                "evidence": "Introduced 2026-04-24 after mismatch incidents; no threshold sweep, and blocked historical bets are not uniformly bad",
                "decision": "REVIEW_BY_SURFACE_PROFILE",
            },
            {
                "id": "atp500_hard_short_favourite",
                "live_scope": "ATP500 Hard high-confidence ML; outside current strict Masters segment",
                "evidence": "Locked policy A/B improved pooled ROI but remained negative overall",
                "decision": "KEEP_AS_PROFILE_FILTER",
            },
            {
                "id": "masters_hard_heavy_favourite_dog",
                "live_scope": "Strict Masters Hard dog ML only, model favourite >=74%",
                "evidence": "Narrow retrospective tail; needs prospective isolated tracking",
                "decision": "KEEP_AND_TRACK_PROSPECTIVELY",
            },
        ],
        "spread_and_cross_market_guards": [
            {
                "id": "point_probability_shape_within_8pp",
                "live_scope": "Trusted handicap display/signal eligibility",
                "evidence": "Not reconstructable from ML result CSVs; stored point probabilities require dedicated spread replay",
                "decision": "PROSPECTIVE_ONLY",
            },
            {
                "id": "extreme_favourite_plus_games_dog_spread",
                "live_scope": "Plus-games dog spreads when model or market favourite <1.25",
                "evidence": "Logic-derived proxy; no independent registered A/B found",
                "decision": "REVIEW_WITH_REAL_SPREAD_ODDS",
            },
            {
                "id": "same_match_favourite_handicap_conflict",
                "live_scope": "Strict dog ML vetoed by >=20% model-favourite handicap edge",
                "evidence": "Cross-market consistency rule; historical ML files do not preserve candidate spread state",
                "decision": "TRACK_CONFLICT_OUTCOMES",
            },
            {
                "id": "opposite_side_handicap_conflict",
                "live_scope": "ML side vetoed by opposite handicap edge >=20%",
                "evidence": "API/report parity repaired; historical ML files do not preserve candidate spread state",
                "decision": "TRACK_CONFLICT_OUTCOMES",
            },
            {
                "id": "spread_v1_line_shape",
                "live_scope": "Spread v1 favourite handicaps only, absolute line 2.0 to 3.5",
                "evidence": "Segment rule from the 2026-04-24 live audit; needs a larger real-price sample",
                "decision": "KEEP_AS_PROFILE_FILTER",
            },
            {
                "id": "spread_v1_edge_band",
                "live_scope": "Spread v1 edge 10% to 18%",
                "evidence": "Fixed shadow-profile band; values outside it remain non-actionable",
                "decision": "STRATEGY_DEFINITION",
            },
            {
                "id": "clay_bo3_handicap_edge_band",
                "live_scope": "Clay bo3 dog handicap edge 6% to 25%",
                "evidence": "Shadow profile boundary; not a general spread safety rule",
                "decision": "STRATEGY_DEFINITION",
            },
            {
                "id": "clay_ml_opposite_spread_suppression",
                "live_scope": "Clay ML display when Spread v1 points to the other player at a near-pick line",
                "evidence": "Cross-lane consistency filter; blocked candidates are not yet persisted for settlement",
                "decision": "TRACK_CONFLICT_OUTCOMES",
            },
        ],
        "model_probability_modifiers": [
            {"id": "elo_magnitude", "decision": "ABLATION_REQUIRED", "evidence": "Embedded before calibration"},
            {"id": "surface_rank_conflict", "decision": "ABLATION_REQUIRED", "evidence": "Embedded before calibration"},
            {"id": "surface_points_mismatch", "decision": "ABLATION_REQUIRED", "evidence": "Embedded before calibration"},
            {"id": "series_probability", "decision": "ABLATION_REQUIRED", "evidence": "Embedded after calibration"},
            {"id": "low_confidence_dog", "decision": "ABLATION_REQUIRED", "evidence": "Embedded probability adjustment"},
            {"id": "stepup_dog", "decision": "ABLATION_REQUIRED", "evidence": "Embedded probability adjustment"},
            {"id": "class_gap", "decision": "ABLATION_REQUIRED", "evidence": "Rank/Elo mismatch correction embedded in final probability"},
            {"id": "probability_delta_caps", "decision": "KEEP_SAFETY_CAP", "evidence": "Bounds component and final adjustments; calibration impact still needs attribution"},
            {"id": "hard_overlay_favourite_cap", "decision": "KEEP_SAFETY_CAP", "evidence": "Caps hard-overlay favourite probabilities by series/confidence; only relevant when the hard overlay is enabled"},
        ],
        "strategy_and_operational_filters": [
            {"id": "strict_segment_confidence_value", "decision": "STRATEGY_DEFINITION", "evidence": "Hard Masters/high/>=10%; not a model guard"},
            {"id": "volume_200_segment_thresholds", "decision": "STRATEGY_DEFINITION", "evidence": "Registered profile rules; not a model guard"},
            {"id": "challenger_research_lane_disabled", "decision": "PRODUCT_STATUS", "evidence": "High coverage/high confidence/10-15% edge still lacks mature ROI and CLV proof"},
            {"id": "clay_bo3_profile", "decision": "SHADOW_ONLY", "evidence": "High confidence, 5-13% ML; dog handicap 6-25%; ML routing disabled by default"},
            {"id": "grass_bo3_profile", "decision": "SHADOW_ONLY", "evidence": "ATP250/500, 10-30%, favourite agreement, lagged CPI required; missing and slow CPI blocked"},
            {"id": "cpi_speed_identity_gate", "decision": "PAUSED", "evidence": "Requires PASS_SHADOW and idclean_v1; current historical identity evidence invalid"},
            {"id": "injury_overlay", "decision": "OFF", "evidence": "Disabled pending validation"},
            {"id": "tournament_overlay", "decision": "OFF", "evidence": "Disabled by default; when enabled it also requires a matched segment, minimum n and minimum shrunk ROI"},
            {"id": "missing_or_invalid_pinnacle_odds", "decision": "KEEP", "evidence": "Cannot calculate takeable EV without a matched two-way market"},
            {"id": "ambiguous_player_pairing", "decision": "KEEP", "evidence": "Fail-closed identity protection against wrong-opponent prices"},
            {"id": "stale_schedule_and_pairing_suppression", "decision": "KEEP", "evidence": "Data-integrity guard, not an edge filter"},
        ],
    }


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "TENNIS FAIR-ODDS GUARD AUDIT",
        f"Generated: {payload['generated_at']}",
        f"Historical rows loaded: {payload['rows_loaded']}",
        "",
        "METHOD",
        "- Replays reconstructable ML guards on identity-clean ATP 2022-2025 result rows.",
        "- Blocked ROI is descriptive, not proof that a guard should be inverted or removed.",
        "- Unique/marginal rows prevent overlapping guards from claiming the same result twice.",
        "- Spread conflicts and embedded probability modifiers require separate prospective/ablation evidence.",
        "",
    ]
    for profile_name, profile in payload["profiles"].items():
        before = profile["before_guards"]
        after = profile["after_all_replayable_guards"]
        blocked = profile["blocked_by_any"]
        lines.extend(
            [
                f"PROFILE {profile_name}",
                f"  {payload['profile_descriptions'][profile_name]}",
                f"  Before: n={before['bets']} ROI={before['roi_pct']}% P/L={before['pnl_units']:+.3f}u",
                f"  After all replayable guards: n={after['bets']} ROI={after['roi_pct']}% P/L={after['pnl_units']:+.3f}u",
                f"  Blocked: n={blocked['bets']} ROI={blocked['roi_pct']}% P/L={blocked['pnl_units']:+.3f}u",
                "  Guard attribution:",
            ]
        )
        for guard_name in GUARD_ORDER:
            entry = profile["guards"][guard_name]
            flagged = entry["flagged"]
            unique = entry["unique"]
            lines.append(
                f"    {guard_name}: flagged={flagged['bets']} ROI={flagged['roi_pct']}% | "
                f"unique={unique['bets']} ROI={unique['roi_pct']}% | first_hit={entry['first_hit_bets']}"
            )
        lines.append("")

    lines.append("DECISION INVENTORY")
    for category, entries in payload["inventory"].items():
        lines.append(f"  {category}")
        for entry in entries:
            lines.append(f"    {entry['id']}: {entry['decision']} - {entry['evidence']}")
    lines.extend(
        [
            "",
            "CURRENT CONCLUSION",
            "- Keep the model-favourite <1.25 protection; it has the strongest documented A/B evidence.",
            "- Do not treat the blanket 10pp gap or side-flip veto as validated edge protection. Keep collecting them as isolated shadow cohorts.",
            "- Do not remove cross-market guards from an ML-only replay; first persist and settle their blocked candidates.",
            "- Embedded probability modifiers need controlled model ablations, not a routing-guard ROI table.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", type=Path, default=DEFAULT_FILES)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    rows: list[BetRow] = []
    source_counts: dict[str, int] = {}
    for input_path in args.files:
        path = input_path if input_path.is_absolute() else ROOT / input_path
        if not path.exists():
            continue
        loaded = 0
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                parsed = parse_row(raw)
                if parsed is not None:
                    rows.append(parsed)
                    loaded += 1
        source_counts[str(path.relative_to(ROOT))] = loaded
    if not rows:
        raise SystemExit("No usable historical rows loaded")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "AUDIT_ONLY_NO_LIVE_CHANGE",
        "rows_loaded": len(rows),
        "source_counts": source_counts,
        "constants": {
            "model_favourite_odds_min": MODEL_FAV_ODDS_MIN,
            "market_favourite_odds_min": MARKET_FAV_ODDS_MIN,
            "model_market_gap_max_pp": MODEL_MARKET_GAP_MAX * 100.0,
            "side_flip_buffer_pp": SIDE_FLIP_BUFFER * 100.0,
            "atp500_hard_short_favourite_max_odds": ATP500_HARD_SHORT_FAV_MAX_ODDS,
            "heavy_favourite_dog_min_prob": HEAVY_FAV_DOG_MIN_PROB,
        },
        "profile_descriptions": {name: description for name, (description, _) in PROFILES.items()},
        "profiles": {name: audit_profile(rows, predicate) for name, (_, predicate) in PROFILES.items()},
        "inventory": evidence_inventory(),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.report_out.write_text(render_report(payload), encoding="utf-8")
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
