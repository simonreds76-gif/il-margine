"""Private price history and result projection from immutable capture and delivery evidence."""
import os
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import requests
from pinnradar_tennis import BUCKET, Store, utc
from price_drop_watch import START, object_key
from desk_games import market_limit, pairs


RETIREMENT = re.compile(r"\b(?:ret(?:ired|irement)?|def(?:ault(?:ed)?)?|disqualifi(?:ed|cation)|dsq|dq)\b", re.I)
WALKOVERS = {"wo", "w/o", "w.o.", "walkover", "walk-over", "withdrawn", "withdrawal", "w/d"}


def retirement_grade(ticket, score, selected_won):
    """A match moneyline needs a verified first set and the officially awarded winner."""
    if ticket.get("market", "winner") in ("spreads", "totals"):
        return {"result":"Void", "score":score, "settled_stake":0, "profit":0}
    raw = RETIREMENT.sub("", score).strip(" .")
    raw = re.sub(r"\s*\(\.?\)$","",raw).strip()
    if not re.fullmatch(r"\d+-\d+(?:\(\d+\))?(?:\s+\d+-\d+(?:\(\d+\))?)*", raw):
        return None
    sets = [(int(a),int(b)) for a,b in re.findall(r"(\d+)-(\d+)",raw)]
    short_sets = "next gen" in normal(ticket.get("league","")).replace("nextgen","next gen")
    target = 4 if short_sets else 6
    for index,(a,b) in enumerate(sets):
        hi,lo = max(a,b),min(a,b)
        complete = ((hi == 4 and lo <= 3) if short_sets else
                    ((hi == 6 and lo <= 4) or (hi == 7 and lo in (5,6))))
        partial = hi < target or (not short_sets and hi == 6 and lo in (5,6))
        if not complete and (not partial or index < len(sets)-1):
            return None
        if index == 0:
            first_complete = complete
    if not first_complete:
        return {"result":"Void", "score":score, "settled_stake":0, "profit":0}
    return {"result":"Won" if selected_won else "Lost", "score":score}


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
    exists = filename in tape["slots"]
    if exists and tape["slots"][filename] != stamp:
        raise ValueError("A saved scan slot changed identity")
    if filename in tape.get("limit_slots", {}):
        return
    for row in snapshot["events"].values():
        for code, pair in pairs(row):
            series_key = key(row) if code == "winner" else key(row) + "|" + code
            series = tape["series"].setdefault(series_key, {"players":pair["labels"], "quotes":[]})
            prices = dict(zip(pair["labels"], pair["prices"]))
            if set(prices) != set(series["players"]):
                raise ValueError("Price series player identity changed")
            quote = [stamp, *[prices[name] for name in series["players"]]]
            if exists:
                saved = next((q for q in series["quotes"] if q[0] == stamp), None)
                if saved is None or saved[:3] != quote:
                    raise ValueError("Stored chart odds and snapshot disagree")
            else:
                series["quotes"].append(quote)
            limit = market_limit(row, pair)
            if limit is not None:
                series.setdefault("limits", {})[stamp] = limit
    tape.setdefault("limit_slots", {})[filename] = True
    tape["slots"][filename] = stamp


def normal(text):
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def competition(label):
    text = normal(label)
    if text in ("atp finals", "nitto atp finals turin"):
        return "atp finals turin"
    return " ".join(p for p in text.split() if p not in ("atp", "challenger"))


def tournament_labels(name):
    exact = competition(name)
    labels = {exact}
    if "challenger" in normal(name).split():
        # A price board can omit the edition number on successive weeks in one city.
        labels.add(re.sub(r" [1-9][0-9]?$", "", exact))
    return labels


# Alternate price-board spellings verified against the singles draws and player IDs.
PLAYER_ALIASES = {
    "adam faragcao": (99304, "adam farag cao"),
    "enzo lima": (85002, "enzo camargo lima"),
    "herbert jody maginley": (36878, "jody maginley"),
    "martinez elias sebastian": (134133, "sebastian martinez elias"),
    "tai leonard sach": (68624, "tai sach"),
    "yun seong chung": (28742, "yunseong chung"),
}


