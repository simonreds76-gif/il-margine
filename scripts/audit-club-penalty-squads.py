#!/usr/bin/env python3
"""Check every published club penalty taker against current FotMob squads.

This is a membership gate, not a penalty-order model. Missing players are sent
to an explicit review report so a transfer cannot remain silently published.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "goalscorer"
MANIFEST_PATH = DATA_DIR / "team-logo-map.json"
DEFAULT_JSON_OUTPUT = DATA_DIR / "club-penalty-squad-audit.json"
DEFAULT_CSV_OUTPUT = DATA_DIR / "club-penalty-squad-audit.csv"
LEAGUE_FILES = {
    "epl": DATA_DIR / "epl-penalty-takers.json",
    "la-liga": DATA_DIR / "la-liga-penalty-takers.json",
    "serie-a": DATA_DIR / "serie-a-penalty-takers.json",
    "bundesliga": DATA_DIR / "bundesliga-penalty-takers.json",
    "ligue-1": DATA_DIR / "ligue-1-penalty-takers.json",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}
TRANSLITERATION = str.maketrans(
    {
        "ø": "o",
        "Ø": "O",
        "ð": "d",
        "Ð": "D",
        "ı": "i",
        "ł": "l",
        "Ł": "L",
        "đ": "d",
        "Đ": "D",
        "ß": "ss",
        "æ": "ae",
        "Æ": "AE",
        "œ": "oe",
        "Œ": "OE",
        "þ": "th",
        "Þ": "Th",
    }
)
NAME_ALIASES = {
    "alex baena": "alejandro baena",
    "antoni martinez": "toni martinez",
    "chris wood": "christopher wood",
    "cucho hernandez": "juan hernandez",
    "fabio carvalho": "fabio daniel carvalho",
    "jota silva": "joao pedro ferreira silva",
    "junior adamu": "chukwubuike adamu",
    "lucas da cunha": "lucas da cunha",
    "nico williams": "nicholas williams",
    "matt o riley": "matthew o riley",
    "peque fernandez": "gerard fernandez",
    "tasos douvikas": "anastasios douvikas",
    "ben lhassine kone": "benjamin lhassine kone",
    "giovane": "giovane nascimento",
    "vitinha": "vitor manuel carvalho oliveira",
}


class NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.payload: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and values.get("id") == "__NEXT_DATA__":
            self.capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.capture:
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.payload.append(data)


def normalize_name(value: str) -> str:
    value = (value or "").translate(TRANSLITERATION)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return NAME_ALIASES.get(value, value)


def extract_team_payload(html_text: str, team_id: int) -> dict[str, Any]:
    parser = NextDataParser()
    parser.feed(html_text)
    if not parser.payload:
        raise ValueError("FotMob page has no __NEXT_DATA__ payload")
    payload = json.loads("".join(parser.payload))
    fallback = payload.get("props", {}).get("pageProps", {}).get("fallback", {})
    team_payload = fallback.get(f"team-{team_id}")
    if not isinstance(team_payload, dict):
        raise ValueError(f"FotMob payload has no team-{team_id} entry")
    return team_payload


def squad_names(team_payload: dict[str, Any]) -> list[str]:
    groups = team_payload.get("squad", {}).get("squad", [])
    names: list[str] = []
    for group in groups if isinstance(groups, list) else []:
        if str(group.get("title") or "").lower() == "coach":
            continue
        for member in group.get("members") or []:
            name = str(member.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def match_player(player: str, current_squad: list[str]) -> tuple[str, str]:
    target = normalize_name(player)
    normalized = {normalize_name(name): name for name in current_squad}
    if target in normalized:
        return "present", normalized[target]

    target_tokens = set(target.split())
    candidates = []
    for key, original in normalized.items():
        tokens = set(key.split())
        if len(target_tokens) >= 2 and target_tokens.issubset(tokens):
            candidates.append(original)
        elif len(tokens) >= 2 and tokens.issubset(target_tokens):
            candidates.append(original)
    if len(candidates) == 1:
        return "present", candidates[0]
    if len(candidates) > 1:
        return "ambiguous", " | ".join(sorted(candidates))
    return "missing", ""


def closest_squad_names(player: str, current_squad: list[str]) -> str:
    normalized = {normalize_name(name): name for name in current_squad}
    matches = difflib.get_close_matches(normalize_name(player), list(normalized), n=3, cutoff=0.55)
    return " | ".join(normalized[name] for name in matches)


def fetch_team_squad(team_id: int, page_url: str, timeout: int) -> list[str]:
    url = f"https://www.fotmob.com{page_url}" if page_url.startswith("/") else page_url
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            response.encoding = "utf-8"
            names = squad_names(extract_team_payload(response.text, team_id))
            if not names:
                raise ValueError("FotMob squad is empty")
            return names
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 + attempt)
    raise RuntimeError(str(last_error) if last_error else "unknown FotMob fetch failure")


def load_jobs(leagues: list[str]) -> list[dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs: list[dict[str, Any]] = []
    for league in leagues:
        hierarchy = json.loads(LEAGUE_FILES[league].read_text(encoding="utf-8"))
        manifest_teams = manifest.get("leagues", {}).get(league, {}).get("teams", {})
        for club, entry in hierarchy.items():
            if club.startswith("_") or not isinstance(entry, dict):
                continue
            mapping = manifest_teams.get(club) or {}
            jobs.append(
                {
                    "league": league,
                    "club": club,
                    "entry": entry,
                    "team_id": int(mapping.get("fotmob_team_id") or 0),
                    "page_url": str(mapping.get("page_url") or ""),
                }
            )
    return jobs


def build_audit(leagues: list[str], timeout: int, workers: int) -> dict[str, Any]:
    jobs = load_jobs(leagues)
    fetched: dict[tuple[str, str], tuple[list[str], str]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 6))) as pool:
        futures = {}
        for job in jobs:
            key = (job["league"], job["club"])
            if not job["team_id"] or not job["page_url"]:
                fetched[key] = ([], "missing FotMob team mapping")
                continue
            future = pool.submit(fetch_team_squad, job["team_id"], job["page_url"], timeout)
            futures[future] = key
        for future in as_completed(futures):
            key = futures[future]
            try:
                fetched[key] = (future.result(), "")
            except RuntimeError as exc:
                fetched[key] = ([], str(exc))

    rows: list[dict[str, Any]] = []
    for job in jobs:
        key = (job["league"], job["club"])
        current_squad, error = fetched.get(key, ([], "missing fetch result"))
        for rank in ("primary", "secondary", "tertiary"):
            player = str(job["entry"].get(rank) or "").strip()
            status, matched_name = ("fetch_error", "") if error else match_player(player, current_squad)
            rows.append(
                {
                    "league": job["league"],
                    "club": job["club"],
                    "rank": rank,
                    "player": player,
                    "status": status,
                    "matched_squad_name": matched_name,
                    "closest_squad_names": closest_squad_names(player, current_squad) if not error else "",
                    "fotmob_team_id": job["team_id"],
                    "source_url": f"https://www.fotmob.com{job['page_url']}",
                    "error": error,
                }
            )

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "FotMob current club squad payloads",
        "scope": "membership only; hierarchy order still requires editorial evidence",
        "clubs_checked": len(jobs),
        "slots_checked": len(rows),
        "status_counts": status_counts,
        "club_squads": {
            f"{league}|{club}": names
            for (league, club), (names, error) in sorted(fetched.items())
            if not error
        },
        "rows": rows,
    }


def write_outputs(payload: dict[str, Any], json_output: Path, csv_output: Path) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = [
        "league",
        "club",
        "rank",
        "player",
        "status",
        "matched_squad_name",
        "closest_squad_names",
        "fotmob_team_id",
        "source_url",
        "error",
    ]
    with csv_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(payload["rows"])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Audit club penalty takers against current FotMob squads")
    parser.add_argument("--league", choices=sorted(LEAGUE_FILES), nargs="+", default=sorted(LEAGUE_FILES))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    args = parser.parse_args()

    payload = build_audit(args.league, args.timeout, args.workers)
    write_outputs(payload, args.json_output, args.csv_output)
    print(
        f"Checked {payload['clubs_checked']} clubs / {payload['slots_checked']} hierarchy slots: "
        + ", ".join(f"{key}={value}" for key, value in sorted(payload["status_counts"].items()))
    )
    for row in payload["rows"]:
        if row["status"] != "present":
            print(f"- {row['status'].upper()} {row['league']} | {row['club']} | {row['rank']} | {row['player']}")
    return 0 if payload["status_counts"] == {"present": payload["slots_checked"]} else 1


if __name__ == "__main__":
    raise SystemExit(main())
