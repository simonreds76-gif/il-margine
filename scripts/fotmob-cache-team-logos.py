#!/usr/bin/env python3
"""
Download and cache FotMob team logos for the penalty-takers reference pages.

The script:
  1. Reads league/team names from the existing penalty hierarchy JSON files
  2. Resolves each club to the correct FotMob team ID using the league table API
  3. Downloads each crest into public/team-logos/<league>/<team>.png
  4. Writes a reusable manifest to data/goalscorer/team-logo-map.json

This keeps the page local-first and avoids hotlinking club crests at render time.
"""

from __future__ import annotations

import argparse
import json
import re
import runpy
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "public" / "team-logos"
MANIFEST_PATH = ROOT / "data" / "goalscorer" / "team-logo-map.json"
FOTMOB_LEAGUES_URL = "https://www.fotmob.com/api/leagues"
FOTMOB_LOGO_URL = "https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fotmob.com/",
}

LOCAL_TEAM_ALIASES = {
    "bayern munchen": "bayern munich",
    "bayern muenchen": "bayern munich",
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "paris saint germain": "paris saint germain",
    "olympique lyonnais": "lyon",
    "olympique de marseille": "marseille",
    "olympique marseille": "marseille",
    "stade rennais": "rennes",
    "stade brestois": "brest",
    "stade brestois 29": "brest",
    "angers sco": "angers",
    "le havre ac": "le havre",
    "losc": "lille",
    "lille osc": "lille",
    "as monaco": "monaco",
    "ogc nice": "nice",
    "rc lens": "lens",
    "as saint etienne": "saint etienne",
    "saint etienne": "saint etienne",
    "koln": "fc cologne",
    "fc koln": "fc cologne",
    "cologne": "fc cologne",
}


@dataclass(frozen=True)
class TeamLookup:
    team_id: int
    fotmob_name: str
    fotmob_short_name: str
    page_url: str
    candidate_keys: Set[str]


def _load_team_key() -> callable:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    return model_mod["_team_key"]


def _load_league_configs() -> dict:
    pipeline_mod = runpy.run_path(
        str(ROOT / "scripts" / "run-goalscorer-pipeline.py"),
        run_name="goalscorer_pipeline",
    )
    return pipeline_mod["LEAGUE_CONFIGS"]


def _ascii_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return text.encode("ascii", "ignore").decode("ascii")


def _normalized_team_key(value: str, team_key_func) -> str:
    base_key = team_key_func(_ascii_text(value))
    return LOCAL_TEAM_ALIASES.get(base_key, base_key)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "team"


def _load_penalty_teams(path: Path) -> List[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.keys())


def _extract_table_rows(payload: dict) -> List[dict]:
    rows: List[dict] = []
    for section in payload.get("table", []):
        data = section.get("data") if isinstance(section, dict) else None
        if not isinstance(data, dict):
            continue
        table = data.get("table")
        if not isinstance(table, dict):
            continue
        for key in ("all", "home", "away"):
            values = table.get(key)
            if isinstance(values, list):
                rows.extend(values)
    deduped: Dict[int, dict] = {}
    for row in rows:
        try:
            team_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        deduped[team_id] = row
    return list(deduped.values())


def _page_url_key(page_url: str, team_key_func) -> Optional[str]:
    if not page_url:
        return None
    parts = [part for part in str(page_url).split("/") if part]
    if not parts:
        return None
    return _normalized_team_key(parts[-1].replace("-", " "), team_key_func)


