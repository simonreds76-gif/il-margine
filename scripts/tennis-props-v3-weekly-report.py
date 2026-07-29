#!/usr/bin/env python3
"""Build and send the weekly ATP ace-v3 evidence summary."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v3-all-tour-gate.json"
DEFAULT_SIGNALS = ROOT / "data" / "tennis-props" / "shadow" / "aces-v3-shadow-signals.csv"
DEFAULT_JSON = ROOT / "data" / "tennis-props" / "backtest" / "aces-v3-weekly-report.json"
DEFAULT_REPORT = ROOT / "data" / "tennis-props" / "backtest" / "aces-v3-weekly-report.txt"


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing v3 gate: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid v3 gate object: {path}")
    return payload


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def evidence(signals: list[dict[str, str]], gate: dict[str, Any]) -> dict[str, Any]:
    settled = [row for row in signals if (row.get("settlement_status") or "").strip().lower() == "settled"]
    pending = [row for row in signals if (row.get("settlement_status") or "").strip().lower() == "pending"]
    event_keys: set[str] = set()
    for row in settled:
        event_id = (row.get("event_id") or "").strip()
        if event_id:
            event_keys.add(f"event:{event_id}")
            continue
        pair = sorted(((row.get("player") or "").strip(), (row.get("opponent") or "").strip()))
        event_keys.add(f"pair:{row.get('date', '')}|{row.get('tour', '')}|{'|'.join(pair)}")

    clv = [number(row.get("clv_pct")) for row in signals if (row.get("clv_pct") or "").strip()]
    pnl = sum(number(row.get("pnl")) for row in settled)
    settled_count = len(settled)
    sell_gate = gate.get("sellability_gate") if isinstance(gate.get("sellability_gate"), dict) else {}
    min_settled = int(number(sell_gate.get("minimum_settled_real_lines"), 300))
    min_events = int(number(sell_gate.get("minimum_distinct_events"), 100))
    required_clv = number(sell_gate.get("required_mean_clv_pct"), 1.0)
    required_roi = number(sell_gate.get("required_roi_pct"), 0.0)
    mean_clv = sum(clv) / len(clv) if clv else 0.0
    roi = pnl / settled_count * 100.0 if settled_count else 0.0
    failures: list[str] = []
    if settled_count < min_settled:
        failures.append(f"settled {settled_count}/{min_settled}")
    if len(event_keys) < min_events:
        failures.append(f"events {len(event_keys)}/{min_events}")
    if len(clv) < min_settled:
        failures.append(f"CLV coverage {len(clv)}/{min_settled}")
    if mean_clv < required_clv:
        failures.append(f"mean CLV {mean_clv:+.2f}%/{required_clv:+.2f}%")
    if roi < required_roi:
        failures.append(f"ROI {roi:+.2f}%/{required_roi:+.2f}%")
    return {
        "status": "PASS" if not failures else "BLOCKED",
        "reason": "all real-price gates passed" if not failures else "; ".join(failures),
        "signals": len(signals),
        "pending": len(pending),
        "settled": settled_count,
        "distinct_events": len(event_keys),
        "pnl_units": round(pnl, 4),
        "roi_pct": round(roi, 4),
        "clv_coverage": len(clv),
        "mean_clv_pct": round(mean_clv, 4),
        "positive_clv_pct": round(sum(1 for value in clv if value > 0) / len(clv) * 100.0, 2) if clv else 0.0,
        "minimum_settled": min_settled,
        "minimum_events": min_events,
        "required_clv_pct": required_clv,
        "required_roi_pct": required_roi,
    }


def build_payload(gate: dict[str, Any], signals: list[dict[str, str]]) -> dict[str, Any]:
    deployment = gate.get("deployment_safe_aces") if isinstance(gate.get("deployment_safe_aces"), dict) else {}
    atp = deployment.get("ATP") if isinstance(deployment.get("ATP"), dict) else {}
    wta = deployment.get("WTA") if isinstance(deployment.get("WTA"), dict) else {}
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "model_generated_at": gate.get("generated_at"),
        "model_status": gate.get("status", "UNKNOWN"),
        "routing": gate.get("routing", "blocked"),
        "atp": {
            "status": atp.get("status", "UNKNOWN"),
            "mae_improvement_pct": number(atp.get("mae_improvement_pct")),
            "logloss_delta": number(atp.get("logloss_delta")),
            "surfaces": sorted((atp.get("surfaces") or {}).keys()) if isinstance(atp.get("surfaces"), dict) else [],
        },
        "wta": {
            "status": wta.get("status", "UNKNOWN"),
            "mae_improvement_pct": number(wta.get("mae_improvement_pct")),
            "logloss_delta": number(wta.get("logloss_delta")),
        },
        "evidence": evidence(signals, gate),
    }


def report_text(payload: dict[str, Any]) -> str:
    atp = payload["atp"]
    wta = payload["wta"]
    ev = payload["evidence"]
    return "\n".join(
        [
            "Tennis Props v3 Weekly Evidence",
            f"Generated UTC: {payload['generated_at']}",
            f"Model refit: {payload.get('model_generated_at') or '-'}",
            "",
            f"ATP aces: {atp['status']} on {', '.join(atp['surfaces']) or 'no verified surface'}",
            f"Holdout improvement: MAE {atp['mae_improvement_pct']:+.2f}%; log-loss delta {atp['logloss_delta']:+.6f}",
            f"WTA aces: {wta['status']} (not routed while its surface guard fails)",
            "",
            f"Prospective ledger: {ev['settled']} settled, {ev['pending']} pending, {ev['distinct_events']} events",
            f"P/L {ev['pnl_units']:+.2f}u | ROI {ev['roi_pct']:+.2f}%",
            f"CLV {ev['mean_clv_pct']:+.2f}% across {ev['clv_coverage']} rows | positive CLV {ev['positive_clv_pct']:.1f}%",
            f"Sellability: {ev['status']} - {ev['reason']}",
            "",
            "Scope: ATP aces, Hard/Clay, shadow-only. WTA, DFs and Grass remain blocked.",
        ]
    )


def post_telegram(message: str) -> None:
    token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("OPS alert Telegram credentials are missing")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": message, "disable_web_page_preview": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Telegram send failed: {exc}") from exc


def publish_github_variable(payload: dict[str, Any], repository: str) -> None:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    result = subprocess.run(
        ["gh", "variable", "set", "TENNIS_PROPS_V3_WEEKLY_JSON", "--repo", repository, "--body", body],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown gh error").strip()
        raise RuntimeError(f"GitHub weekly snapshot publish failed: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and send the ATP ace-v3 weekly evidence report.")
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-telegram", action="store_true")
    parser.add_argument("--no-github", action="store_true")
    parser.add_argument("--github-repository", default=os.environ.get("GITHUB_REPOSITORY", "simonreds76-gif/il-margine"))
    args = parser.parse_args()

    load_env()
    gate = load_json(args.gate)
    payload = build_payload(gate, load_csv(args.signals))
    rendered = report_text(payload)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if not args.no_github:
        publish_github_variable(payload, args.github_repository)
        print("TENNIS_PROPS_V3_WEEKLY_GITHUB_SNAPSHOT published")
    if not args.no_telegram and os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN") and os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID"):
        post_telegram(rendered)
        print("TENNIS_PROPS_V3_WEEKLY_TELEGRAM sent")
    elif not args.no_telegram:
        print("TENNIS_PROPS_V3_WEEKLY_TELEGRAM deferred to Monday GitHub report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