def same_player(label, player_id, names):
    registered = names.get(player_id)
    return label == registered or PLAYER_ALIASES.get(label) == (player_id, registered)


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
    wanted = competition(label)
    matches = set()
    for row in [*schedule, *games]:
        tour = tours.get(row["tour_id"])
        if not tour or row["round_id"] not in rounds:
            continue
        if ("challenger" in tour["name"].casefold()) != (ticket["tour"] == "Challenger"):
            continue
        if not -3 <= (day - date.fromisoformat(tour["date"][:10])).days <= 13:
            continue
        if wanted not in tournament_labels(tour["name"]):
            continue
        if wanted != competition(tour["name"]):
            row_day = row.get("date")
            if row_day:
                if abs((day - date.fromisoformat(row_day[:10])).days) > 1:
                    continue
            elif not -3 <= (day - date.fromisoformat(tour["date"][:10])).days <= 6:
                continue
        p = row.get("player1_id",row.get("winner_id"))
        q = row.get("player2_id",row.get("loser_id"))
        if same_player(player, q, names) and same_player(opponent, p, names):
            p,q = q,p
        if same_player(player, p, names) and same_player(opponent, q, names) and p != q:
            matches.add((row["tour_id"],row["round_id"],p,q))
    return list(matches.pop()) if len(matches) == 1 else None


def native_outcome(ticket, games, schedule, now):
    if not ticket.get("binding") or utc(ticket["start"]) >= now:
        return None
    tour, rnd, player, other = ticket["binding"]
    pair = {player, other}
    candidates = [r for r in games if r["tour_id"] == tour and r["round_id"] == rnd
                  and {r["winner_id"],r["loser_id"]} == pair]
    day = date.fromisoformat(ticket["start"][:10])
    voids = [r for r in schedule if r["tour_id"] == tour and r["round_id"] == rnd
             and {r["player1_id"],r["player2_id"]} == pair and str(r.get("result") or "").lower().strip() in WALKOVERS]
    if len(candidates) != 1:
        return {"result":"Void","score":"W/O"} if not candidates and len(voids) == 1 else None
    row = candidates[0]
    if not row.get("date") or abs((date.fromisoformat(row["date"][:10]) - day).days) > 1:
        return None
    score = str(row["result"] or "").strip()
    if score.lower() in WALKOVERS:
        return {"result":"Void","score":score}
    if voids:
        return None
    if RETIREMENT.search(score):
        return retirement_grade(ticket, score, row["winner_id"] == player)
    if ticket.get("market") in ("spreads","totals") and re.search(r"\babandoned\b",score,re.I):
        return {"result":"Void","score":score,"settled_stake":0,"profit":0}
    label = normal(ticket["league"])
    slam = any(title in label for title in ("australian open","roland garros","french open","wimbledon","us open"))
    need = 3 if slam and rnd >= 4 else 2
    if not completed_score(score,need):
        return None
    if ticket.get("market","winner") in ("spreads","totals"):
        from desk_games import grade
        sets = [(int(a),int(b)) for a,b in re.findall(r"(\d+)-(\d+)",score)]
        return {"score":score, **grade(ticket,sets,row["winner_id"]==player)}
    return {"result":"Won" if row["winner_id"] == player else "Lost","score":score}


# Reviewed draw snapshot for the November backlog. Only the scheduled single writer grades it.
DRAW_REVIEW = "f52e8197cb69cda7b9a500b469b7360f34af2e4a29a35d14193a353192367ec5"


@lru_cache(maxsize=1)
def draw_review():
    packet = Store().get("presentation/result-reviews/" + DRAW_REVIEW + ".json")
    if packet is None:
        return {}
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(encoded).hexdigest() != DRAW_REVIEW:
        raise ValueError("Reviewed draw evidence failed its integrity check")
    return {(r["league"], utc(r["start"]), tuple(r["players"])): r for r in packet}


