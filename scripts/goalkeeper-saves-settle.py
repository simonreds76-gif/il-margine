#!/usr/bin/env python3
"""Settle GK Saves v1 shadow signals from API-Football player statistics.

The script is daily-only and hard-capped. It never substitutes team saves for
the named goalkeeper's own saves.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from verified_player_targets import archive_observed_targets, stat_values, count
from football_team_names import football_form_team_key
from goalkeeper_saves_live import ROOT, parse_float, person_match_score
from football_fixture_resolutions import apply_reviewed_voids


BASE_URL = "https://v3.football.api-sports.io"
FOTMOB_MATCHES_URL = "https://www.fotmob.com/api/data/matches"
FOTMOB_MATCH_URL = "https://www.fotmob.com/api/data/matchDetails"
FOTMOB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fotmob.com/",
}
DEFAULT_SIGNALS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-shadow-signals.csv"
DEFAULT_ODDS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-odds-history.csv"
DEFAULT_REPORT = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-settlement-status.json"
LEAGUES = {
    "epl": 39,
    "serie-a": 135,
    "la-liga": 140,
    "bundesliga": 78,
    "ligue-1": 61,
}
FOTMOB_LEAGUES = {
    "epl": 47,
    "serie-a": 55,
    "la-liga": 87,
    "bundesliga": 54,
    "ligue-1": 53,
}
FINISHED = {"FT", "AET", "PEN"}


def iso_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def api_error_messages(payload: dict[str, Any]) -> list[str]:
    errors = payload.get("errors")
    if not errors:
        return []
    if isinstance(errors, dict):
        return [f"{key}: {value}" for key, value in errors.items() if value]
    if isinstance(errors, list):
        return [str(value) for value in errors if value]
    return [str(errors)]


def signal_is_due(signal: dict[str, str], now: datetime) -> bool:
    raw_kickoff = str(signal.get("kickoff_at") or "").strip()
    if raw_kickoff:
        try:
            kickoff = datetime.fromisoformat(raw_kickoff.replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=UTC)
            return kickoff <= now - timedelta(hours=3)
        except ValueError:
            pass
    raw_day = str(signal.get("match_date") or "")[:10]
    try:
        return date.fromisoformat(raw_day) < now.date()
    except ValueError:
        return False


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_env() -> None:
    for path in (ROOT / ".env.local", ROOT / "env.local"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def request_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    key = (os.environ.get("API_FOOTBALL_KEY") or "").strip()
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY is missing")
    response = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        params=params,
        headers={"x-apisports-key": key, "Accept": "application/json", "User-Agent": "il-margine/gk-saves-shadow"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def request_fotmob_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, headers=FOTMOB_HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def request_fotmob_match_payload(match_id: int) -> dict[str, Any]:
    # A fragment on a team-pair page is not sent to the server. Its HTML can
    # therefore describe a newer meeting than the requested historical match.
    page = request_fotmob_json(FOTMOB_MATCH_URL, {"matchId": match_id})
    if str((page.get("general") or {}).get("matchId")) != str(match_id):
        raise ValueError(f"FotMob requested match {match_id} identity mismatch")
    return {"props": {"pageProps": page}}


def validate_fotmob_fixture(payload: dict[str, Any], fixture: dict[str, Any], day: str) -> None:
    general = payload["props"]["pageProps"].get("general") or {}
    if (str(general.get("matchId")) != str(fixture.get("id"))
            or str(general.get("matchTimeUTCDate") or "")[:10] != day
            or general.get("finished") is not True):
        raise ValueError("FotMob fixture ID, date or completed status mismatch")
    for side in ("home", "away"):
        expected = (fixture.get(side) or {}).get("id")
        actual = (general.get(side + "Team") or {}).get("id")
        if not expected or str(expected) != str(actual):
            raise ValueError("FotMob fixture team identity mismatch")


def fotmob_fixtures(payload: dict[str, Any], league: str) -> list[dict[str, Any]]:
    league_id = FOTMOB_LEAGUES.get(league)
    if league_id is None:
        return []
    return [
        match
        for competition in payload.get("leagues") or []
        if int(competition.get("id") or competition.get("primaryId") or 0) == league_id
        for match in competition.get("matches") or []
    ]


def fotmob_fixture_match(row: dict[str, Any], home: str, away: str) -> bool:
    aliases = {"lille osc": "lille", "estac troyes": "troyes"}
    def key(value: object) -> str:
        normalized = football_form_team_key(value)
        return aliases.get(normalized, normalized)
    source_home = key((row.get("home") or {}).get("longName") or (row.get("home") or {}).get("name"))
    source_away = key((row.get("away") or {}).get("longName") or (row.get("away") or {}).get("name"))
    return source_home == key(home) and source_away == key(away)


def fotmob_player_saves(payload: dict[str, Any], goalkeeper: str) -> tuple[int | None, dict[str, Any]]:
    page_props = (payload.get("props") or {}).get("pageProps") or {}
    content = page_props.get("content") or {}
    lineup = content.get("lineup") or {}
    matches: list[tuple[int, dict[str, Any]]] = []
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side) or {}
        for bucket in ("starters", "subs"):
            for player in team.get(bucket) or []:
                score = person_match_score(goalkeeper, player.get("name"))
                if score:
                    matches.append((score, player))
    if not matches:
        return None, {"error": "fotmob_goalkeeper_not_found"}
    matches.sort(key=lambda item: item[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return None, {"error": "fotmob_goalkeeper_ambiguous"}
    player = matches[0][1]
    if int(player.get("positionId") or 0) != 11:
        return None, {"error": "fotmob_matched_player_not_goalkeeper", "position_id": player.get("positionId")}
    keeper_id = int(player.get("id") or 0)
    if keeper_id <= 0:
        return None, {"error": "fotmob_goalkeeper_id_missing"}

    shotmap = content.get("shotmap")
    shots = shotmap.get("shots") if isinstance(shotmap, dict) else None
    # An absent/incomplete event feed is not evidence of zero saves. An
    # explicit player-stat zero can be supplied by the existing API fallback.
    if not isinstance(shots, list) or not shots:
        return None, {"error": "fotmob_shotmap_unavailable"}
    if any(not isinstance(shot, dict) or not shot.get("eventType") for shot in shots):
        return None, {"error": "fotmob_shotmap_incomplete"}
    for shot in shots:
        if (str(shot.get("eventType") or "").casefold() == "attemptsaved"
                and not shot.get("isBlocked") and not shot.get("isSavedOffLine")
                and not shot.get("keeperId")):
            return None, {"error": "fotmob_save_keeper_missing"}

    saves: set[str] = set()
    for index, shot in enumerate(shots):
        if str(shot.get("eventType") or "").casefold() != "attemptsaved":
            continue
        if int(shot.get("keeperId") or 0) != keeper_id:
            continue
        if bool(shot.get("isBlocked")) or bool(shot.get("isSavedOffLine")):
            continue
        if str(shot.get("period") or "").casefold() in {"penaltyshootout", "penalty shootout"}:
            continue
        saves.add(str(shot.get("id") or f"row-{index}"))
    named_stats = (content.get("playerStats") or {}).get(str(keeper_id))
    if named_stats:
        try:
            explicit = count(stat_values(named_stats).get("saves"))
        except ValueError:
            return None, {"error": "fotmob_conflicting_player_totals"}
        if explicit is not None and explicit != len(saves):
            return None, {"error": "fotmob_save_totals_disagree", "player_id": keeper_id,
                          "explicit_saves": explicit, "event_saves": len(saves)}
    return len(saves), {
        "player_id": keeper_id,
        "player_name": player.get("name"),
        "position": "GK",
        "source": "fotmob_named_keeper_shotmap",
    }


def season_for_day(day: date) -> int:
    return day.year if day.month >= 8 else day.year - 1


def fixture_match(row: dict[str, Any], home: str, away: str) -> bool:
    teams = row.get("teams") or {}
    source_home = football_form_team_key((teams.get("home") or {}).get("name"))
    source_away = football_form_team_key((teams.get("away") or {}).get("name"))
    return source_home == football_form_team_key(home) and source_away == football_form_team_key(away)


def player_saves(payload: dict[str, Any], goalkeeper: str) -> tuple[int | None, dict[str, Any]]:
    matches: list[tuple[int, int, dict[str, Any]]] = []
    for team in payload.get("response") or []:
        for item in team.get("players") or []:
            player = item.get("player") or {}
            score = person_match_score(goalkeeper, player.get("name"))
            if not score:
                continue
            for stats in item.get("statistics") or []:
                games = stats.get("games") or {}
                goals = stats.get("goals") or {}
                saves = goals.get("saves")
                parsed_saves = parse_float(saves)
                if (isinstance(saves, bool) or parsed_saves is None
                        or parsed_saves < 0 or not parsed_saves.is_integer()):
                    continue
                if str(games.get("position") or "").upper() not in {"G", "GK"}:
                    continue
                actual = int(parsed_saves)
                matches.append(
                    (
                        score,
                        actual,
                        {
                            "player_id": player.get("id"),
                            "player_name": player.get("name"),
                            "minutes": games.get("minutes"),
                            "position": games.get("position"),
                            "substitute": games.get("substitute"),
                        },
                    )
                )
    if not matches:
        return None, {}
    matches.sort(key=lambda item: item[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return None, {"error": "ambiguous_player"}
    return matches[0][1], matches[0][2]


def latest_close(
    odds_rows: list[dict[str, str]],
    signal: dict[str, str],
) -> float | None:
    def timestamp(value: object) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    created_at = timestamp(signal.get("created_at"))
    kickoff_at = timestamp(signal.get("kickoff_at"))
    if created_at is None or kickoff_at is None:
        return None
    candidates: list[tuple[datetime, float]] = []
    for row in odds_rows:
        if str(row.get("event_id") or "") != str(signal.get("event_id") or ""):
            continue
        if str(row.get("line") or "") != str(signal.get("line") or ""):
            continue
        if str(row.get("side") or "").casefold() != str(signal.get("side") or "").casefold():
            continue
        if person_match_score(row.get("player"), signal.get("goalkeeper")) < 80:
            continue
        if str(row.get("capture_mode") or "").casefold() != "close":
            continue
        captured_at = timestamp(row.get("captured_at"))
        if captured_at is None or captured_at <= created_at or captured_at >= kickoff_at:
            continue
        if kickoff_at - captured_at > timedelta(minutes=120):
            continue
        price = parse_float(row.get("odds_decimal"))
        if price and price > 1.0:
            candidates.append((captured_at, price))
    return max(candidates)[1] if candidates else None


def settle_row(
    signal: dict[str, str],
    actual: int,
    close_odds: float | None,
    settled_at: str,
    source: str = "api_football_fixture_players",
) -> None:
    line = parse_float(signal.get("line")) or 0.0
    price = parse_float(signal.get("odds_decimal")) or 0.0
    stake = parse_float(signal.get("stake_units")) or 0.0
    side = str(signal.get("side") or "over").casefold()
    won = actual > line if side == "over" else actual < line
    lost = actual < line if side == "over" else actual > line
    if won:
        result, pnl = "won", stake * (price - 1.0)
    elif lost:
        result, pnl = "lost", -stake
    else:
        result, pnl = "push", 0.0
    signal.update(
        {
            "status": result,
            "result": result,
            "actual_saves": str(actual),
            "pnl_units": f"{pnl:.4f}",
            "settled_at": settled_at,
            "settlement_source": source,
            "close_odds": f"{close_odds:.4f}" if close_odds else "",
            "clv": f"{(price / close_odds) - 1.0:.6f}" if close_odds else "",
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle Goalkeeper Saves v1 shadow signals")
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--odds", type=Path, default=DEFAULT_ODDS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-requests", type=int, default=10)
    parser.add_argument("--max-fotmob-requests", type=int, default=50)
    parser.add_argument("--api-football-fallback", action="store_true")
    args = parser.parse_args()
    load_env()

    fields, signals = read_csv(args.signals)
    generated_at = iso_utc()
    if not signals:
        write_report(args.report, {"generated_at": generated_at, "status": "NO_SIGNALS", "settled": 0, "reason_counts": {}})
        print("No goalkeeper-save shadow signals to settle.")
        return
    reviewed_voids = apply_reviewed_voids(signals, ROOT, goalkeeper=True)
    if reviewed_voids:
        write_csv(args.signals, fields, signals)
    pending = [row for row in signals if str(row.get("status") or "").lower() == "pending"]
    now_dt = datetime.now(UTC)
    deferred = [row for row in pending if not signal_is_due(row, now_dt)]
    pending = [row for row in pending if signal_is_due(row, now_dt)]
    if not pending:
        write_report(
            args.report,
            {
                "generated_at": generated_at,
                "status": "NOTHING_DUE",
                "pending_total": len(deferred),
                "pending_due": 0,
                "deferred_not_due": len(deferred),
                "settled": 0,
                "reviewed_voids": reviewed_voids,
                "requests_used": 0,
                "max_requests": args.max_requests,
                "reason_counts": {"not_due": len(deferred)} if deferred else {},
            },
        )
        print("No due goalkeeper-save shadow signals.")
        return

    odds_rows = read_csv(args.odds)[1]
    requests_used = 0
    fotmob_requests_used = 0
    settled = 0
    reasons: Counter[str] = Counter()
    details: list[dict[str, str]] = []
    api_errors: list[str] = []
    now = generated_at

    def record(signal: dict[str, str], reason: str, detail: str = "") -> None:
        reasons[reason] += 1
        details.append(
            {
                "signal_id": str(signal.get("signal_id") or ""),
                "match_date": str(signal.get("match_date") or ""),
                "match": f"{signal.get('home_team', '')} vs {signal.get('away_team', '')}",
                "goalkeeper": str(signal.get("goalkeeper") or ""),
                "reason": reason,
                "detail": detail,
            }
        )

    unresolved: list[dict[str, str]] = []
    date_cache: dict[str, dict[str, Any]] = {}
    match_cache: dict[int, dict[str, Any]] = {}
    target_capture: list[dict[str, Any]] = []
    for signal in pending:
        league = str(signal.get("league") or "")
        day_text = str(signal.get("match_date") or "")[:10]
        if league not in FOTMOB_LEAGUES:
            record(signal, "fotmob_unsupported_league", league)
            unresolved.append(signal)
            continue
        if day_text not in date_cache:
            if fotmob_requests_used >= args.max_fotmob_requests:
                record(signal, "fotmob_request_budget_exhausted")
                unresolved.append(signal)
                continue
            try:
                fotmob_requests_used += 1
                date_cache[day_text] = request_fotmob_json(
                    FOTMOB_MATCHES_URL,
                    {"date": day_text.replace("-", "")},
                )
            except Exception as exc:
                record(signal, "fotmob_fixture_request_failed", str(exc)[:240])
                unresolved.append(signal)
                continue
        fixtures = fotmob_fixtures(date_cache[day_text], league)
        fixture = next(
            (
                row
                for row in fixtures
                if fotmob_fixture_match(row, signal.get("home_team", ""), signal.get("away_team", ""))
                and bool((row.get("status") or {}).get("finished"))
            ),
            None,
        )
        match_id = int((fixture or {}).get("id") or 0)
        if match_id <= 0:
            record(signal, "fotmob_finished_fixture_not_found", f"fixtures_returned={len(fixtures)}")
            unresolved.append(signal)
            continue
        if match_id not in match_cache:
            if fotmob_requests_used + 1 > args.max_fotmob_requests:
                record(signal, "fotmob_request_budget_exhausted")
                unresolved.append(signal)
                continue
            try:
                fotmob_requests_used += 1
                fetched = request_fotmob_match_payload(match_id)
                validate_fotmob_fixture(fetched, fixture, day_text)
                match_cache[match_id] = fetched
                # Reuse the existing response; target collection adds no requests.
                try:
                    target_capture.append(archive_observed_targets(
                        match_cache[match_id], args.signals.parent / "verified-player-targets", match_id))
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    # An optional research archive must never decide a bet result.
                    target_capture.append({"status": "rejected", "match_id": match_id,
                                           "reason": str(exc)[:240]})
            except Exception as exc:
                record(signal, "fotmob_match_request_failed", str(exc)[:240])
                unresolved.append(signal)
                continue
        actual, metadata = fotmob_player_saves(match_cache[match_id], str(signal.get("goalkeeper") or ""))
        if actual is None:
            record(signal, str(metadata.get("error") or "fotmob_goalkeeper_stats_not_found"))
            unresolved.append(signal)
            continue
        settle_row(
            signal,
            actual,
            latest_close(odds_rows, signal),
            now,
            source="fotmob_named_keeper_shotmap",
        )
        settled += 1
        record(signal, "settled_fotmob")

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    if args.api_football_fallback:
        for signal in unresolved:
            groups[(str(signal.get("league") or ""), str(signal.get("match_date") or "")[:10])].append(signal)

    for (league, day_text), group in sorted(groups.items()):
        if league not in LEAGUES:
            for signal in group:
                record(signal, "unsupported_league", league)
            continue
        if requests_used >= args.max_requests:
            for signal in group:
                record(signal, "request_budget_exhausted")
            continue
        day = date.fromisoformat(day_text)
        try:
            fixture_payload = request_json(
                "fixtures",
                {"league": LEAGUES[league], "season": season_for_day(day), "date": day_text, "status": "FT-AET-PEN"},
            )
            requests_used += 1
        except Exception as exc:  # Network/API failure must remain visible in the evidence report.
            for signal in group:
                record(signal, "fixture_request_failed", str(exc)[:240])
            continue
        fixture_errors = api_error_messages(fixture_payload)
        if fixture_errors:
            api_errors.extend(fixture_errors)
            for signal in group:
                record(signal, "fixture_api_error", "; ".join(fixture_errors)[:240])
            continue
        fixtures = fixture_payload.get("response") or []
        for signal in group:
            if requests_used >= args.max_requests:
                record(signal, "request_budget_exhausted")
                continue
            fixture = next(
                (
                    row for row in fixtures
                    if fixture_match(row, signal.get("home_team", ""), signal.get("away_team", ""))
                    and str(((row.get("fixture") or {}).get("status") or {}).get("short") or "") in FINISHED
                ),
                None,
            )
            fixture_id = ((fixture or {}).get("fixture") or {}).get("id")
            if not fixture_id:
                record(signal, "finished_fixture_not_found", f"fixtures_returned={len(fixtures)}")
                continue
            try:
                players_payload = request_json("fixtures/players", {"fixture": fixture_id})
                requests_used += 1
            except Exception as exc:  # Keep the signal pending and explain why.
                record(signal, "player_stats_request_failed", str(exc)[:240])
                continue
            player_errors = api_error_messages(players_payload)
            if player_errors:
                api_errors.extend(player_errors)
                record(signal, "player_stats_api_error", "; ".join(player_errors)[:240])
                continue
            actual, metadata = player_saves(players_payload, str(signal.get("goalkeeper") or ""))
            if actual is None:
                record(signal, str(metadata.get("error") or "goalkeeper_stats_not_found"))
                continue
            # The signal gate already required a confirmed starter. The player
            # payload must independently identify a goalkeeper, not an outfield
            # name collision.
            if str(metadata.get("position") or "").upper() not in {"G", "GK", "GOALKEEPER"}:
                record(signal, "matched_player_not_goalkeeper", str(metadata.get("position") or ""))
                continue
            settle_row(signal, actual, latest_close(odds_rows, signal), now)
            settled += 1
            record(signal, "settled_api_football")

    write_csv(args.signals, fields, signals)
    remaining_due = sum(str(row.get("status") or "").casefold() == "pending" for row in pending)
    status = "SETTLED" if settled and remaining_due == 0 else "PARTIAL" if settled else "BLOCKED"
    report = {
        "generated_at": generated_at,
        "status": status,
        "pending_total": remaining_due + len(deferred),
        "pending_due": remaining_due,
        "deferred_not_due": len(deferred),
        "settled": settled,
        "requests_used": requests_used,
        "max_requests": args.max_requests,
        "verified_player_targets": target_capture,
        "fotmob_requests_used": fotmob_requests_used,
        "max_fotmob_requests": args.max_fotmob_requests,
        "reason_counts": dict(sorted(reasons.items())),
        "api_errors": sorted(set(api_errors)),
        "details": details,
    }
    write_report(args.report, report)
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, sort_keys=True))


if __name__ == "__main__":
    main()
