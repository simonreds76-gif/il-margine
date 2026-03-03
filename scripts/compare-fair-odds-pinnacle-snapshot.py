#!/usr/bin/env python3
"""
Compare our fair odds (daily_fair_odds) to Pinnacle odds stored in bookmaker_odds_snapshot.
Use this after: (1) oncourt-compute-fair-odds.py, (2) pinnacle-scrape-odds.py --supabase.

Pinnacle is the sharp reference: if our fair odds imply a higher win prob than Pinnacle's
price, we have value on the other side (book odds > our fair odds = value bet).

Usage:
  python scripts/compare-fair-odds-pinnacle-snapshot.py
  python scripts/compare-fair-odds-pinnacle-snapshot.py --date 2025-02-08   # use this capture date
"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta

def load_env():
    base = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(base)
    for name in ["env.local", ".env.local"]:
        path = os.path.join(root, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().replace("\r", "")
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        os.environ[k.strip()] = v


def normalize_name(s):
    if not s:
        return ""
    return (s or "").strip().lower().replace(".", "").replace("-", " ")


def surname(name):
    parts = normalize_name(name).split()
    return parts[-1] if parts else ""


def compute_value(our_odds, book_odds):
    if our_odds <= 1.0 or book_odds <= 1.0:
        return None
    return round((book_odds / our_odds) - 1, 4)


def main():
    load_env()
    import requests

    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local")
        sys.exit(1)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    # Optional: --date YYYY-MM-DD for snapshot date
    capture_date = datetime.now(timezone.utc).date().isoformat()
    if "--date" in sys.argv:
        i = sys.argv.index("--date")
        if i + 1 < len(sys.argv):
            capture_date = sys.argv[i + 1]

    # 1) Load our fair odds with player names
    r = requests.get(
        f"{url}/rest/v1/daily_fair_odds",
        headers=headers,
        params={"select": "tour_id,player1_id,player2_id,odds1,odds2,p1_win_prob,p2_win_prob"},
        timeout=30,
    )
    r.raise_for_status()
    fair_rows = r.json()
    if not fair_rows:
        print("No rows in daily_fair_odds. Run oncourt-compute-fair-odds.py first.")
        sys.exit(1)

    player_ids = set()
    for row in fair_rows:
        if row.get("player1_id") is not None:
            player_ids.add(row["player1_id"])
        if row.get("player2_id") is not None:
            player_ids.add(row["player2_id"])
    player_ids = list(player_ids)
    players = {}
    for i in range(0, len(player_ids), 100):
        chunk = player_ids[i : i + 100]
        r2 = requests.get(
            f"{url}/rest/v1/oncourt_players",
            headers=headers,
            params={"id": "in.(" + ",".join(str(x) for x in chunk) + ")", "select": "id,name"},
            timeout=30,
        )
        if r2.status_code == 200:
            for p in r2.json():
                players[p["id"]] = (p.get("name") or "").strip()

    for row in fair_rows:
        row["p1_name"] = players.get(row.get("player1_id"), "")
        row["p2_name"] = players.get(row.get("player2_id"), "")

    # 2) Load Pinnacle snapshot for capture_date
    r = requests.get(
        f"{url}/rest/v1/bookmaker_odds_snapshot",
        headers=headers,
        params={
            "select": "capture_date,captured_at,league,player1_name,player2_name,odds1,odds2",
            "bookmaker": "eq.Pinnacle",
            "capture_date": f"eq.{capture_date}",
            "order": "captured_at.desc",
            "limit": 500,
        },
        timeout=30,
    )
    r.raise_for_status()
    pinnacle_rows = r.json()
    if not pinnacle_rows:
        print(f"No Pinnacle snapshot for {capture_date}. Run: python scripts/pinnacle-scrape-odds.py --supabase")
        sys.exit(1)
    print(f"Our fixtures: {len(fair_rows)}  |  Pinnacle snapshot ({capture_date}): {len(pinnacle_rows)} matches")

    # 3) Match by surname
    matched = []
    for pin in pinnacle_rows:
        p1_pin = (pin.get("player1_name") or "").strip()
        p2_pin = (pin.get("player2_name") or "").strip()
        s1 = surname(p1_pin)
        s2 = surname(p2_pin)
        if not s1 or not s2:
            continue
        for fo in fair_rows:
            p1_our = fo.get("p1_name") or ""
            p2_our = fo.get("p2_name") or ""
            s1_our = surname(p1_our)
            s2_our = surname(p2_our)
            if not s1_our or not s2_our:
                continue
            if s1 == s1_our and s2 == s2_our:
                matched.append({"fair": fo, "pinnacle": pin, "home_is_p1": True})
                break
            if s1 == s2_our and s2 == s1_our:
                matched.append({"fair": fo, "pinnacle": pin, "home_is_p1": False})
                break

    print(f"Matched: {len(matched)} matches\n")
    print("=" * 72)
    print("Our fair odds vs Pinnacle (reference)")
    print("=" * 72)

    value_bets = []
    for m in matched:
        fo, pin, home_is_p1 = m["fair"], m["pinnacle"], m["home_is_p1"]
        our_1 = float(fo.get("odds1") or 0)
        our_2 = float(fo.get("odds2") or 0)
        pin_1 = float(pin.get("odds1") or 0)
        pin_2 = float(pin.get("odds2") or 0)
        if home_is_p1:
            our_home, our_away = our_1, our_2
            pin_home, pin_away = pin_1, pin_2
            p1_name, p2_name = fo.get("p1_name"), fo.get("p2_name")
        else:
            our_home, our_away = our_2, our_1
            pin_home, pin_away = pin_2, pin_1
            p1_name, p2_name = fo.get("p2_name"), fo.get("p1_name")

        v_h = compute_value(our_home, pin_home)
        v_a = compute_value(our_away, pin_away)
        if v_h and v_h > 0:
            value_bets.append({"player": p1_name, "odds": pin_home, "our": our_home, "value": v_h, "match": f"{p1_name} vs {p2_name}"})
        if v_a and v_a > 0:
            value_bets.append({"player": p2_name, "odds": pin_away, "our": our_away, "value": v_a, "match": f"{p1_name} vs {p2_name}"})

        print(f"{p1_name} vs {p2_name}")
        print(f"  Our fair:   {p1_name}={our_home:.2f}  {p2_name}={our_away:.2f}")
        print(f"  Pinnacle:   {p1_name}={pin_home:.2f}  {p2_name}={pin_away:.2f}")
        vh_str = f"+{v_h:.1%}" if v_h and v_h > 0 else f"{v_h:.1%}" if v_h else "—"
        va_str = f"+{v_a:.1%}" if v_a and v_a > 0 else f"{v_a:.1%}" if v_a else "—"
        print(f"  Value vs Pinnacle:  {p1_name} {vh_str}   {p2_name} {va_str}")
        print()

    if value_bets:
        print("=" * 72)
        print("VALUE vs Pinnacle (our fair odds shorter than Pinnacle = bet at Pinnacle)")
        print("=" * 72)
        for vb in sorted(value_bets, key=lambda x: x["value"], reverse=True):
            print(f"  {vb['player']} @ {vb['odds']:.2f} (Pinnacle) — our fair {vb['our']:.2f} — value +{vb['value']:.1%}")
            print(f"    {vb['match']}")
    else:
        print("No value bets vs Pinnacle (all Pinnacle odds ≤ our fair odds).")
    print("\nDone.")


if __name__ == "__main__":
    main()
