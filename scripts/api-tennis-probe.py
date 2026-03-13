#!/usr/bin/env python3
"""
Probe API-Tennis: call every main method and print what we get.
Uses API_TENNIS_KEY from .env.local in project root (same file as Supabase keys).

Run from project root:
  python scripts/api-tennis-probe.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://api.api-tennis.com/tennis/"


def _load_env():
    for name in [".env.local", "env.local"]:
        p = ROOT / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
            return  # loaded first file found
    # If we get here, no file was found
    pass


def _get(method: str, **params) -> dict:
    key = os.environ.get("API_TENNIS_KEY", "").strip()
    if not key:
        return {"success": 0, "error": "API_TENNIS_KEY not set in .env.local"}
    params.setdefault("method", method)
    params.setdefault("APIkey", key)
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    _load_env()
    # Debug: where we're looking and if we found the var (never print the key)
    env_path = ROOT / ".env.local"
    env_alt = ROOT / "env.local"
    found_file = env_path.exists() or env_alt.exists()
    print("Project root: %s" % ROOT)
    print(".env.local exists: %s" % env_path.exists())
    print("env.local exists: %s" % env_alt.exists())
    key = os.environ.get("API_TENNIS_KEY", "").strip()
    print("API_TENNIS_KEY set: %s" % ("yes (len %d)" % len(key) if key else "no"))
    if not key:
        print("\nERROR: Add API_TENNIS_KEY=your_key to .env.local in project root (same file as SUPABASE keys).")
        sys.exit(1)
    print("\nAPI-Tennis probe\n")

    from datetime import date
    today = date.today().isoformat()

    # 1) get_events
    d = _get("get_events")
    ok = d.get("success") == 1
    res = d.get("result") or []
    print("get_events: success=%s, count=%d" % (ok, len(res)))
    if res:
        for i, e in enumerate(res[:5]):
            print("  [%s] %s" % (e.get("event_type_key"), e.get("event_type_type")))
        if len(res) > 5:
            print("  ...")
    print()

    # 2) get_tournaments
    d = _get("get_tournaments")
    ok = d.get("success") == 1
    res = d.get("result") or []
    print("get_tournaments: success=%s, count=%d" % (ok, len(res)))
    if res:
        atp = [t for t in res if "Atp" in (t.get("event_type_type") or "")]
        print("  ATP-related: %d" % len(atp))
        for t in atp[:3]:
            print("  [%s] %s - %s" % (t.get("tournament_key"), t.get("tournament_name"), t.get("event_type_type")))
    print()

    # 3) get_fixtures (today)
    d = _get("get_fixtures", date_start=today, date_stop=today)
    ok = d.get("success") == 1
    res = d.get("result") or []
    print("get_fixtures (today=%s): success=%s, count=%d" % (today, ok, len(res)))
    first_match_key = None
    first_player_key_1 = None
    first_player_key_2 = None
    if res:
        m = res[0]
        first_match_key = m.get("event_key")
        first_player_key_1 = m.get("first_player_key")
        first_player_key_2 = m.get("second_player_key")
        print("  sample: %s vs %s (event_key=%s)" % (
            m.get("event_first_player"), m.get("event_second_player"), first_match_key))
        print("  tournament: %s | round: %s | status: %s" % (
            m.get("tournament_name"), m.get("tournament_round"), m.get("event_status")))
    print()

    # 4) get_standings (ATP)
    d = _get("get_standings", event_type="ATP")
    ok = d.get("success") == 1
    res = d.get("result") or []
    print("get_standings (ATP): success=%s, count=%d" % (ok, len(res)))
    if res:
        for r in res[:3]:
            print("  rank %s: %s (key=%s)" % (r.get("rank"), r.get("player_name"), r.get("player_key")))
    print()

    # 5) get_livescore
    d = _get("get_livescore")
    ok = d.get("success") == 1
    res = d.get("result") or []
    print("get_livescore: success=%s, count=%d" % (ok, len(res)))
    if res:
        for m in res[:2]:
            print("  %s vs %s | %s" % (m.get("event_first_player"), m.get("event_second_player"), m.get("event_game_result")))
    print()

    # 6) get_players (one player from fixtures if we have keys)
    if first_player_key_1:
        d = _get("get_players", player_key=first_player_key_1)
        ok = d.get("success") == 1
        res = d.get("result")
        print("get_players (player_key=%s): success=%s" % (first_player_key_1, ok))
        if res is not None:
            if isinstance(res, dict):
                print("  keys: %s" % list(res.keys())[:12])
            else:
                print("  type: %s, len: %s" % (type(res).__name__, len(res) if hasattr(res, "__len__") else "?"))
        print()
    else:
        print("get_players: skipped (no fixture to get player_key from)")
        print()

    # 7) get_H2H (two players from fixtures)
    if first_player_key_1 and first_player_key_2:
        d = _get("get_H2H", first_player_key=first_player_key_1, second_player_key=first_player_key_2)
        ok = d.get("success") == 1
        res = d.get("result")
        if res is None:
            res = []
        count = len(res) if hasattr(res, "__len__") and not isinstance(res, dict) else (len(res) if isinstance(res, dict) else 0)
        print("get_H2H (%s vs %s): success=%s" % (first_player_key_1, first_player_key_2, ok))
        if isinstance(res, dict):
            print("  keys: %s" % list(res.keys())[:12])
        elif hasattr(res, "__getitem__") and not isinstance(res, (str, dict)):
            for h in list(res)[:3]:
                print("  %s" % h)
        print()
    else:
        print("get_H2H: skipped (need two player keys from fixtures)")
        print()

    # 8) get_odds (one match)
    if first_match_key:
        d = _get("get_odds", match_key=first_match_key)
        ok = d.get("success") == 1
        res = d.get("result")
        print("get_odds (match_key=%s): success=%s" % (first_match_key, ok))
        if res is not None:
            print("  type: %s" % (list(res.keys())[:10] if isinstance(res, dict) else "list len %d" % len(res)))
        print()
    else:
        print("get_odds: skipped (no match_key from today fixtures)")
        print()

    # 9) get_live_odds
    d = _get("get_live_odds")
    ok = d.get("success") == 1
    res = d.get("result")
    if res is None:
        res = []
    n = len(res) if isinstance(res, (list, tuple)) else (len(res) if isinstance(res, dict) else 0)
    print("get_live_odds: success=%s, count=%d" % (ok, n))
    if isinstance(res, dict):
        print("  keys: %s" % list(res.keys())[:8])
    elif isinstance(res, (list, tuple)) and res:
        for m in list(res)[:2]:
            print("  %s" % (m if isinstance(m, str) else list(m.keys())[:8] if isinstance(m, dict) else m))
    print()

    print("Done. We have Pinnacle for odds; use API-Tennis for fixtures/standings/H2H if useful.")


if __name__ == "__main__":
    main()
