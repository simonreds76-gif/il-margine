"""Attach scoped model records to alerts and retain future provisional quotes.

Reports describe model selections, not a user's bets or confirmed Telegram
delivery. Audited provisional history is explicitly labelled reconstructed; forward alert receipts stay separate.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from tennis_provisional_performance import provisional_summary, format_provisional

REPORTS = {
    "STRICT": ("Strict", "strict-policy-performance-weekly.csv"),
    "VOL200": ("Volume 200", "strict-policy-performance-volume200-weekly.csv"),
    "SPREAD V1": ("Spread v1", "strict-policy-performance-spreadv1-weekly.csv"),
    "GRASS BO3": ("Grass BO3", "strict-policy-performance-grass_bo3-weekly.csv"),
    "CLAY BO3": ("Clay BO3", "strict-policy-performance-clay_bo3-weekly.csv"),
    "CPI SPEED": ("CPI Speed", "strict-policy-performance-cpi_speed-weekly.csv"),
}
PROVISIONAL = {"PROVISIONAL HARD ML": "provisional_hard", "PROVISIONAL ML EXPANSION": "provisional_expansion"}


def number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def primary_label(signal: Any) -> str | None:
    if 'MOST DF PAPER' in signal.labels:
        return 'MOST DF PAPER'
    if 'MOST ACES PAPER' in signal.labels:
        return 'MOST ACES PAPER'
    if signal.section in PROVISIONAL:
        return PROVISIONAL[signal.section]
    return next((label for label in signal.labels if label in REPORTS), None)


def saved_report(root: Path, label: str, market: str, now: datetime) -> str:
    name, filename = REPORTS[label]
    title = f"{name} {'ML' if market == 'ml' else 'handicap'} record"
    try:
        rows = read_csv(root / "data/backtest" / filename)
        latest = max(row.get("generated_utc", "") for row in rows)
        generated = utc(latest)
        if generated is None or generated > now or (now - generated).total_seconds() > 72 * 3600:
            return f"{title}: ROI unavailable; performance report needs refresh."
        selected = [row for row in rows if row.get("generated_utc") == latest
                    and row.get("scope") == "all_time" and row.get("eval_period") == "clean"
                    and row.get("league_scope") == "combined" and row.get("policy_mode") == "base"
                    and row.get("bet_type") == market]
        if len(selected) != 1:
            return f"{title}: ROI unavailable for this exact market and policy period."
        row = selected[0]
        roi, pnl, stake = (number(row.get(key)) for key in ("roi_pct", "pnl_units", "staked_units"))
        settled, wins, losses, pending = (number(row.get(key)) for key in ("settled", "wins", "losses", "unsettled"))
        if settled == 0:
            return f"{title}: no settled selections yet."
        if any(value is None for value in (roi, pnl, stake, settled, wins, losses, pending)) or stake <= 0 or abs(roi - pnl / stake * 100) > 0.02 or wins + losses > settled or any(value < 0 or not value.is_integer() for value in (settled, wins, losses, pending)):
            return f"{title}: ROI unavailable; report totals need review."
        other = int(settled - wins - losses)
        record = f"{int(wins)}W/{int(losses)}L" + (f"/{other} void or push" if other else "")
        small = " | small sample" if settled < 50 else ""
        return (f"{title}: ROI {roi:+.2f}% | P/L {pnl:+.2f}u | {int(settled)} settled ({record}){small}\n"
                f"Report cutoff {row.get('as_of_date') or 'unknown'} | {int(pending)} unresolved | refreshed {generated.date().isoformat()}")
    except (OSError, ValueError, KeyError):
        return f"{title}: ROI unavailable; saved performance report missing or unreadable."


def receipt_dir(root: Path) -> Path:
    return root / "data/backtest/tennis-alert-records"


def provisional_record(root: Path, lane: str, now: datetime) -> dict[str, Any]:
    """Use frozen alert quotes and exact source IDs; quarantine date ambiguity."""
    receipts: dict[str, dict[str, Any]] = {}
    for path in sorted(receipt_dir(root).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload.get("selections", []):
            if record.get("lane") != lane:
                continue
            existing = receipts.get(record["contract_id"])
            if existing is None or record["registered_at"] < existing["registered_at"]:
                receipts[record["contract_id"]] = record
    result: dict[str, Any] = {"registered": len(receipts), "wins": 0, "losses": 0, "void": 0,
                              "pending": 0, "review": 0, "pnl": 0.0, "stake": 0.0,
                              "since": min((r["registered_at"][:10] for r in receipts.values()), default=None)}
    if not receipts:
        return result
    source = read_csv(root / "data/backtest/tennis-model-market-gap-archive.csv")
    for record in receipts.values():
        if record["fixture_date"] > now.date().isoformat():
            result["pending"] += 1
            continue
        candidates = [row for row in source if row.get("anomaly_id") == record.get("source_id")
                      and row.get("selected_side") == record.get("selected_side")
                      and row.get("player1_id") == record.get("player1_id")
                      and row.get("player2_id") == record.get("player2_id")
                      and row.get("bet_type", "match") != "spread"]
        resolved = [row for row in candidates if row.get("settlement_status") == "settled"]
        outcomes = {row.get("bet_outcome") for row in resolved}
        if not record.get("prematch_verified") or not record.get("source_id"):
            result["review"] += 1
        elif not resolved:
            result["pending"] += 1
        elif len(outcomes) != 1 or any(row.get("match_date") != record["fixture_date"] for row in resolved):
            result["review"] += 1
        elif next(iter(outcomes)) in {"VOID", "PUSH"}:
            result["void"] += 1
        elif next(iter(outcomes)) in {"WIN", "LOSS"}:
            win = next(iter(outcomes)) == "WIN"
            selected_id = record["player1_id"] if record["selected_side"] == "P1" else record["player2_id"]
            opponent_id = record["player2_id"] if record["selected_side"] == "P1" else record["player1_id"]
            expected_winner, expected_loser = (selected_id, opponent_id) if win else (opponent_id, selected_id)
            if any(row.get("winner_id") != expected_winner or row.get("loser_id") != expected_loser for row in resolved):
                result["review"] += 1
                continue
            result["wins" if win else "losses"] += 1
            result["stake"] += record["stake"]
            result["pnl"] += record["stake"] * (record["odds"] - 1 if win else -1)
        else:
            result["review"] += 1
    return result


def provisional_text(root: Path, lane: str, now: datetime) -> str:
    return format_provisional(provisional_summary(root, now)[lane])


def props_side(source: dict[str, str]) -> str:
    bettable = source.get("bettable", "").lower() in {"1", "true", "yes"}
    return source.get("recommended_side" if bettable else "shadow_side", "").upper()


def props_record(root: Path, source: dict[str, str]) -> str:
    market, side, tour = source.get("market"), props_side(source), source.get("tour")
    if not market or not side or not tour:
        return "No matching model selection record for this alert."
    path = root / "data/tennis-props/shadow/aces-dfs-shadow-signals.csv"
    if not path.exists(): return "No matching model selection record for this alert."
    rows = read_csv(path)
    rows = [r for r in rows if r.get("market") == market and r.get("side") == side and r.get("tour") == tour
            and r.get("decision_mode") != "breaks_calibration_unfiltered"
            and all(r.get(k, "") == source.get(k, "") for k in ("model_id", "model_version", "variant_id"))]
    name=f"{tour} {market.replace('_', ' ')} {side.title()} watchlist"
    settled=[r for r in rows if r.get("settlement_status") == "settled" and r.get("result") in {"win", "loss", "push"}]
    if not settled: return f"{name}: no settled selections yet | {len(rows)} recorded."
    pnl=sum(number(r.get("pnl")) or 0 for r in settled)
    wins=sum(r.get("result")=="win" for r in settled);losses=sum(r.get("result")=="loss" for r in settled)
    pending=sum(r.get("settlement_status")=="pending" for r in rows)
    return f"{name}: ROI {100*pnl/len(settled):+.2f}% | P/L {pnl:+.2f}u | {len(settled)} settled ({wins}W/{losses}L) | {pending} pending. Hypothetical 1u selections."


def attach_performance(signals: list[Any], root: Path, *, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    cached = {}
    for signal in signals:
        label = primary_label(signal)
        market = "handicap" if len(signal.key) > 4 and signal.key[4].startswith("spread:") else "ml"
        key = (label, market, signal.performance_source.get("market"), signal.performance_source.get("tour"), props_side(signal.performance_source), *(signal.performance_source.get(k, "") for k in ("model_id", "model_version", "variant_id")))
        if key not in cached:
            if label == 'MOST DF PAPER':
                try:
                    r=json.loads((root/'data/tennis-props/shadow/most-df-v1/report.json').read_text())
                    cached[key]=(f"Most DF paper: {r['wins']}W/{r['losses']}L; "
                        + (f"ROI {r['roi_pct']:+.2f}% ({r['pnl_units']:+.2f}u / {r['stake_units']:g}u). " if r['settled'] else 'No settled selections; ROI unavailable. ')
                        + f"{r['pending']} pending. Experimental, uncalibrated; not a proven edge.")
                except (OSError,ValueError,KeyError,TypeError):
                    cached[key]='Most DF paper record unavailable; zero real stake.'
            elif label == 'MOST ACES PAPER':
                from tennis_most_aces_current import record, COUNT_MODEL
                r=record(read_csv(root/'data/tennis-props/shadow/most-aces-1x2-observations.csv'),COUNT_MODEL)
                cached[key]=(f"Count-model paper research: {r['wins']}W/{r['losses']}L; "
                             + (f"ROI {r['roi']:+.1f}% ({r['profit']:+.2f}u / {r['stake']}u). " if r['settled'] else 'No settled paper bets. ')
                             + 'Small experimental sample, not a proven edge. This is the model research record, not an alerted-bets record.')
            elif label in PROVISIONAL.values():
                cached[key] = provisional_text(root, label, now)
            elif label in REPORTS:
                cached[key] = saved_report(root, label, market, now)
            else:
                cached[key] = props_record(root, signal.performance_source)
        signal.performance_text = cached[key]


def retain_dispatch(signals: list[Any], root: Path, messages: list[str], *, now: datetime | None = None) -> Path:
    """Keep accepted relay requests; never label them confirmed delivery."""
    now = now or datetime.now(UTC)
    records = []
    for signal in signals:
        lane = primary_label(signal)
        if lane not in PROVISIONAL.values():
            continue
        source = signal.performance_source
        odds = number(source.get("selected_odds"))
        if odds is None or odds <= 1:
            raise ValueError("Cannot retain an invalid provisional price")
        fixture = signal.key[0]
        # time_utc in this archive is often the capture clock, not a start time.
        start = utc(source.get("scheduled_start_utc", ""))
        before_start = now < start if start else now.date().isoformat() < fixture
        captured = utc(source.get("captured_at", ""))
        fresh = captured is not None and -300 <= (now - captured).total_seconds() <= 6 * 3600
        pair = sorted((source.get("player1_id", ""), source.get("player2_id", "")))
        selected_id = source.get("player1_id" if source.get("selected_side") == "P1" else "player2_id", "")
        parts = [fixture, source.get("tour_id", ""), *pair, selected_id, "ml"]
        records.append({"lane": lane, "contract_id": "|".join(parts),
                        "fixture_date": fixture, "selection": signal.selection,
                        "source_id": source.get("anomaly_id", ""), "selected_side": source.get("selected_side", ""),
                        "player1_id": source.get("player1_id", ""), "player2_id": source.get("player2_id", ""),
                        "odds": odds, "stake": 0.5, "prematch_verified": before_start and fresh and all(pair),
                        "quote_captured_at": source.get("captured_at", ""),
                        "registered_at": now.isoformat().replace("+00:00", "Z")})
    body = {"schema_version": 1, "relay_status": "request_accepted_delivery_unverified",
            "registered_at": now.isoformat().replace("+00:00", "Z"), "selections": records,
            "messages": messages}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    directory = receipt_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{digest[:12]}.json"
    temporary = target.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target
