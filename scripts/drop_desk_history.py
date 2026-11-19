"""Private price history and result projection from immutable capture and delivery evidence."""
import os
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import requests
from pinnradar_tennis import BUCKET, Store, utc
from price_drop_watch import START, object_key


def completed_score(score, sets_needed):
    """Canonical winner-first completed sets. Retirements/incomplete scores stay open."""
    if not re.fullmatch(r"\d+-\d+(?:\(\d+\))?(?:\s+\d+-\d+(?:\(\d+\))?)*",score):
        return False
    won = lost = 0
    for a,b in re.findall(r"(\d+)-(\d+)",score):
        left,right = int(a),int(b)
        hi,lo = max(left,right),min(left,right)
        if won == sets_needed or lost == sets_needed:
            return False
        if not ((hi == 6 and lo <= 4) or (hi >= 7 and hi-lo == 2) or (hi,lo) == (7,6)):
            return False
        won += left > right
        lost += left < right
    return won == sets_needed and lost < sets_needed


def rows(store, prefix):
    response = store.request("POST", "/object/list/" + BUCKET, json={
        "prefix": prefix + "/", "limit": 100, "sortBy": {"column": "name", "order": "asc"}})
    store.require(response)
    return sorted(r["name"] for r in response.json() if re.fullmatch(r"\d{4}\.json", r["name"]))


def key(row):
    return "|".join((row["id"], row["fixture"], row["start"]))


def append_snapshot(tape, filename, snapshot):
    stamp = snapshot["observed"]
    if filename in tape["slots"]:
        if tape["slots"][filename] != stamp:
            raise ValueError("A saved scan slot changed identity")
        return
    for row in snapshot["events"].values():
        entry = tape["series"].setdefault(key(row), {"players": [row["home"],row["away"]], "quotes": []})
        prices = {row["home"]: row["home_price"], row["away"]: row["away_price"]}
        if set(prices) != set(entry["players"]):
            raise ValueError("Price series player identity changed")
        entry["quotes"].append([stamp, *[prices[name] for name in entry["players"]]])
    tape["slots"][filename] = stamp


def normal(text):
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def competition(label):
    text = normal(label)
    if text in ("atp finals", "nitto atp finals turin"):
        return "atp finals turin"
    return " ".join(p for p in text.split() if p not in ("atp", "challenger"))


def round_ids(label, tour):
    rounds = {"groups":{8},"qf":{9},"sf":{10},"final":{12},"q1":{1},"q2":{2},
              "q3":{3},"qualifiers":{1,2,3},"r1":{4},"r2":{5}}
    if tour == "Challenger":
        rounds.update({"r32":{4},"r16":{5}})
    return rounds.get(label.casefold(), set())


def api_rows(table, fields, **filters):
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + table
    token = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    response = requests.get(url, headers={"apikey":token, "Authorization":"Bearer " + token},
                            params={"select":fields, "limit":1000, **filters}, timeout=18, allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f"Result records unavailable (HTTP {response.status_code})")
    result = response.json()
    if not isinstance(result,list) or len(result) >= 1000:
        raise RuntimeError("Incomplete result page")
    return result


def in_filter(ids):
    return "in.(" + ",".join(str(int(x)) for x in sorted(set(ids))) + ")"


def bind(ticket, tours, schedule, games, names):
    player, opponent = normal(ticket["player"]), normal(ticket["opponent"])
    day = date.fromisoformat(ticket["start"][:10])
    label, _, round_label = ticket["league"].rpartition(" - ")
    rounds = round_ids(round_label, ticket["tour"])
    matches = set()
    for row in [*schedule, *games]:
        tour = tours.get(row["tour_id"])
        if not tour or row["round_id"] not in rounds:
            continue
        if ("challenger" in tour["name"].casefold()) != (ticket["tour"] == "Challenger"):
            continue
        if not -3 <= (day - date.fromisoformat(tour["date"][:10])).days <= 13:
            continue
        if competition(tour["name"]) != competition(label):
            continue
        p = row.get("player1_id",row.get("winner_id"))
        q = row.get("player2_id",row.get("loser_id"))
        if (names.get(q), names.get(p)) == (player, opponent):
            p,q = q,p
        if (names.get(p), names.get(q)) == (player,opponent) and p != q:
            matches.add((row["tour_id"],row["round_id"],p,q))
    return list(matches.pop()) if len(matches) == 1 else None


def outcome(ticket, games, schedule, now):
    if not ticket.get("binding") or utc(ticket["start"]) >= now:
        return None
    tour, rnd, player, other = ticket["binding"]
    pair = {player, other}
    candidates = [r for r in games if r["tour_id"] == tour and r["round_id"] == rnd
                  and {r["winner_id"],r["loser_id"]} == pair]
    day = date.fromisoformat(ticket["start"][:10])
    voids = [r for r in schedule if r["tour_id"] == tour and r["round_id"] == rnd
             and {r["player1_id"],r["player2_id"]} == pair and str(r.get("result") or "").lower().strip() in ("w/o","wo","walkover")]
    if len(candidates) != 1:
        return {"result":"Void","score":"W/O"} if not candidates and len(voids) == 1 else None
    row = candidates[0]
    if not row.get("date") or abs((date.fromisoformat(row["date"][:10]) - day).days) > 1:
        return None
    score = str(row["result"] or "").strip()
    if score.lower() in ("w/o","wo","walkover"):
        return {"result":"Void","score":score}
    label = normal(ticket["league"])
    slam = any(title in label for title in ("australian open","roland garros","french open","wimbledon","us open"))
    need = 3 if slam and rnd >= 4 else 2
    if voids or not completed_score(score,need):
        return None
    return {"result":"Won" if row["winner_id"] == player else "Lost","score":score}


