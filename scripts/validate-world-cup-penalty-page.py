"""Validate the World Cup penalty taker public page/data before promotion.

This intentionally checks the failure modes that are easy to miss during a
small hierarchy update: stale JSON copied over newer audit work, old homepage
copy returning, broken latest-update cards, mojibake, and CTA regressions.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "goalscorer" / "world-cup-2026-penalty-takers.json"
MAIN_PAGE_PATH = ROOT / "src" / "app" / "penalty-takers" / "world-cup-2026" / "page.tsx"
TEAM_PAGE_PATH = ROOT / "src" / "app" / "penalty-takers" / "world-cup-2026" / "[teamSlug]" / "page.tsx"
LIB_PATH = ROOT / "src" / "lib" / "world-cup-penalties.ts"
CONFIG_PATH = ROOT / "src" / "lib" / "config.ts"
NAV_PATH = ROOT / "src" / "components" / "GlobalNav.tsx"
PENALTY_LANDING_PATH = ROOT / "src" / "app" / "penalty-takers" / "PenaltyTakersClient.tsx"
PLAYER_PROPS_PATH = ROOT / "src" / "app" / "player-props" / "PlayerPropsClient.tsx"
OVERLAYS_PATH = ROOT / "src" / "components" / "RouteScopedOverlays.tsx"
TELEGRAM_OVERLAY_PATH = ROOT / "src" / "components" / "WorldCupTelegramOverlay.tsx"
TELEGRAM_ROUTE_PATH = ROOT / "src" / "app" / "go" / "world-cup-telegram" / "route.ts"
GENERIC_TELEGRAM_ROUTE_PATH = ROOT / "src" / "app" / "go" / "telegram" / "route.ts"
WC_FREE_PAGE_PATH = ROOT / "src" / "app" / "world-cup-2026-free-picks" / "page.tsx"
SITEMAP_PATH = ROOT / "src" / "app" / "sitemap.ts"
PROXY_PATH = ROOT / "src" / "proxy.ts"
WC_BRAND_IMAGE_PATH = ROOT / "public" / "brand" / "world-cup-2026-free-picks.png"

EXPECTED_AUDITED_HIERARCHY = {
    "Australia": ("Ajdin Hrustic", "Mohamed Toure"),
    "Brazil": ("Neymar", "Raphinha"),
    "Cabo Verde": ("Ryan Mendes", "Jovane Cabral"),
    "Curacao": ("Leandro Bacuna", "Juninho Bacuna"),
    "IR Iran": ("Mehdi Taremi", "Alireza Jahanbakhsh"),
    "Korea Republic": ("Son Heung-min", "Hwang Hee-chan"),
    "Spain": ("Mikel Oyarzabal", "Lamine Yamal"),
    "Switzerland": ("Granit Xhaka", "Breel Embolo"),
    "Uruguay": ("Federico Valverde", "Rodrigo Bentancur"),
}

EXPECTED_LATEST_UPDATE_TEAMS = set(EXPECTED_AUDITED_HIERARCHY)
REJECTED_COPY = {
    "Late qualifiers added",
    "Groups locked in",
    "The last six teams are now on the board",
    "LATE_QUALIFIER_TEAMS",
}
MOJIBAKE_MARKERS = ("Ã", "Â", "Ä", "�", "â€")


def fail(message: str) -> None:
    print(f"[wc-penalties] FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        fail(f"{path.relative_to(ROOT)} has a UTF-8 BOM")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{path.relative_to(ROOT)} is not valid UTF-8: {exc}")


def parse_iso_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail(f"{label} is not ISO YYYY-MM-DD: {value!r}")


def as_team_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    teams = data.get("teams")
    if not isinstance(teams, list):
        fail("JSON field teams must be a list")

    names: list[str] = []
    result: dict[str, dict[str, Any]] = {}
    for row in teams:
        if not isinstance(row, dict):
            fail("team rows must be objects")
        name = row.get("team")
        if not isinstance(name, str) or not name:
            fail("each team row needs a team name")
        names.append(name)
        result[name] = row

    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        fail(f"duplicate teams in JSON: {', '.join(duplicates)}")
    return result


def check_no_mojibake(label: str, text: str) -> None:
    marker = next((item for item in MOJIBAKE_MARKERS if item in text), None)
    if marker:
        fail(f"{label} contains likely mojibake marker {marker!r}")


def check_json_data() -> dict[str, dict[str, Any]]:
    text = read_text(DATA_PATH)
    check_no_mojibake(DATA_PATH.relative_to(ROOT).as_posix(), text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"World Cup penalty JSON is invalid: {exc}")

    if data.get("qualified_count") != 48:
        fail(f"qualified_count must be 48, got {data.get('qualified_count')!r}")
    if data.get("playoff_count") != 0:
        fail(f"playoff_count must be 0 after the final field, got {data.get('playoff_count')!r}")

    teams = as_team_map(data)
    if len(teams) != 48:
        fail(f"expected 48 team rows, got {len(teams)}")

    last_verified = parse_iso_date(str(data.get("last_verified", "")), "last_verified")
    latest_squad_date = last_verified
    for team in teams.values():
        squad_verified_at = team.get("squad_verified_at")
        if squad_verified_at:
            latest_squad_date = max(latest_squad_date, parse_iso_date(str(squad_verified_at), f"{team['team']}.squad_verified_at"))
    if last_verified < latest_squad_date:
        fail(f"last_verified {last_verified} is older than latest squad audit {latest_squad_date}")

    for team_name, (expected_primary, expected_secondary) in EXPECTED_AUDITED_HIERARCHY.items():
        row = teams.get(team_name)
        if not row:
            fail(f"audited team missing from JSON: {team_name}")
        actual = (row.get("likely_primary"), row.get("likely_secondary"))
        expected = (expected_primary, expected_secondary)
        if actual != expected:
            fail(f"{team_name} hierarchy regressed: expected {expected}, got {actual}")
        if not row.get("last_evidence"):
            fail(f"{team_name} is missing last_evidence")
        if not row.get("evidence_log"):
            fail(f"{team_name} is missing evidence_log")

    return teams


def check_world_cup_page(teams: dict[str, dict[str, Any]]) -> None:
    text = read_text(MAIN_PAGE_PATH)
    check_no_mojibake(MAIN_PAGE_PATH.relative_to(ROOT).as_posix(), text)

    for rejected in REJECTED_COPY:
        if rejected in text:
            fail(f"old stale page copy returned: {rejected!r}")

    latest_teams = re.findall(r'team:\s*"([^"]+)"', text)
    latest_teams = latest_teams[: len(EXPECTED_LATEST_UPDATE_TEAMS)]
    missing = sorted(EXPECTED_LATEST_UPDATE_TEAMS - set(latest_teams))
    extra = sorted(set(latest_teams) - EXPECTED_LATEST_UPDATE_TEAMS)
    if missing or extra:
        fail(f"latest-update cards mismatch; missing={missing}, extra={extra}, found={latest_teams}")
    for team_name in latest_teams:
        if team_name not in teams:
            fail(f"latest-update card points to unknown team: {team_name}")

    required_page_snippets = [
        "formatAuditDate(data.last_verified)",
        "Latest penalty taker updates",
        "Boyle cut, hierarchy rebuilt",
        "Neymar conditional No. 1",
        "Backup caveat tightened",
        "Azmoun stays off the hierarchy",
        "Bebe out, Cabral in",
    ]
    for snippet in required_page_snippets:
        if snippet not in text:
            fail(f"main World Cup page missing required snippet: {snippet!r}")


def check_team_pages() -> None:
    team_page = read_text(TEAM_PAGE_PATH)
    lib = read_text(LIB_PATH)
    for label, text in {
        TEAM_PAGE_PATH.relative_to(ROOT).as_posix(): team_page,
        LIB_PATH.relative_to(ROOT).as_posix(): lib,
    }.items():
        check_no_mojibake(label, text)

    if "formatAuditDate(data.last_verified)" not in team_page:
        fail("team page must display formatted audit dates, not raw American-style dates")
    if 'new Intl.DateTimeFormat("en-GB"' not in lib:
        fail("formatAuditDate must use en-GB date formatting")


def check_telegram_cta() -> None:
    files = {
        "config": read_text(CONFIG_PATH),
        "nav": read_text(NAV_PATH),
        "penalty_landing": read_text(PENALTY_LANDING_PATH),
        "player_props": read_text(PLAYER_PROPS_PATH),
        "overlays": read_text(OVERLAYS_PATH),
        "telegram_overlay": read_text(TELEGRAM_OVERLAY_PATH),
        "telegram_route": read_text(TELEGRAM_ROUTE_PATH),
        "generic_telegram_route": read_text(GENERIC_TELEGRAM_ROUTE_PATH),
        "wc_free_page": read_text(WC_FREE_PAGE_PATH),
        "sitemap": read_text(SITEMAP_PATH),
        "proxy": read_text(PROXY_PATH),
    }
    for label, text in files.items():
        check_no_mojibake(label, text)

    if "https://t.me/IlMargineWC" not in files["config"]:
        fail("Telegram config must default to https://t.me/IlMargineWC")
    if "X-Robots-Tag" not in files["telegram_route"] or "noindex, nofollow" not in files["telegram_route"]:
        fail("Telegram redirect route must be noindex/nofollow")
    if "X-Robots-Tag" not in files["generic_telegram_route"] or "noindex, nofollow" not in files["generic_telegram_route"]:
        fail("generic Telegram redirect route must be noindex/nofollow")
    if "/world-cup-2026-free-picks" in files["nav"]:
        fail("completed World Cup campaign must not be promoted in global navigation")
    if "Never miss a player-prop pick" not in files["player_props"] or "/go/telegram?source=player_props_alerts" not in files["player_props"]:
        fail("player-props page missing the contextual Telegram alerts CTA")
    club_index = files["penalty_landing"].find("Club penalty takers")
    archive_index = files["penalty_landing"].find("Tournament archive")
    if club_index < 0 or archive_index < 0 or club_index > archive_index:
        fail("club 2026/27 penalty board must appear before the World Cup archive")
    if "WorldCupTelegramOverlay" not in files["overlays"]:
        fail("route-scoped overlays must mount the World Cup Telegram overlay")
    if "setShowBar(false)" not in files["telegram_overlay"] or "Close Telegram prompt" not in files["telegram_overlay"]:
        fail("World Cup archive bar close handler is missing")
    if "Join Free" not in files["telegram_overlay"]:
        fail("World Cup archive bar missing Telegram CTA")
    if "world-cup-2026-free-picks" not in files["sitemap"]:
        fail("World Cup free picks landing page missing from sitemap")
    if 'url.searchParams.has("q")' not in files["proxy"] or "NextResponse.redirect" not in files["proxy"]:
        fail("proxy must redirect search-query homepage URLs to the canonical homepage")
    if not WC_BRAND_IMAGE_PATH.exists() or WC_BRAND_IMAGE_PATH.stat().st_size < 100_000:
        fail("World Cup CTA image is missing or suspiciously small")


def main() -> None:
    teams = check_json_data()
    check_world_cup_page(teams)
    check_team_pages()
    check_telegram_cta()
    print("[wc-penalties] OK: World Cup penalty data/page/CTA validation passed.")


if __name__ == "__main__":
    main()
