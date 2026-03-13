"""
Quick debug: query player_elo for given player names.
Usage: python scripts/debug-elo.py Djokovic Majchrzak
"""
import os
import sys
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
for name in ["env.local", ".env.local"]:
    path = os.path.join(_root, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip().replace("\r", "")
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    os.environ[k.strip()] = v

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not url or not key:
    print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local")
    sys.exit(1)

import requests
base = url.rstrip("/") + "/rest/v1"
headers = {"apikey": key, "Authorization": f"Bearer {key}"}

names = [a.strip() for a in sys.argv[1:]] if len(sys.argv) > 1 else ["Djokovic", "Majchrzak"]
print(f"Looking up Elo for: {names}\n")

# Get players by name (ilike filter)
players = []
for q in names:
    r = requests.get(
        f"{base}/oncourt_players",
        headers=headers,
        params={"select": "id,name", "name": f"ilike.%{q}%", "limit": 20},
        timeout=60,
    )
    if r.status_code != 200:
        print(f"Error: oncourt_players {r.status_code} {r.text[:200]}")
        sys.exit(1)
    data = r.json()
    for row in data:
        pid, n = int(row["id"]), (row.get("name") or "").strip()
        if not any(p[0] == pid for p in players):
            players.append((pid, n))

if not players:
    print("No matching players found in oncourt_players")
    sys.exit(1)

pids = [p[0] for p in players]
print("Players:", {p[0]: p[1] for p in players})

# Get Elo for these players
elo_rows = []
for pid in pids:
    r = requests.get(
        f"{base}/player_elo",
        headers=headers,
        params={"player_id": "eq." + str(pid), "select": "player_id,surface,elo"},
        timeout=30,
    )
    r.raise_for_status()
    elo_rows.extend(r.json())

pid_to_name = {p[0]: p[1] for p in players}
by_player = {}
for row in elo_rows:
    pid = int(row["player_id"])
    surf = (row.get("surface") or "N/A").strip()
    elo = row.get("elo")
    if pid not in by_player:
        by_player[pid] = {}
    by_player[pid][surf] = elo

print("\nElo by player:")
for pid, name in players:
    rows = by_player.get(pid, {})
    if not rows:
        print(f"  {name} (id={pid}): NO ELO DATA")
        continue
    surf_elo = {k: v for k, v in rows.items() if k != "Overall"}
    overall = rows.get("Overall")
    print(f"  {name} (id={pid}):")
    for surf, elo in sorted(rows.items()):
        print(f"    {surf}: {elo}")
    if surf_elo and overall is not None:
        avg_surf = sum(v for v in surf_elo.values() if v is not None) / len([v for v in surf_elo.values() if v is not None])
        print(f"    -> surface avg ~{avg_surf:.0f}, Overall={overall}")

if len(players) == 2:
    p1_id, p1_name = players[0]
    p2_id, p2_name = players[1]
    e1 = by_player.get(p1_id, {})
    e2 = by_player.get(p2_id, {})
    # Use Hard or first available surface for gap
    for surf in ["Hard", "Clay", "Overall", "Grass", "I.hard"]:
        v1 = e1.get(surf) if e1 else None
        v2 = e2.get(surf) if e2 else None
        if v1 is not None and v2 is not None:
            gap = abs(float(v1) - float(v2))
            print(f"\n  Gap ({surf}): {p1_name} {v1} vs {p2_name} {v2} -> gap={gap:.0f}")
            if gap < 250:
                print(f"    Class gap: NO (gap < 250 onset)")
            elif gap < 500:
                print(f"    Class gap: PARTIAL (250-500, ramping)")
            else:
                print(f"    Class gap: FULL (gap >= 500)")
            break