def outcome(ticket, games, schedule, now):
    grade = native_outcome(ticket, games, schedule, now)
    if grade or ticket.get("tour") != "Challenger" or not "2026-11-22" <= ticket["start"][:10] <= "2026-11-24":
        return grade
    start = utc(ticket["start"])
    if not start or now <= start:
        return None
    key = (ticket["league"], start, tuple(sorted([ticket["player"], ticket["opponent"]])))
    review = draw_review().get(key)
    if not review:
        return None
    replacement = review.get("replaced")
    if replacement:
        # No score from the replacement match can be carried over to the original bet.
        def recorded(opponent):
            return [g for g in games if (g["tour_id"],g["round_id"]) == (replacement["tour_id"],replacement["round_id"])
                    and {g["winner_id"],g["loser_id"]} == {replacement["player"],opponent}]
        if not ticket.get("binding") and not recorded(replacement["original"]) and len(recorded(replacement["replacement"])) == 1:
            return {"result":"Void","score":"Opponent replaced before play"}
        return None
    row = review["row"]
    binding = ticket.get("binding")
    if not binding or list(binding[:2]) != [row["tour_id"],row["round_id"]] or set(binding[2:]) != {row["winner_id"],row["loser_id"]}:
        return None
    if any(g["tour_id"] == binding[0] and g["round_id"] == binding[1] and
           {g["winner_id"],g["loser_id"]} == set(binding[2:]) for g in games):
        return None
    return native_outcome(ticket, [row], schedule, now)


def event_data(tickets):
    days = [date.fromisoformat(t["start"][:10]) for t in tickets]
    tours = {r["id"]:r for r in api_rows("oncourt_tours","id,date,name",
             **{"and":f"(date.gte.{min(days)-timedelta(days=14)},date.lte.{max(days)+timedelta(days=3)})"})}
    wanted = {competition(t["league"].rpartition(" - ")[0]) for t in tickets}
    ids = sorted(i for i,r in tours.items() if tournament_labels(r["name"]) & wanted)
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


def wta_result(ticket, events):
    """Match a women's singles result to the recorded city/event, round, players and UTC date."""
    label, _, rnd = ticket["league"].rpartition(" - ")
    location = normal(re.sub(r"^WTA\s+(?:125k?\s+)?", "", label, flags=re.I))
    rounds = {"sf":{"semifinal"}, "qf":{"quarterfinal"}, "final":{"final"},
              "r1":{"first round"}, "r2":{"second round"}, "r3":{"third round"},
              "qualifiers":{"qualifying first round","qualifying second round","qualifying final"},
              "q1":{"qualifying first round"}, "groups":{"round robin","group stage"}}
    expected = rounds.get(rnd.casefold(), set())
    numbered = re.fullmatch(r"r(16|32|64|128)", rnd.casefold())
    if numbered:
        expected = {"round of " + numbered[1]}
    names = (normal(ticket["player"]), normal(ticket["opponent"]))
    matches = []
    for event in events:
        for group in event.get("groupings", []):
            if group.get("grouping", {}).get("slug") != "womens-singles":
                continue
            for game in group.get("competitions", []):
                city = normal((game.get("venue") or {}).get("fullName","").split(",")[0])
                if not location or location not in {city, normal(event.get("name","")), normal(event.get("shortName",""))}:
                    continue
                if normal((game.get("round") or {}).get("displayName","")) not in expected:
                    continue
                played = utc(game.get("date"))
                if not played or abs((played.date() - utc(ticket["start"]).date()).days) > 1:
                    continue
                sides = game.get("competitors",[])
                if len(sides) == 2 and {normal((p.get("athlete") or {}).get("displayName","")) for p in sides} == set(names):
                    matches.append((event["id"],game,sides))
    if len(matches) != 1:
        return None
    edition, game, sides = matches[0]
    if not game.get("id") or not all(s.get("id") for s in sides) or sides[0]["id"] == sides[1]["id"]:
        return None
    binding = ["wta",edition,game["id"],*[s["id"] for s in sides]]
    status = game.get("status",{}).get("type",{})
    if not status.get("completed") or status.get("state") != "post":
        return None
    state = status.get("name")
    if state in {"STATUS_WALKOVER","STATUS_WALK_OVER"}:
        return binding, {"score":"W/O","result":"Void","profit":0,"settled_stake":0}
    is_games = ticket.get("market") in ("spreads","totals")
    retired = state in {"STATUS_RETIRED","STATUS_RETIREMENT","STATUS_DISQUALIFIED","STATUS_DEFAULT","STATUS_DEFAULTED"}
    if retired and is_games:
        return binding, {"score":"Retired","result":"Void","profit":0,"settled_stake":0}
    if (not retired and state != "STATUS_FINAL") or any(type(s.get("winner")) is not bool for s in sides) or sum(s["winner"] for s in sides) != 1:
        return None
    winner,loser = sorted(sides,key=lambda p:not p["winner"])
    w,l = (p.get("linescores",[]) for p in (winner,loser))
    if not isinstance(w,list) or not isinstance(l,list) or len(w)!=len(l) or any(not isinstance(s,dict) or type(s.get("value")) not in (int,float) or not float(s["value"]).is_integer() for s in [*w,*l]):
        return None
    sets = [(int(a["value"]),int(b["value"])) for a,b in zip(w,l)]
    if retired:
        while len(sets) > 1 and sets[-1] == (0,0):
            sets.pop()
    score = " ".join(f"{a}-{b}" for a,b in sets)
    picked_winner = normal(winner["athlete"]["displayName"])==names[0]
    if retired:
        grade = retirement_grade(ticket, score + " RET", picked_winner)
        return (binding, grade) if grade else None
    if not completed_score(score,2):
        return None
    if is_games:
        from desk_games import grade
        return binding, {"score":score, **grade(ticket,sets,picked_winner)}
    return binding, {"score":score,"result":"Won" if picked_winner else "Lost"}


