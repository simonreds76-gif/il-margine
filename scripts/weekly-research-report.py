#!/usr/bin/env python3
"""Weekly research-lane monitoring report.

This is intentionally boring and strict: it reports what is live, what is
blocked, how much live CLV evidence exists, and whether any pre-agreed pause
rule has fired. It must not fail just because no research picks exist yet.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "football-form"
DEFAULT_JSON = OUT_DIR / "weekly-research-report.json"
DEFAULT_REPORT = OUT_DIR / "weekly-research-report.md"

TEAM_SHOTS_MODEL = "canonical_form_v3_ema20_nb"
CORNERS_MODEL = "canonical_form_v0"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_env_files() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": f"{display_path(path)} parse failed: {exc}"}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def pf(value: Any) -> float | None:
    text = str(value or "").strip().replace("%", "")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value:+.{digits}f}%"


def league_title(league: str) -> str:
    return {
        "epl": "EPL",
        "serie-a": "Serie A",
        "la-liga": "La Liga",
        "bundesliga": "Bundesliga",
        "ligue-1": "Ligue 1",
    }.get(league, league or "-")


def join_leagues(leagues: list[str]) -> str:
    return ", ".join(league_title(league) for league in leagues) if leagues else "-"


def find_lane(state: dict[str, Any], market: str, model: str) -> dict[str, Any]:
    for lane in state.get("lanes", []) or []:
        if lane.get("market") == market and lane.get("model") == model:
            return lane
    return {}


def clv_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    settled = [row for row in rows if (row.get("result") or "").strip()]
    avg_pub_close = avg([x for x in (pf(row.get("published_to_close_clv")) for row in settled) if x is not None])
    avg_model_close = avg([x for x in (pf(row.get("model_to_close_clv")) for row in settled) if x is not None])
    pnl = sum(x for x in (pf(row.get("pnl_units")) for row in settled) if x is not None)
    positive_clv = [
        row
        for row in settled
        if (pf(row.get("published_to_close_clv")) is not None and (pf(row.get("published_to_close_clv")) or 0) > 0)
    ]
    return {
        "published_picks": len(rows),
        "settled": len(settled),
        "pnl_units": round(pnl, 4),
        "avg_published_to_close_clv": avg_pub_close,
        "avg_model_to_close_clv": avg_model_close,
        "positive_clv_share": len(positive_clv) / len(settled) if settled else None,
        "sample_state": "actionable" if len(settled) >= 50 else "too_early",
        "pause_rule_fired": bool(len(settled) >= 50 and avg_pub_close is not None and avg_pub_close < 0),
    }


def weighted_last90_delta(promotion: dict[str, Any]) -> dict[str, Any]:
    total_n = 0
    current_sum = 0.0
    canonical_sum = 0.0
    league_rows: list[dict[str, Any]] = []
    for row in promotion.get("league_results", []) or []:
        last90 = row.get("last_90_common") or {}
        n = int(last90.get("n") or 0)
        current = pf(last90.get("current_mae"))
        canonical = pf(last90.get("canonical_mae"))
        improvement = pf(last90.get("improvement_pct"))
        if n and current is not None and canonical is not None:
            total_n += n
            current_sum += current * n
            canonical_sum += canonical * n
        league_rows.append(
            {
                "league": row.get("league", ""),
                "passes": bool(row.get("passes")),
                "n": n,
                "current_mae": current,
                "canonical_mae": canonical,
                "improvement_pct": improvement,
            }
        )
    current_mae = current_sum / total_n if total_n else None
    canonical_mae = canonical_sum / total_n if total_n else None
    improvement = (current_mae - canonical_mae) / current_mae if current_mae else None
    return {
        "n": total_n,
        "current_mae": current_mae,
        "canonical_mae": canonical_mae,
        "improvement_pct": improvement,
        "leagues": league_rows,
    }


def build_payload() -> dict[str, Any]:
    state = load_json(OUT_DIR / "research-lane-state.json")
    team_allowed = load_json(OUT_DIR / "team-shots-v3-ema20-allowed-leagues.json")
    team_promo = load_json(OUT_DIR / "team-shots-v3-ema20-promotion-check.json")
    corners_allowed = load_json(OUT_DIR / "corners-v0-allowed-leagues.json")
    corners_diag = load_json(OUT_DIR / "corners-total-diagnostic.json")

    team_clv_rows = load_csv(OUT_DIR / "team-shots-v3-ema20-clv-monitor.csv")
    corners_clv_rows = load_csv(OUT_DIR / "corners-v0-clv-monitor.csv")

    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "team_shots_v3_ema20": {
            "label": "Team Shots V3 EMA20 Research",
            "model": TEAM_SHOTS_MODEL,
            "lane": find_lane(state, "team_shots", TEAM_SHOTS_MODEL),
            "allowed_leagues": team_allowed.get("allowed_leagues", []),
            "blocked_leagues": team_allowed.get("blocked_leagues", []),
            "canonical_only_allowed": bool(team_allowed.get("canonical_only_allowed")),
            "segment_gate": weighted_last90_delta(team_promo),
            "clv": clv_summary(team_clv_rows),
        },
        "corners_v0": {
            "label": "Corners V0 Research Partial",
            "model": CORNERS_MODEL,
            "lane": find_lane(state, "corners_total", CORNERS_MODEL),
            "allowed_leagues": corners_allowed.get("allowed_leagues", []),
            "blocked_leagues": corners_allowed.get("blocked_leagues", []),
            "canonical_only_allowed": bool(corners_allowed.get("canonical_only_allowed")),
            "blocked_diagnostic": {
                league: corners_diag.get("by_league", {}).get(league, {})
                for league in corners_allowed.get("blocked_leagues", [])
            },
            "clv": clv_summary(corners_clv_rows),
        },
    }
    payload["status"] = {
        "pause_required": bool(
            payload["team_shots_v3_ema20"]["clv"]["pause_rule_fired"]
            or payload["corners_v0"]["clv"]["pause_rule_fired"]
        ),
        "read": "observe_live_sample",
    }
    return payload


def render_report(payload: dict[str, Any]) -> str:
    team = payload["team_shots_v3_ema20"]
    corners = payload["corners_v0"]
    team_gate = team["segment_gate"]
    team_clv = team["clv"]
    corners_clv = corners["clv"]

    lines = [
        "# Weekly Research Lane Report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Overall read: {'PAUSE REQUIRED' if payload['status']['pause_required'] else 'observe live sample'}",
        "",
        "## Team Shots V3 EMA20 Research",
        "",
        f"- Model: `{team['model']}`",
        f"- Allowed leagues: {join_leagues(team['allowed_leagues'])}",
        f"- Blocked leagues: {join_leagues(team['blocked_leagues'])}",
        f"- Canonical-only fixtures: {'allowed' if team['canonical_only_allowed'] else 'blocked'}",
        f"- Last-90 segment gate: {team_gate['n']} rows, current MAE {team_gate['current_mae']:.4f}, V3 MAE {team_gate['canonical_mae']:.4f}, improvement {pct((team_gate['improvement_pct'] or 0) * 100)}" if team_gate["current_mae"] is not None and team_gate["canonical_mae"] is not None else "- Last-90 segment gate: unavailable",
        f"- Live CLV sample: {team_clv['published_picks']} published, {team_clv['settled']} settled",
        f"- Avg published-to-close CLV: {pct((team_clv['avg_published_to_close_clv'] or 0) * 100) if team_clv['avg_published_to_close_clv'] is not None else '-'}",
        f"- P/L sample: {team_clv['pnl_units']:+.2f}u",
        f"- Action: {'pause and investigate' if team_clv['pause_rule_fired'] else 'watch passively; not enough live sample until 50 settled picks' if team_clv['sample_state'] == 'too_early' else 'continue'}",
        "",
        "## Corners V0 Research Partial",
        "",
        f"- Model: `{corners['model']}`",
        f"- Allowed leagues: {join_leagues(corners['allowed_leagues'])}",
        f"- Blocked leagues: {join_leagues(corners['blocked_leagues'])}",
        f"- Canonical-only fixtures: {'allowed' if corners['canonical_only_allowed'] else 'blocked'}",
        f"- Live CLV sample: {corners_clv['published_picks']} published, {corners_clv['settled']} settled",
        f"- Avg published-to-close CLV: {pct((corners_clv['avg_published_to_close_clv'] or 0) * 100) if corners_clv['avg_published_to_close_clv'] is not None else '-'}",
        f"- P/L sample: {corners_clv['pnl_units']:+.2f}u",
        f"- Action: {'pause and investigate' if corners_clv['pause_rule_fired'] else 'keep partial; Bundesliga/La Liga remain blocked'}",
        "",
        "## Blocked Corners Diagnostic",
        "",
    ]
    blocked_diag = corners.get("blocked_diagnostic", {})
    if blocked_diag:
        for league, row in blocked_diag.items():
            delta = pf(row.get("mae_delta"))
            lines.append(
                f"- {league_title(league)}: current MAE {row.get('current_mae', '-')}, V0 MAE {row.get('canonical_mae', '-')}, delta {delta:+.4f}" if delta is not None else f"- {league_title(league)}: diagnostic unavailable"
            )
    else:
        lines.append("- No blocked league diagnostic available.")

    lines.extend(
        [
            "",
            "## Plain-English Read",
            "",
            "- Team-shots V3 is not proven profitable live yet; it is the first broad research candidate that passed the backtest segment gates.",
            "- Corners V0 is narrower and deliberately blocked in two leagues. That is a discipline feature, not a failure.",
            "- The next real evidence is CLV and settled live sample. Until 50 settled picks, do not overreact to wins/losses.",
            "",
        ]
    )
    return "\n".join(lines)


def telegram_text(payload: dict[str, Any]) -> str:
    team = payload["team_shots_v3_ema20"]
    corners = payload["corners_v0"]
    team_clv = team["clv"]
    corners_clv = corners["clv"]
    return "\n".join(
        [
            "Il Margine weekly research report",
            f"Generated: {payload['generated_at']}",
            "",
            f"Team Shots V3 EMA20: {len(team['allowed_leagues'])}/5 leagues, {team_clv['published_picks']} picks, {team_clv['settled']} settled, avg CLV {pct((team_clv['avg_published_to_close_clv'] or 0) * 100) if team_clv['avg_published_to_close_clv'] is not None else '-'}",
            f"Corners V0: {len(corners['allowed_leagues'])}/5 leagues, blocked {join_leagues(corners['blocked_leagues'])}, {corners_clv['published_picks']} picks, {corners_clv['settled']} settled, avg CLV {pct((corners_clv['avg_published_to_close_clv'] or 0) * 100) if corners_clv['avg_published_to_close_clv'] is not None else '-'}",
            "",
            "Read: observe live sample. No production claim until CLV/settled sample is real.",
        ]
    )


def post_telegram(message: str) -> bool:
    token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("WEEKLY_REPORT_TELEGRAM skipped missing creds")
        return False
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
        print("WEEKLY_REPORT_TELEGRAM sent")
        return True
    except Exception as exc:
        print(f"Warning: telegram post failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and optionally send the weekly research-lane report.")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    load_env_files()
    payload = build_payload()
    report = render_report(payload)

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    print(report)
    print(f"Wrote {display_path(args.json)}")
    print(f"Wrote {display_path(args.report)}")

    if not args.no_telegram:
        post_telegram(telegram_text(payload))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