def event_data(tickets):
    days = [date.fromisoformat(t["start"][:10]) for t in tickets]
    tours = {r["id"]:r for r in api_rows("oncourt_tours","id,date,name",
             **{"and":f"(date.gte.{min(days)-timedelta(days=14)},date.lte.{max(days)+timedelta(days=3)})"})}
    wanted = {competition(t["league"].rpartition(" - ")[0]) for t in tickets}
    ids = sorted(i for i,r in tours.items() if competition(r["name"]) in wanted)
    schedule, games, names = [], [], {}
    for start in range(0,len(ids),2):
        sel = in_filter(ids[start:start+2])
        schedule.extend(api_rows("oncourt_today","tour_id,round_id,player1_id,player2_id,result",tour_id=sel))
        games.extend(api_rows("oncourt_games","tour_id,round_id,winner_id,loser_id,date,result",tour_id=sel))
    player_ids = sorted({r[c] for r in schedule for c in ("player1_id","player2_id")} |
                        {r[c] for r in games for c in ("winner_id","loser_id")})
    for start in range(0,len(player_ids),100):
        names.update({r["id"]:normal(r["name"]) for r in api_rows("oncourt_players","id,name",id=in_filter(player_ids[start:start+100]))})
    return tours, schedule, games, names


def settle(store, state, now):
    pending = state["pending"]
    due = {}
    for mid,ticket in pending.items():
        start = utc(ticket["start"])
        last = utc(ticket.get("last_check"))
        if ticket.get("binding") and now < start:
            continue
        interval = timedelta(days=1) if now - start > timedelta(days=7) else timedelta(hours=1)
        if last and now - last < interval:
            continue
        due.setdefault(ticket["start"][:10],{})[mid] = ticket
    if not due:
        return
    resolved = defaultdict(dict)
    for group in due.values():
        tours, schedule, games, names = event_data(list(group.values()))
        for mid,ticket in group.items():
            if not ticket.get("binding"):
                ticket["binding"] = bind(ticket,tours,schedule,games,names)
            result = outcome(ticket,games,schedule,now)
            ticket["last_check"] = now.isoformat()
            if result:
                resolved[ticket["after"][:10]][mid] = {**result,"binding":ticket["binding"],
                    "settled_at":now.isoformat(),"alerted_price":ticket["new"],"message_id":ticket["message_id"]}
    for day,changes in resolved.items():
        path = f"presentation/outcomes/{day}.json"
        records = store.get(path) or {}
        for mid,value in changes.items():
            if mid in records and any(records[mid].get(k) != value[k] for k in ("result","score")):
                raise ValueError("Existing outcome differs from verified result")
            records.setdefault(mid,value)
        store.put(path,records,replace=True)
        for mid in changes:
            del pending[mid]


def project(store, now):
    state_path = "presentation/desk-checkpoint-v1.json"
    state = store.get(state_path) or {"next_day":START.date().isoformat(),"pending":{}}
    day = date.fromisoformat(state["next_day"])
    while day <= now.date():
        prefix = "snapshots/" + day.strftime("%Y/%m/%d")
        dest = f"presentation/desk-tapes/{day.isoformat()}.json"
        tape = store.get(dest) or {"slots":{},"series":{}}
        # Checkpoint intake independently so a retry after writing a tape still registers its alerts.
        processed = state.setdefault("intake",{})
        changed = False
        for name in rows(store,prefix):
            if name in processed and name in tape["slots"]:
                continue
            snap = store.get(prefix + "/" + name)
            if snap is None:
                raise ValueError("Listed scan missing")
            if name not in tape["slots"]:
                append_snapshot(tape,name,snap)
                changed = True
            stamp = snap["observed"]
            if utc(stamp) >= START:
                batch = store.get("drop-scans-v2/" + object_key(stamp))
                if batch is None:
                    continue
                if batch["moves"]:
                    receipt = store.get("drop-deliveries-v2/" + object_key(stamp))
                    if not receipt or receipt.get("state") != "sent":
                        continue
                    delivered = set(receipt["move_ids"])
                    for m in batch["moves"]:
                        if m["move_id"] in delivered:
                            t = {k:m[k] for k in ("player","opponent","tour","league","start","after","new")}
                            state["pending"].setdefault(m["move_id"],{**t,"message_id":receipt["message_id"]})
            processed[name] = True
        if changed:
            store.put(dest,tape,replace=True)
        if day < now.date():
            state["intake"] = {}
            state["next_day"] = (day + timedelta(days=1)).isoformat()
        day += timedelta(days=1)
    # Save newly observed receipts before attempting any independent result reads.
    store.put(state_path,state,replace=True)
    settle(store,state,now)
    store.put(state_path,state,replace=True)
    print("Private quote history and settlement check completed.")


if __name__ == "__main__":
    project(Store(),datetime.now(timezone.utc))