def _build_team_lookup(rows: Iterable[dict], team_key_func) -> Dict[str, TeamLookup]:
    by_key: Dict[str, TeamLookup] = {}
    collisions: Dict[str, List[str]] = {}

    for row in rows:
        try:
            team_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        name = str(row.get("name") or "").strip()
        short_name = str(row.get("shortName") or "").strip()
        page_url = str(row.get("pageUrl") or "").strip()

        keys = {
            _normalized_team_key(name, team_key_func),
            _normalized_team_key(short_name, team_key_func),
        }
        page_key = _page_url_key(page_url, team_key_func)
        if page_key:
            keys.add(page_key)
        keys = {key for key in keys if key}

        lookup = TeamLookup(
            team_id=team_id,
            fotmob_name=name,
            fotmob_short_name=short_name,
            page_url=page_url,
            candidate_keys=keys,
        )
        for key in keys:
            existing = by_key.get(key)
            if existing and existing.team_id != lookup.team_id:
                collisions.setdefault(key, [existing.fotmob_name]).append(lookup.fotmob_name)
                continue
            by_key[key] = lookup

    if collisions:
        print("Warning: duplicate FotMob keys detected:")
        for key, names in sorted(collisions.items()):
            deduped = ", ".join(sorted(set(names)))
            print(f"  - {key}: {deduped}")

    return by_key


def _fetch_league_rows(session: requests.Session, league_id: int) -> List[dict]:
    response = session.get(
        FOTMOB_LEAGUES_URL,
        params={"id": league_id, "ccode3": "GBR"},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    payload = response.json()
    rows = _extract_table_rows(payload)
    if not rows:
        raise RuntimeError(f"Could not extract league table rows for FotMob league {league_id}")
    return rows


def _download_logo(session: requests.Session, team_id: int, output_path: Path) -> None:
    response = session.get(
        FOTMOB_LOGO_URL.format(team_id=team_id),
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)


def cache_logos(leagues: Iterable[str], force: bool) -> dict:
    team_key_func = _load_team_key()
    league_configs = _load_league_configs()
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "fotmob",
        "logo_base": "https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png",
        "leagues": {},
    }

    with requests.Session() as session:
        for league_slug in leagues:
            config = league_configs[league_slug]
            penalty_path = ROOT / config["penalty_hierarchy"]
            league_rows = _fetch_league_rows(session, int(config["league_id"]))
            lookup_by_key = _build_team_lookup(league_rows, team_key_func)

            league_manifest = {
                "label": config["label"],
                "league_id": config["league_id"],
                "teams": {},
            }
            missing: List[str] = []
            for team_name in _load_penalty_teams(penalty_path):
                team_key = _normalized_team_key(team_name, team_key_func)
                lookup = lookup_by_key.get(team_key)
                if not lookup:
                    missing.append(team_name)
                    continue

                file_slug = _slugify(team_key)
                relative_path = f"/team-logos/{league_slug}/{file_slug}.png"
                output_path = OUTPUT_DIR / league_slug / f"{file_slug}.png"
                if force or not output_path.exists():
                    _download_logo(session, lookup.team_id, output_path)

                league_manifest["teams"][team_name] = {
                    "team_key": team_key,
                    "fotmob_team_id": lookup.team_id,
                    "fotmob_name": lookup.fotmob_name,
                    "fotmob_short_name": lookup.fotmob_short_name,
                    "page_url": lookup.page_url,
                    "logo_path": relative_path,
                }

            if missing:
                missing_text = ", ".join(missing)
                raise RuntimeError(f"{league_slug}: could not resolve FotMob teams for: {missing_text}")

            manifest["leagues"][league_slug] = league_manifest
            print(f"{league_slug}: cached {len(league_manifest['teams'])} team logos")

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    league_configs = _load_league_configs()
    parser = argparse.ArgumentParser(description="Cache FotMob team logos locally for goalscorer pages")
    parser.add_argument(
        "--league",
        choices=sorted(league_configs),
        nargs="+",
        default=sorted(league_configs),
        help="League slug(s) to cache. Default: all configured leagues.",
    )
    parser.add_argument("--force", action="store_true", help="Redownload logos even if the local file exists")
    args = parser.parse_args()

    manifest = cache_logos(args.league, force=args.force)
    total = sum(len(league["teams"]) for league in manifest["leagues"].values())
    print(f"Saved {total} logos to {OUTPUT_DIR}")
    print(f"Wrote manifest to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
