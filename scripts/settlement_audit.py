from __future__ import annotations

import csv
import json
import argparse
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

PendingBucket = str

PENDING_BUCKETS: tuple[PendingBucket, ...] = (
    "future",
    "live",
    "stale",
    "old_stale",
    "unknown",
)


def _parse_date_only(raw: str) -> Optional[date]:
    text = (raw or "").strip()[:10]
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime_utc(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_iso_z(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_pending_row(
    row: Mapping[str, str],
    *,
    now_utc: datetime,
    kickoff_fields: Sequence[str],
    date_fields: Sequence[str],
    stale_threshold_hours: float = 3.0,
    old_stale_threshold_hours: float = 48.0,
) -> tuple[PendingBucket, str, Optional[float]]:
    kickoff_dt: Optional[datetime] = None
    for field in kickoff_fields:
        kickoff_dt = _parse_datetime_utc(str(row.get(field, "") or ""))
        if kickoff_dt is not None:
            break

    if kickoff_dt is None:
        for field in date_fields:
            raw_date = str(row.get(field, "") or "").strip()
            parsed_date = _parse_date_only(raw_date)
            if parsed_date is None:
                continue
            kickoff_dt = datetime.combine(parsed_date, time(23, 59, 59), tzinfo=timezone.utc)
            break

    if kickoff_dt is None:
        return "unknown", "", None

    hours = (now_utc - kickoff_dt).total_seconds() / 3600
    kickoff_iso = _to_iso_z(kickoff_dt)
    if hours < 0:
        return "future", kickoff_iso, round(hours, 2)
    if hours < stale_threshold_hours:
        return "live", kickoff_iso, round(hours, 2)
    if hours < old_stale_threshold_hours:
        return "stale", kickoff_iso, round(hours, 2)
    return "old_stale", kickoff_iso, round(hours, 2)


def load_settlement_overrides(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _normalize_match_text(row: Mapping[str, str]) -> str:
    explicit = str(row.get("match", "") or "").strip()
    if explicit:
        return explicit.casefold()
    home = str(row.get("home_team", "") or "").strip()
    away = str(row.get("away_team", "") or "").strip()
    return f"{home} vs {away}".strip().casefold()


def find_matching_override(
    row: Mapping[str, str],
    overrides: Sequence[Mapping[str, str]],
    *,
    kickoff_fields: Sequence[str],
    date_fields: Sequence[str],
) -> Optional[dict]:
    if not overrides:
        return None
    row_league = str(row.get("league", "") or "").strip().casefold()
    row_match = _normalize_match_text(row)
    row_kickoff = ""
    for field in kickoff_fields:
        row_kickoff = str(row.get(field, "") or "").strip()
        if row_kickoff:
            break
    if not row_kickoff:
        for field in date_fields:
            raw_date = str(row.get(field, "") or "").strip()[:10]
            if raw_date:
                row_kickoff = f"{raw_date}T23:59:59Z"
                break

    normalized_row_kickoff = _to_iso_z(_parse_datetime_utc(row_kickoff)) if row_kickoff else ""
    for override in overrides:
        league = str(override.get("league", "") or "").strip().casefold()
        match = str(override.get("match", "") or "").strip().casefold()
        if league != row_league or match != row_match:
            continue
        override_kickoff = str(override.get("kickoff_iso", "") or "").strip()
        if not override_kickoff:
            return dict(override)
        normalized_override_kickoff = _to_iso_z(_parse_datetime_utc(override_kickoff))
        if normalized_override_kickoff and normalized_override_kickoff == normalized_row_kickoff:
            return dict(override)
    return None


def summarize_pending_row(
    row: Mapping[str, str],
    *,
    kickoff_iso: str,
    hours_elapsed: Optional[float],
) -> dict:
    return {
        "match": str(row.get("match", "") or "").strip()
        or f"{str(row.get('home_team', '') or '').strip()} vs {str(row.get('away_team', '') or '').strip()}".strip(),
        "league": str(row.get("league", "") or "").strip(),
        "line": str(row.get("line", "") or "").strip(),
        "side": str(row.get("side", "") or "").strip(),
        "kickoff": kickoff_iso,
        "hours_elapsed": hours_elapsed,
    }


def build_settlement_audit(
    *,
    rows: Sequence[Mapping[str, str]],
    model: str,
    now_utc: datetime,
    settled_this_run: int,
    is_pending: Callable[[Mapping[str, str]], bool],
    is_settled: Callable[[Mapping[str, str]], bool],
    kickoff_fields: Sequence[str],
    date_fields: Sequence[str],
    source_freshness: Mapping[str, Mapping[str, object]],
    overrides: Sequence[Mapping[str, str]],
    stale_threshold_hours: float = 3.0,
    old_stale_threshold_hours: float = 48.0,
    same_league_stale_fail_count: int = 3,
) -> dict:
    pending_breakdown = {bucket: 0 for bucket in PENDING_BUCKETS}
    stale_rows: List[dict] = []
    old_stale_rows: List[dict] = []
    unknown_rows: List[dict] = []
    overridden_rows: List[dict] = []
    stale_by_league: Counter[str] = Counter()

    for row in rows:
        if not is_pending(row):
            continue
        override = find_matching_override(
            row,
            overrides,
            kickoff_fields=kickoff_fields,
            date_fields=date_fields,
        )
        if override is not None:
            kickoff = str(override.get("kickoff_iso", "") or "").strip()
            overridden_rows.append(
                {
                    **summarize_pending_row(row, kickoff_iso=kickoff, hours_elapsed=None),
                    "reason": str(override.get("reason", "") or "").strip(),
                }
            )
            continue

        bucket, kickoff_iso, hours_elapsed = classify_pending_row(
            row,
            now_utc=now_utc,
            kickoff_fields=kickoff_fields,
            date_fields=date_fields,
            stale_threshold_hours=stale_threshold_hours,
            old_stale_threshold_hours=old_stale_threshold_hours,
        )
        pending_breakdown[bucket] += 1
        summary = summarize_pending_row(row, kickoff_iso=kickoff_iso, hours_elapsed=hours_elapsed)
        if bucket == "stale":
            stale_rows.append(summary)
            stale_by_league[summary["league"] or "?"] += 1
        elif bucket == "old_stale":
            old_stale_rows.append(summary)
        elif bucket == "unknown":
            unknown_rows.append(summary)

    warnings: List[str] = []
    errors: List[str] = []

    if stale_rows:
        warnings.append(
            f"{len(stale_rows)} stale pending row(s) ({stale_threshold_hours:g}-{old_stale_threshold_hours:g}h elapsed)"
        )
    if unknown_rows:
        warnings.append(f"{len(unknown_rows)} pending row(s) with unknown kickoff")

    for league, stats in source_freshness.items():
        lag_days = stats.get("lag_days")
        try:
            lag_days_val = int(lag_days) if lag_days is not None else None
        except (TypeError, ValueError):
            lag_days_val = None
        if lag_days_val is not None and lag_days_val > 3:
            warnings.append(
                f"{league}: Football-Data latest date is {stats.get('football_data_latest') or 'unknown'} ({lag_days_val}d old)"
            )
        football_data_count = int(stats.get("football_data_count") or 0)
        fotmob_count = int(stats.get("fotmob_count") or 0)
        api_football_count = int(stats.get("api_football_count") or 0)
        api_football_error = str(stats.get("api_football_error", "") or "").strip()
        if football_data_count == 0 and fotmob_count == 0 and api_football_count == 0:
            warnings.append(f"{league}: Football-Data, FotMob, and API-Football all returned 0 results")
        elif api_football_error:
            warnings.append(f"{league}: API-Football fallback issue - {api_football_error}")

    if old_stale_rows:
        errors.append(f"{len(old_stale_rows)} old stale pending row(s) (>={old_stale_threshold_hours:g}h elapsed)")
    for league, count in stale_by_league.items():
        if count >= same_league_stale_fail_count:
            errors.append(f"{league}: {count} stale pending rows from the same league")

    total_settled = sum(1 for row in rows if is_settled(row))
    total_pending = sum(1 for row in rows if is_pending(row))
    audit = {
        "run_at": _to_iso_z(now_utc),
        "model": model,
        "total_bets": len(rows),
        "settled_this_run": settled_this_run,
        "total_settled": total_settled,
        "total_pending": total_pending,
        "pending_breakdown": pending_breakdown,
        "source_freshness": source_freshness,
        "stale_rows": stale_rows,
        "old_stale_rows": old_stale_rows,
        "unknown_rows": unknown_rows,
        "overridden_rows": overridden_rows,
        "warnings": warnings,
        "errors": errors,
        "exit_code_recommendation": 1 if errors else 0,
    }
    return audit


def write_audit(path: Path, audit: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def emit_github_annotations(audit: Mapping[str, object]) -> None:
    model = str(audit.get("model") or "settlement")
    for message in audit.get("warnings", []) or []:
        print(f"::warning title=Settlement Warning ({model})::{message}")
    for message in audit.get("errors", []) or []:
        print(f"::error title=Settlement Failure ({model})::{message}")


def read_audit(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit settlement audit annotations and exit on failure")
    parser.add_argument("paths", nargs="+", help="Settlement audit JSON files to inspect")
    args = parser.parse_args()

    exit_code = 0
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            print(f"::warning title=Settlement Warning (missing audit)::Audit file missing: {path}")
            continue
        audit = read_audit(path)
        emit_github_annotations(audit)
        exit_code = max(exit_code, int(audit.get("exit_code_recommendation", 0)))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
