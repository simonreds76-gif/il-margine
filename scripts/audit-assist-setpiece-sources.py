#!/usr/bin/env python3
"""Audit live set-piece role sources for the Assist Value Lab.

This is research-only. It does not touch production data, public UI, or any
existing goalscorer pipeline output. The script answers one question:

Can we obtain current, player-level corner/free-kick/penalty role data that is
good enough to support an assist-value shadow lane?
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

ROTOWIRE_DEPTH_CHARTS = {
    "epl": "https://www.rotowire.com/soccer/premier-league-depth-charts-1/",
    "bundesliga": "https://www.rotowire.com/soccer/bundesliga-depth-charts-2/",
    "ligue-1": "https://www.rotowire.com/soccer/ligue-1-depth-charts-3/",
    "la-liga": "https://www.rotowire.com/soccer/la-liga-depth-charts-5/",
    "serie-a": "https://www.rotowire.com/soccer/serie-a-depth-charts-6/",
}

SETPIECETAKERS_LEAGUES = ["premier-league", "bundesliga", "la-liga", "serie-a", "ligue-1"]
SETPIECETAKERS_CATEGORIES = ["corners", "freekicks", "penalties"]

FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: int | None
    text: str
    error: str = ""


def fetch_text(url: str, *, timeout: int = 25, retries: int = 2, pause: float = 0.5) -> FetchResult:
    last_error = ""
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as response:
                raw = response.read()
                status = getattr(response, "status", None)
            return FetchResult(url=url, ok=True, status=status, text=raw.decode("utf-8", "replace"))
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.reason}"
            if 400 <= exc.code < 500:
                return FetchResult(url=url, ok=False, status=exc.code, text="", error=last_error)
        except (URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        if attempt < retries:
            time.sleep(pause * (attempt + 1))
    return FetchResult(url=url, ok=False, status=None, text="", error=last_error)


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def intish(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = clean_text(str(value))
    return int(text) if text.isdigit() else 0


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


def parse_rotowire_depth_chart(page: str) -> list[dict[str, str]]:
    blocks = re.findall(
        r'<div class="depth-charts__block">(.*?)(?=<div class="depth-charts__block">|</main>|<footer)',
        page,
        re.S,
    )
    teams: list[dict[str, str]] = []
    for block in blocks:
        team_match = re.search(r'<div class="depth-charts__team-name">([^<]+)</div>', block)
        player_match = re.search(r'href="(/soccer/player/[^"]+)"', block)
        if not team_match or not player_match:
            continue
        teams.append(
            {
                "team": clean_text(team_match.group(1)),
                "sample_player_url": "https://www.rotowire.com" + player_match.group(1),
            }
        )
    return teams


def parse_rotowire_setpiece_page(page: str) -> tuple[str, list[dict[str, Any]], int]:
    team_match = re.search(
        r'<img[^>]+alt="([^"]+)">([^<]*?)\s*2025&nbsp;<span[^>]*>Set Piece Crosses and Shots',
        page,
        re.S,
    )
    rotowire_team = clean_text(team_match.group(1)) if team_match else ""

    data_match = re.search(r"var data = (\[.*?\]);", page, re.S)
    if not data_match:
        return rotowire_team, [], 0

    try:
        rows = json.loads(data_match.group(1))
    except json.JSONDecodeError:
        return rotowire_team, [], 0

    weeks: set[int] = set()
    for row in rows:
        for key in row:
            match = re.fullmatch(r"(?:wk|corners|freeKicks|penalties)(\d+)", key)
            if match:
                weeks.add(int(match.group(1)))
    latest_week = max(weeks) if weeks else 0
    last_weeks = sorted(weeks)[-5:]

    team_totals = {
        "total": sum(intish(row.get("total")) for row in rows),
        "corners": sum(intish(row.get("cornersTotal")) for row in rows),
        "free_kicks": sum(intish(row.get("freeKicksTotal")) for row in rows),
        "penalties": sum(intish(row.get("penaltiesTotal")) for row in rows),
        "last5_total": 0,
        "last5_corners": 0,
        "last5_free_kicks": 0,
        "last5_penalties": 0,
    }

    for row in rows:
        for week in last_weeks:
            team_totals["last5_total"] += intish(row.get(f"wk{week}"))
            team_totals["last5_corners"] += intish(row.get(f"corners{week}"))
            team_totals["last5_free_kicks"] += intish(row.get(f"freeKicks{week}"))
            team_totals["last5_penalties"] += intish(row.get(f"penalties{week}"))

    parsed_rows: list[dict[str, Any]] = []
    for row in rows:
        player_name = row.get("nickname") or f"{row.get('firstname', '')} {row.get('lastname', '')}".strip()
        last5 = {
            "total": sum(intish(row.get(f"wk{week}")) for week in last_weeks),
            "corners": sum(intish(row.get(f"corners{week}")) for week in last_weeks),
            "free_kicks": sum(intish(row.get(f"freeKicks{week}")) for week in last_weeks),
            "penalties": sum(intish(row.get(f"penalties{week}")) for week in last_weeks),
        }
        parsed_rows.append(
            {
                "player_name": clean_text(str(player_name)),
                "player_url": "https://www.rotowire.com" + str(row.get("URL", "")),
                "total_setpieces": intish(row.get("total")),
                "corner_total": intish(row.get("cornersTotal")),
                "fk_total": intish(row.get("freeKicksTotal")),
                "penalty_total": intish(row.get("penaltiesTotal")),
                "latest_week": latest_week,
                "last5_weeks": ",".join(str(week) for week in last_weeks),
                "last5_setpieces": last5["total"],
                "last5_corners": last5["corners"],
                "last5_free_kicks": last5["free_kicks"],
                "last5_penalties": last5["penalties"],
                "total_share_pct": pct(intish(row.get("total")), team_totals["total"]),
                "corner_share_total_pct": pct(intish(row.get("cornersTotal")), team_totals["corners"]),
                "fk_share_total_pct": pct(intish(row.get("freeKicksTotal")), team_totals["free_kicks"]),
                "penalty_share_total_pct": pct(intish(row.get("penaltiesTotal")), team_totals["penalties"]),
                "setpiece_share_last5_pct": pct(last5["total"], team_totals["last5_total"]),
                "corner_share_last5_pct": pct(last5["corners"], team_totals["last5_corners"]),
                "fk_share_last5_pct": pct(last5["free_kicks"], team_totals["last5_free_kicks"]),
                "penalty_share_last5_pct": pct(last5["penalties"], team_totals["last5_penalties"]),
            }
        )
    return rotowire_team, parsed_rows, latest_week


def audit_rotowire(timeout: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    role_rows: list[dict[str, Any]] = []
    team_status: list[dict[str, Any]] = []
    for league, url in ROTOWIRE_DEPTH_CHARTS.items():
        depth = fetch_text(url, timeout=timeout)
        if not depth.ok:
            team_status.append(
                {
                    "source": "rotowire",
                    "league": league,
                    "team": "",
                    "ok": False,
                    "reason": f"depth_chart_fetch_failed: {depth.error}",
                    "sample_player_url": "",
                    "role_rows": 0,
                    "latest_week": 0,
                }
            )
            continue
        teams = parse_rotowire_depth_chart(depth.text)
        for team in teams:
            page = fetch_text(team["sample_player_url"], timeout=timeout)
            if not page.ok:
                team_status.append(
                    {
                        "source": "rotowire",
                        "league": league,
                        "team": team["team"],
                        "ok": False,
                        "reason": f"player_page_fetch_failed: {page.error}",
                        "sample_player_url": team["sample_player_url"],
                        "role_rows": 0,
                        "latest_week": 0,
                    }
                )
                continue
            rotowire_team, parsed_rows, latest_week = parse_rotowire_setpiece_page(page.text)
            ok = bool(parsed_rows)
            team_status.append(
                {
                    "source": "rotowire",
                    "league": league,
                    "team": team["team"],
                    "rotowire_team": rotowire_team,
                    "ok": ok,
                    "reason": "ok" if ok else "missing_setpiece_data",
                    "sample_player_url": team["sample_player_url"],
                    "role_rows": len(parsed_rows),
                    "latest_week": latest_week,
                }
            )
            for row in parsed_rows:
                role_rows.append(
                    {
                        "source": "rotowire",
                        "league": league,
                        "team": team["team"],
                        "rotowire_team": rotowire_team,
                        **row,
                    }
                )
    return role_rows, team_status


def audit_fpl(timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fetched = fetch_text(FPL_BOOTSTRAP_URL, timeout=timeout)
    if not fetched.ok:
        return [], {"source": "fpl_api", "ok": False, "reason": fetched.error, "players_with_roles": 0}
    data = json.loads(fetched.text)
    teams = {team["id"]: team["name"] for team in data.get("teams", [])}
    role_rows: list[dict[str, Any]] = []
    for player in data.get("elements", []):
        corner_order = player.get("corners_and_indirect_freekicks_order")
        direct_fk_order = player.get("direct_freekicks_order")
        penalty_order = player.get("penalties_order")
        if corner_order is None and direct_fk_order is None and penalty_order is None:
            continue
        role_rows.append(
            {
                "source": "fpl_api",
                "league": "epl",
                "team": teams.get(player.get("team"), ""),
                "player_name": player.get("web_name", ""),
                "element_id": player.get("id", ""),
                "corner_indirect_fk_order": corner_order if corner_order is not None else "",
                "direct_fk_order": direct_fk_order if direct_fk_order is not None else "",
                "penalty_order": penalty_order if penalty_order is not None else "",
                "status": player.get("status", ""),
                "chance_of_playing_next_round": player.get("chance_of_playing_next_round", ""),
                "now_cost": player.get("now_cost", ""),
            }
        )
    status = {
        "source": "fpl_api",
        "ok": bool(role_rows),
        "reason": "ok" if role_rows else "no_role_rows",
        "teams": len(teams),
        "players": len(data.get("elements", [])),
        "players_with_roles": len(role_rows),
    }
    return role_rows, status


def audit_setpiecetakers(timeout: int) -> list[dict[str, Any]]:
    status_rows: list[dict[str, Any]] = []
    for category in SETPIECETAKERS_CATEGORIES:
        for league in SETPIECETAKERS_LEAGUES:
            url = f"https://data.setpiecetakers.com/{category}/{league}"
            fetched = fetch_text(url, timeout=timeout)
            row: dict[str, Any] = {
                "source": "setpiecetakers",
                "category": category,
                "league": league,
                "url": url,
                "ok": fetched.ok,
                "visible_updated": "",
                "row_update_days": "",
                "rows": 0,
                "unique_clubs": 0,
                "csv_button_disabled": "",
                "reason": "ok" if fetched.ok else fetched.error,
            }
            if fetched.ok:
                visible = re.search(r"Updated <!-- -->([^<]+)", fetched.text)
                row["visible_updated"] = visible.group(1).strip() if visible else ""
                updates = re.findall(r'\\"updated_at\\":\\"([^"\\]+)', fetched.text)
                update_days = sorted({item[:10] for item in updates if len(item) >= 10})
                clubs = re.findall(r'\\"club\\":\\"([^"\\]+)', fetched.text)
                row["row_update_days"] = ",".join(update_days)
                row["rows"] = len(updates)
                row["unique_clubs"] = len(set(clubs))
                row["csv_button_disabled"] = (
                    "true" if "CSV export coming soon" in fetched.text or "btn-disabled" in fetched.text else "false"
                )
                if "2026-03-20" in update_days or row["visible_updated"] == "20 Mar 2026":
                    row["reason"] = "stale_march_20"
            status_rows.append(row)
    return status_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_report(
    *,
    out_dir: Path,
    rotowire_rows: list[dict[str, Any]],
    rotowire_status: list[dict[str, Any]],
    fpl_rows: list[dict[str, Any]],
    fpl_status: dict[str, Any],
    spt_status: list[dict[str, Any]],
    fetched_at: str,
) -> tuple[str, dict[str, Any]]:
    rotowire_teams = len(rotowire_status)
    rotowire_ok = sum(1 for row in rotowire_status if row.get("ok"))
    rotowire_pass = rotowire_teams > 0 and rotowire_ok == rotowire_teams
    fpl_pass = bool(fpl_status.get("ok")) and int(fpl_status.get("players_with_roles", 0)) > 0
    spt_fresh_rows = [
        row
        for row in spt_status
        if row.get("ok") and row.get("reason") != "stale_march_20" and row.get("csv_button_disabled") == "false"
    ]
    spt_pass = len(spt_fresh_rows) == len(spt_status) if spt_status else False

    by_league: dict[str, dict[str, Any]] = {}
    for row in rotowire_status:
        league = str(row.get("league", ""))
        item = by_league.setdefault(league, {"teams": 0, "ok": 0, "role_rows": 0, "max_latest_week": 0})
        item["teams"] += 1
        item["ok"] += 1 if row.get("ok") else 0
        item["role_rows"] += int(row.get("role_rows") or 0)
        item["max_latest_week"] = max(item["max_latest_week"], int(row.get("latest_week") or 0))

    top_corner_rows = sorted(rotowire_rows, key=lambda row: float(row.get("corner_share_last5_pct") or 0), reverse=True)[
        :15
    ]

    json_report = {
        "fetched_at_utc": fetched_at,
        "overall_decision": "PASS_SOURCE_LAYER" if rotowire_pass and fpl_pass else "FAIL_SOURCE_LAYER",
        "production_guard": "research_only_no_public_assist_picks_authorised",
        "rotowire_scope_caveat": (
            "RotoWire set-piece weeks can exceed domestic league matchweeks; use the feed for current role inference, "
            "not as a league-only historical volume source."
        ),
        "rotowire": {
            "pass": rotowire_pass,
            "teams_ok": rotowire_ok,
            "teams_total": rotowire_teams,
            "role_rows": len(rotowire_rows),
            "by_league": by_league,
        },
        "fpl_api": fpl_status | {"pass": fpl_pass},
        "setpiecetakers": {
            "pass": spt_pass,
            "pages_checked": len(spt_status),
            "stale_pages": sum(1 for row in spt_status if row.get("reason") == "stale_march_20"),
            "csv_disabled_pages": sum(1 for row in spt_status if row.get("csv_button_disabled") == "true"),
        },
        "outputs": {
            "rotowire_roles": str(out_dir / "rotowire-setpiece-roles.csv"),
            "rotowire_status": str(out_dir / "rotowire-source-status.csv"),
            "fpl_roles": str(out_dir / "fpl-setpiece-roles.csv"),
            "setpiecetakers_status": str(out_dir / "setpiecetakers-source-status.csv"),
        },
    }

    lines = [
        "# Assist Value Set-Piece Source Audit",
        "",
        f"Fetched at UTC: `{fetched_at}`",
        "",
        "## Decision",
        "",
        f"Overall: **{json_report['overall_decision']}**",
        "",
        "- RotoWire public player pages are accepted as the primary Big-5 role source if every team returns a set-piece block.",
        "- Official FPL API is accepted as the Premier League validator if it returns current set-piece order fields.",
        "- SetPieceTakers is rejected as a live primary while row timestamps are stale and CSV export is disabled.",
        "- RotoWire week numbers can exceed domestic league matchweeks, so the feed is a role source, not a league-only historical-volume source.",
        "",
        "## RotoWire",
        "",
        f"- Teams with set-piece blocks: `{rotowire_ok}/{rotowire_teams}`",
        f"- Player role rows extracted: `{len(rotowire_rows)}`",
        "",
        "| League | Teams OK | Teams | Role rows | Max latest week |",
        "|---|---:|---:|---:|---:|",
    ]
    for league, item in sorted(by_league.items()):
        lines.append(
            f"| {league} | {item['ok']} | {item['teams']} | {item['role_rows']} | {item['max_latest_week']} |"
        )

    lines.extend(
        [
            "",
            "## FPL API",
            "",
            f"- Status: `{'PASS' if fpl_pass else 'FAIL'}`",
            f"- Teams: `{fpl_status.get('teams', 0)}`",
            f"- Players: `{fpl_status.get('players', 0)}`",
            f"- Players with set-piece role fields: `{fpl_status.get('players_with_roles', 0)}`",
            "",
            "## SetPieceTakers",
            "",
            f"- Pages checked: `{len(spt_status)}`",
            f"- Stale March 20 pages: `{json_report['setpiecetakers']['stale_pages']}`",
            f"- CSV-disabled pages: `{json_report['setpiecetakers']['csv_disabled_pages']}`",
            f"- Decision: `{'PASS' if spt_pass else 'REJECT_AS_LIVE_PRIMARY'}`",
            "",
            "## Top Last-5 Corner Role Shares From RotoWire",
            "",
            "| League | Team | Player | Last-5 corner share | Season corner share | Corner total |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for row in top_corner_rows:
        lines.append(
            "| {league} | {team} | {player} | {last5}% | {season}% | {total} |".format(
                league=row.get("league", ""),
                team=row.get("team", ""),
                player=row.get("player_name", ""),
                last5=row.get("corner_share_last5_pct", 0),
                season=row.get("corner_share_total_pct", 0),
                total=row.get("corner_total", 0),
            )
        )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- `{out_dir / 'rotowire-setpiece-roles.csv'}`",
            f"- `{out_dir / 'rotowire-source-status.csv'}`",
            f"- `{out_dir / 'fpl-setpiece-roles.csv'}`",
            f"- `{out_dir / 'setpiecetakers-source-status.csv'}`",
            f"- `{out_dir / 'setpiece-source-audit.json'}`",
            "",
            "## Production Guard",
            "",
            "No public Assist Value Lab picks are authorised by this audit. This only proves the source layer is viable enough to build a shadow model.",
        ]
    )
    return "\n".join(lines) + "\n", json_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="data/assist-value", type=Path)
    parser.add_argument("--timeout", default=25, type=int)
    args = parser.parse_args()

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Auditing RotoWire public set-piece blocks...", file=sys.stderr)
    rotowire_rows, rotowire_status = audit_rotowire(args.timeout)
    print("Auditing official FPL API set-piece order fields...", file=sys.stderr)
    fpl_rows, fpl_status = audit_fpl(args.timeout)
    print("Auditing SetPieceTakers freshness/export state...", file=sys.stderr)
    spt_status = audit_setpiecetakers(args.timeout)

    write_csv(out_dir / "rotowire-setpiece-roles.csv", rotowire_rows)
    write_csv(out_dir / "rotowire-source-status.csv", rotowire_status)
    write_csv(out_dir / "fpl-setpiece-roles.csv", fpl_rows)
    write_csv(out_dir / "setpiecetakers-source-status.csv", spt_status)

    report_md, report_json = build_report(
        out_dir=out_dir,
        rotowire_rows=rotowire_rows,
        rotowire_status=rotowire_status,
        fpl_rows=fpl_rows,
        fpl_status=fpl_status,
        spt_status=spt_status,
        fetched_at=fetched_at,
    )
    (out_dir / "setpiece-source-audit.md").write_text(report_md, encoding="utf-8")
    (out_dir / "setpiece-source-audit.json").write_text(
        json.dumps(report_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(report_json["overall_decision"])
    print(f"rotowire_teams_ok={report_json['rotowire']['teams_ok']}/{report_json['rotowire']['teams_total']}")
    print(f"rotowire_role_rows={report_json['rotowire']['role_rows']}")
    print(f"fpl_players_with_roles={report_json['fpl_api'].get('players_with_roles', 0)}")
    print(f"setpiecetakers_stale_pages={report_json['setpiecetakers']['stale_pages']}")
    return 0 if report_json["overall_decision"] == "PASS_SOURCE_LAYER" else 1


if __name__ == "__main__":
    raise SystemExit(main())
