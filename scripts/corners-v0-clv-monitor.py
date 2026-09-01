#!/usr/bin/env python3
"""Join corners v0 research picks to Pinnacle prices for CLV monitoring.

The script is deliberately lane-agnostic: it can run before there are any
published v0 picks and will still write the expected schema. Once picks exist,
it records publication price, 3h/1h reference prices, close, CLV, and whether
the hard canonical-only guard would have blocked the pick.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from clv_snapshot_utils import close_lag_minutes, is_true_close, snapshot_at_or_before, snapshot_price


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PICKS = ROOT / "data" / "football-form" / "corners-v0-published-picks.csv"
DEFAULT_PINNACLE = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"
DEFAULT_OUTPUT = ROOT / "data" / "football-form" / "corners-v0-clv-monitor.csv"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "corners-v0-clv-monitor.md"
DEFAULT_ALLOWED_CONFIG = ROOT / "data" / "football-form" / "corners-v0-allowed-leagues.json"

OUTPUT_FIELDS = [
    "pick_id",
    "published_at_utc",
    "kickoff_utc",
    "time_to_kickoff_hours",
    "match_id",
    "match_date",
    "league",
    "match",
    "home_team",
    "away_team",
    "selection",
    "line",
    "side",
    "model",
    "model_fair_odds",
    "model_implied_prob",
    "raw_model_probability",
    "market_fair_probability",
    "model_market_gap",
    "edge",
    "matchday",
    "team_neff",
    "opponent_neff",
    "model_mean",
    "distribution_parameter",
    "signal_status",
    "pinnacle_price_at_publication",
    "pinnacle_price_3h_pre_kickoff",
    "pinnacle_price_1h_pre_kickoff",
    "pinnacle_price_close",
    "close_lag_minutes",
    "true_close",
    "published_to_close_clv",
    "model_to_close_clv",
    "pinnacle_movement_to_close",
    "result",
    "pnl_units",
    "actual_total_corners",
    "settled_at",
    "current_model_would_have_priced",
    "confidence_guard_applied",
    "blocked_reason",
]

SETTLED_RESULTS = {"won", "lost", "push"}
SETTLEMENT_FIELDS = ("result", "pnl_units", "actual_total_corners", "settled_at")


def norm_team(text: str) -> str:
    text = (text or "").strip().lower().replace("(corners)", "")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def parse_dt(text: Any) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pf(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def load_existing_settlements(path: Path) -> dict[str, dict[str, str]]:
    rows = load_csv(path)
    settlements: dict[str, dict[str, str]] = {}
    for row in rows:
        pick_id = str(row.get("pick_id") or "").strip()
        result = str(row.get("result") or "").strip().lower()
        if pick_id and result in SETTLED_RESULTS:
            settlements[pick_id] = row
    return settlements


def preserve_settlement(row: dict[str, Any], existing: dict[str, dict[str, str]]) -> dict[str, Any]:
    prior = existing.get(str(row.get("pick_id") or "").strip())
    if not prior:
        return row
    for field in SETTLEMENT_FIELDS:
        if field in prior:
            row[field] = prior.get(field, "")
    return row


def split_match(row: dict[str, str]) -> tuple[str, str]:
    home = row.get("home_team", "").strip()
    away = row.get("away_team", "").strip()
    if home and away:
        return home, away
    match = row.get("match", "")
    if " vs " in match:
        left, right = match.split(" vs ", 1)
        return left.strip(), right.strip()
    if " v " in match:
        left, right = match.split(" v ", 1)
        return left.strip(), right.strip()
    return home, away


def line_label(value: Any) -> str:
    parsed = pf(value)
    if parsed is None:
        return str(value or "").strip()
    return f"{parsed:.1f}"


def build_pinnacle_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        home = norm_team(row.get("home_team", ""))
        away = norm_team(row.get("away_team", ""))
        match_date = (row.get("match_date") or row.get("kickoff_iso") or "").strip()[:10]
        side = (row.get("side") or "").strip().lower()
        line = line_label(row.get("line"))
        odds = pf(row.get("odds_decimal"))
        captured_at = parse_dt(row.get("captured_at"))
        kickoff = parse_dt(row.get("kickoff_iso"))
        if not (home and away and match_date and side and line and odds and captured_at):
            continue
        item = {"captured_at": captured_at, "kickoff": kickoff, "odds": odds}
        index[f"{match_date}|{home}|{away}|{line}|{side}"].append(item)
        index[f"__any__|{home}|{away}|{line}|{side}"].append(item)
    for items in index.values():
        items.sort(key=lambda item: item["captured_at"])
    return index


def price_at_or_before(items: list[dict[str, Any]], target: datetime | None) -> float | None:
    return snapshot_price(snapshot_at_or_before(items, target))


def row_bool(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def load_allowed_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "allowed_leagues": [],
            "canonical_only_allowed": False,
            "config_valid": False,
            "config_error": f"missing allowed config: {path}",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "allowed_leagues": [],
            "canonical_only_allowed": False,
            "config_valid": False,
            "config_error": f"malformed allowed config: {exc}",
        }
    if not isinstance(payload.get("allowed_leagues"), list):
        return {
            "allowed_leagues": [],
            "canonical_only_allowed": False,
            "config_valid": False,
            "config_error": "allowed config missing list field: allowed_leagues",
        }
    payload["config_valid"] = True
    payload["config_error"] = ""
    return payload


def build_pick_row(
    pick: dict[str, str],
    index: dict[str, list[dict[str, Any]]],
    *,
    allow_canonical_only: bool,
    allowed_leagues: set[str],
    config_valid: bool,
    config_error: str,
) -> dict[str, Any]:
    home, away = split_match(pick)
    league = (pick.get("league") or "").strip().lower()
    match_date = (pick.get("match_date") or pick.get("kickoff_utc") or pick.get("kick_off") or "").strip()[:10]
    line = line_label(pick.get("line"))
    side = (pick.get("side") or "").strip().lower()
    published = parse_dt(pick.get("published_at_utc") or pick.get("published_at") or pick.get("logged_at"))
    kickoff = parse_dt(pick.get("kickoff_utc") or pick.get("kick_off") or pick.get("kickoff_iso"))
    key = f"{match_date}|{norm_team(home)}|{norm_team(away)}|{line}|{side}"
    items = index.get(key) or index.get(f"__any__|{norm_team(home)}|{norm_team(away)}|{line}|{side}") or []

    price_publication = price_at_or_before(items, published)
    price_3h = price_at_or_before(items, kickoff - timedelta(hours=3) if kickoff else None)
    price_1h = price_at_or_before(items, kickoff - timedelta(hours=1) if kickoff else None)
    close_snapshot = snapshot_at_or_before(items, kickoff)
    close = snapshot_price(close_snapshot)
    close_lag = close_lag_minutes(close_snapshot, kickoff)
    model_fair = pf(pick.get("model_fair_odds") or pick.get("model_fair"))
    model_prob = pf(pick.get("model_implied_prob") or pick.get("model_prob"))
    if model_prob is None and model_fair and model_fair > 1:
        model_prob = 1.0 / model_fair
    current_model_would_have_priced = row_bool(pick.get("current_model_would_have_priced"))
    blocked_reasons: list[str] = []
    confidence_guard_applied = False
    if not config_valid:
        confidence_guard_applied = True
        blocked_reasons.append("allowed_config_invalid")
    if not current_model_would_have_priced and not allow_canonical_only:
        confidence_guard_applied = True
        blocked_reasons.append("canonical_only_guard")
    if league not in allowed_leagues:
        confidence_guard_applied = True
        blocked_reasons.append("league_not_allowed")
    if config_error:
        blocked_reasons.append(config_error)

    published_to_close_clv = ""
    movement_to_close = ""
    if price_publication and close:
        published_to_close_clv = round((price_publication / close) - 1.0, 6)
        movement_to_close = round(close - price_publication, 6)

    model_to_close_clv = ""
    if model_prob and close:
        model_to_close_clv = round((model_prob * close) - 1.0, 6)
    time_to_kickoff_hours = ""
    if published and kickoff:
        time_to_kickoff_hours = round((kickoff - published).total_seconds() / 3600.0, 3)

    match = pick.get("match") or f"{home} vs {away}"
    return {
        "pick_id": pick.get("pick_id") or "|".join([league, match_date, norm_team(home), norm_team(away), line, side]),
        "published_at_utc": fmt_dt(published),
        "kickoff_utc": fmt_dt(kickoff),
        "time_to_kickoff_hours": time_to_kickoff_hours,
        "match_id": pick.get("match_id") or "|".join([league, match_date, norm_team(home), norm_team(away)]),
        "match_date": match_date,
        "league": league,
        "match": match,
        "home_team": home,
        "away_team": away,
        "selection": pick.get("selection") or f"{side} {line}",
        "line": line,
        "side": side,
        "model": pick.get("model", ""),
        "model_fair_odds": round(model_fair, 6) if model_fair else "",
        "model_implied_prob": round(model_prob, 6) if model_prob else "",
        "raw_model_probability": pick.get("raw_model_probability", ""),
        "market_fair_probability": pick.get("market_fair_probability", ""),
        "model_market_gap": pick.get("model_market_gap", ""),
        "edge": pick.get("edge", ""),
        "matchday": pick.get("matchday", ""),
        "team_neff": pick.get("team_neff", ""),
        "opponent_neff": pick.get("opponent_neff", ""),
        "distribution_parameter": pick.get("distribution_parameter", ""),
        "signal_status": pick.get("signal_status", ""),
        "pinnacle_price_at_publication": round(price_publication, 6) if price_publication else "",
        "pinnacle_price_3h_pre_kickoff": round(price_3h, 6) if price_3h else "",
        "pinnacle_price_1h_pre_kickoff": round(price_1h, 6) if price_1h else "",
        "pinnacle_price_close": round(close, 6) if close else "",
        "close_lag_minutes": close_lag if close_lag is not None else "",
        "true_close": "true" if is_true_close(close_lag) else "false",
        "published_to_close_clv": published_to_close_clv,
        "model_to_close_clv": model_to_close_clv,
        "pinnacle_movement_to_close": movement_to_close,
        "result": pick.get("result", "") or "pending",
        "pnl_units": pick.get("pnl_units", ""),
        "actual_total_corners": pick.get("actual_total_corners", ""),
        "settled_at": pick.get("settled_at", ""),
        "current_model_would_have_priced": "true" if current_model_would_have_priced else "false",
        "confidence_guard_applied": "true" if confidence_guard_applied else "false",
        "blocked_reason": ";".join(blocked_reasons),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else ROOT / path
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def avg(values: list[float]) -> float | None:
    vals = [value for value in values if value == value]
    return sum(vals) / len(vals) if vals else None


def is_active_pick(row: dict[str, Any]) -> bool:
    return not str(row.get("blocked_reason") or "").strip() and not row_bool(row.get("confidence_guard_applied"))


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value:+.2f}%"


def segment_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in rows if is_active_pick(row)]
    settled = [row for row in active if str(row.get("result") or "").strip().lower() in SETTLED_RESULTS]
    pending = [row for row in active if str(row.get("result") or "").strip().lower() in {"", "pending"}]
    won = sum(1 for row in settled if str(row.get("result") or "").strip().lower() == "won")
    lost = sum(1 for row in settled if str(row.get("result") or "").strip().lower() == "lost")
    pushed = sum(1 for row in settled if str(row.get("result") or "").strip().lower() == "push")
    pnl = sum(value for value in (pf(row.get("pnl_units")) for row in settled) if value is not None)
    clv_values = [value for value in (pf(row.get("published_to_close_clv")) for row in settled) if value is not None]
    roi = (pnl / len(settled) * 100.0) if settled else None
    avg_clv = avg(clv_values)
    return {
        "active": len(active),
        "settled": len(settled),
        "pending": len(pending),
        "won": won,
        "lost": lost,
        "pushed": pushed,
        "pnl": pnl,
        "roi": roi,
        "avg_clv_pct": avg_clv * 100.0 if avg_clv is not None else None,
        "clv_n": len(clv_values),
    }


def append_segment_table(lines: list[str], title: str, groups: list[tuple[str, list[dict[str, Any]]]]) -> None:
    lines.extend([
        f"## {title}",
        "",
        "| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for label, group_rows in groups:
        summary = segment_summary(group_rows)
        if not summary["active"]:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    str(summary["active"]),
                    str(summary["settled"]),
                    str(summary["pending"]),
                    f"{summary['won']}-{summary['lost']}-{summary['pushed']}",
                    f"{summary['pnl']:+.2f}u",
                    pct(summary["roi"]),
                    f"{pct(summary['avg_clv_pct'])} (n={summary['clv_n']})",
                ]
            )
            + " |"
        )
    lines.append("")


def render_report(rows: list[dict[str, Any]], picks_path: Path, pinnacle_path: Path, allowed_config: dict[str, Any]) -> str:
    clv_values = [pf(row.get("published_to_close_clv")) for row in rows if pf(row.get("published_to_close_clv")) is not None]
    blocked = [row for row in rows if row.get("blocked_reason")]
    active_rows = [row for row in rows if is_active_pick(row)]
    with_close = [row for row in rows if row.get("pinnacle_price_close")]
    settled = [row for row in rows if str(row.get("result") or "").strip().lower() in SETTLED_RESULTS]
    open_rows = [row for row in rows if str(row.get("result") or "").strip().lower() in {"", "pending"}]
    pnl_values = [pf(row.get("pnl_units")) for row in settled if pf(row.get("pnl_units")) is not None]
    total_pnl = sum(value for value in pnl_values if value is not None)
    avg_clv = avg([value for value in clv_values if value is not None])
    now = datetime.now(UTC)
    close_eligible = [
        row
        for row in rows
        if (parse_dt(row.get("kickoff_utc")) or datetime.max.replace(tzinfo=UTC)) <= now
    ]
    true_close_rows = [row for row in close_eligible if row_bool(row.get("true_close"))]
    true_close_clv = [
        value
        for value in (pf(row.get("published_to_close_clv")) for row in true_close_rows)
        if value is not None
    ]
    close_coverage = len(true_close_rows) / len(close_eligible) if close_eligible else None
    avg_true_close_clv = avg(true_close_clv)
    model = str(allowed_config.get("model") or "corners-research")
    lines = [
        f"# Corners CLV Monitor: `{model}`",
        "",
        f"Generated: {fmt_dt(datetime.now(UTC))}",
        f"Picks input: `{picks_path.relative_to(ROOT) if picks_path.is_absolute() and ROOT in picks_path.parents else picks_path}`",
        f"Pinnacle input: `{pinnacle_path.relative_to(ROOT) if pinnacle_path.is_absolute() and ROOT in pinnacle_path.parents else pinnacle_path}`",
        "",
        "## Summary",
        "",
        f"- Picks: {len(rows)}",
        f"- Active published picks: {len(active_rows)}",
        f"- Settled: {len(settled)}",
        f"- Open/pending: {len(open_rows)}",
        f"- Settled PnL: {total_pnl:+.2f}u" if settled else "- Settled PnL: -",
        f"- Picks with close: {len(with_close)}",
        f"- True-close coverage (<=120m): {len(true_close_rows)}/{len(close_eligible)} ({close_coverage:.1%})" if close_coverage is not None else "- True-close coverage (<=120m): -",
        f"- Average true-close CLV: {avg_true_close_clv:+.2%} (n={len(true_close_clv)})" if avg_true_close_clv is not None else "- Average true-close CLV: -",
        f"- Hard-guard blocked: {len(blocked)}",
        f"- Average published-to-close CLV: {avg_clv:+.2%}" if avg_clv is not None else "- Average published-to-close CLV: -",
        f"- Allowed-league config valid: {'yes' if allowed_config.get('config_valid') else 'no'}",
        f"- Allowed leagues: `{', '.join(allowed_config.get('allowed_leagues', [])) or '-'}`",
        f"- Config error: `{allowed_config.get('config_error') or '-'}`",
        "",
    ]
    append_segment_table(lines, "Active Side Breakdown", [(side.title(), [row for row in rows if str(row.get("side") or "").strip().lower() == side]) for side in ("over", "under")])
    leagues = sorted({str(row.get("league") or "").strip().lower() for row in active_rows if str(row.get("league") or "").strip()})
    append_segment_table(lines, "Active League Breakdown", [(league or "unknown", [row for row in rows if str(row.get("league") or "").strip().lower() == league]) for league in leagues])
    append_segment_table(
        lines,
        "Active Side x League Breakdown",
        [
            (f"{side.title()} / {league}", [
                row for row in rows
                if str(row.get("side") or "").strip().lower() == side
                and str(row.get("league") or "").strip().lower() == league
            ])
            for side in ("over", "under")
            for league in leagues
        ],
    )
    lines.extend([
        "## Required Fields",
        "",
        "- `current_model_would_have_priced` must be true for publication while canonical-only evidence is below threshold.",
        "- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.",
        "- `published_to_close_clv` tracks the taken/published Pinnacle price versus close.",
        "- `close_lag_minutes` records how far the selected close snapshot was from kickoff; `true_close=true` requires <=120 minutes.",
        "- `model_to_close_clv` tracks the model-implied probability versus close.",
        "- `confidence_guard_applied=true` means the row must not be treated as a published pick.",
        "",
        "## De-Promotion Rules",
        "",
        f"- Pause `{model}` if 30-day rolling CLV is below 0 with at least 50 settled picks.",
        "- Pause corners v0 if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.",
        "",
        "## Re-Promotion Rules After A Pause",
        "",
        "- Re-run the original full-window and last-90 Brier/log-loss gates.",
        "- Document the specific cause of the pause: negative CLV drift or Brier calibration drift.",
        "- Ship a documented data/model/scope change before re-enabling; do not simply re-enable because variance looks nicer.",
        "- Wait at least 14 days after the pause before attempting re-promotion.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Join corners v0 research picks to Pinnacle CLV prices")
    parser.add_argument("--picks", type=Path, default=DEFAULT_PICKS)
    parser.add_argument("--pinnacle", type=Path, default=DEFAULT_PINNACLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--allowed-config", type=Path, default=DEFAULT_ALLOWED_CONFIG)
    parser.add_argument(
        "--allow-canonical-only",
        action="store_true",
        help="Disable the hard canonical-only publication guard. Do not use until segment evidence exists.",
    )
    args = parser.parse_args()

    picks = load_csv(args.picks)
    pinnacle_rows = load_csv(args.pinnacle)
    index = build_pinnacle_index(pinnacle_rows)
    existing_settlements = load_existing_settlements(args.output)
    allowed_config = load_allowed_config(args.allowed_config)
    allowed_leagues = {str(league).strip().lower() for league in allowed_config.get("allowed_leagues", [])}
    allow_canonical_only = args.allow_canonical_only or bool(allowed_config.get("canonical_only_allowed"))
    rows = [
        preserve_settlement(
            build_pick_row(
            pick,
            index,
            allow_canonical_only=allow_canonical_only,
            allowed_leagues=allowed_leagues,
            config_valid=bool(allowed_config.get("config_valid")),
            config_error=str(allowed_config.get("config_error") or ""),
            ),
            existing_settlements,
        )
        for pick in picks
    ]
    write_csv(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(rows, args.picks, args.pinnacle, allowed_config), encoding="utf-8")
    print(f"Wrote {display_path(args.output)}")
    print(f"Wrote {display_path(args.report)}")


if __name__ == "__main__":
    main()