def wta_scoreboard(day):
    response = requests.get("https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard",
                            params={"dates":day.replace("-","")}, timeout=12, allow_redirects=False)
    response.raise_for_status()
    events = response.json()["events"]
    if not isinstance(events,list):
        raise ValueError("Invalid women's singles scoreboard")
    return events


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
        womens = ticket["tour"] in ("WTA", "WTA 125")
        if womens and now < start:
            continue
        due.setdefault((ticket["start"][:10],womens),{})[mid] = ticket
    if not due:
        return
    resolved = defaultdict(dict)
    for (day,womens), group in due.items():
        if womens:
            try:
                events = wta_scoreboard(day)
            except (requests.RequestException, KeyError, ValueError) as exc:
                print(f"WTA score check unavailable for {day}: {type(exc).__name__}.")
                for ticket in group.values():
                    ticket["last_check"] = now.isoformat()
                continue
        else:
            tours, schedule, games, names = event_data(list(group.values()))
        for mid,ticket in group.items():
            if womens:
                graded = wta_result(ticket,events)
                result = None
                if graded:
                    ticket["binding"], result = graded
            else:
                if not ticket.get("binding"):
                    ticket["binding"] = bind(ticket,tours,schedule,games,names)
                result = outcome(ticket,games,schedule,now)
            ticket["last_check"] = now.isoformat()
            if result:
                resolved[ticket["after"][:10]][mid] = {**result,**{k:ticket[k] for k in ("market","line","side","selection") if k in ticket},"binding":ticket["binding"],
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
            # Limit capture started at the 11:00 UTC slot on 21 November.
            missing_limits = ((day.isoformat(), name) >= ("2026-11-21", "1100.json")
                              and name not in tape.get("limit_slots", {}))
            if name in processed and name in tape["slots"] and not missing_limits:
                continue
            snap = store.get(prefix + "/" + name)
            if snap is None:
                raise ValueError("Listed scan missing")
            if name not in tape["slots"] or missing_limits:
                append_snapshot(tape,name,snap)
                changed = True
            if name in processed:
                continue
            stamp = snap["observed"]
            if utc(stamp) >= START:
                batch = store.get("drop-scans-v2/" + object_key(stamp))
                if batch is None:
                    continue
                if batch.get("alert_ids",batch["moves"]):
                    receipt = store.get("drop-deliveries-v2/" + object_key(stamp))
                    if not receipt or receipt.get("state") != "sent":
                        continue
                    delivered = set(receipt["move_ids"])
                    for m in batch["moves"]:
                        if m["move_id"] in delivered:
                            t = {k:m[k] for k in ("player","opponent","tour","league","start","after","new")}
                            t.update({k:m[k] for k in ("market","line","side","contract","selection") if k in m})
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
