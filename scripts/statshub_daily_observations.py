"""Retain bounded private matchweek evidence independently of selection and delivery."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from statshub_daily_board import CLOSE, LAST, REPORT, START, Reads, board_matches, screen_age
from statshub_daily_contracts import LEAGUES, MARKETS, contracts, fixtures, identity, norm, utc, won
from statshub_daily_io import Provider, Store, timestamp

PREFIX = "research/cm-tackles-v1"
ROLES = {"CM", "LCM", "RCM"}


def archive_key(slot, tool, args):
    return hashlib.sha256(json.dumps([slot, tool, args], sort_keys=True).encode()).hexdigest()


def lookup(store, day, phase, slot, tool, args):
    key = archive_key(slot, tool, args)
    return store.get(f"evidence/{day}/{phase}/{key}.json")


def original_opportunities(store, day, board):
    """Use the same cached inputs, ordered fixture IDs and quote-age arithmetic as morning()."""
    found = {}
    gaps = Counter()
    excluded = []
    candidates = []
    stop = utc(board["at"])
    for league, (competition, _) in LEAGUES.items():
        args = dict(date=day, days=1, timeZone="Europe/London", competitionId=competition)
        envelope = lookup(store, day, "morning", "am", "getFixturesByDate", args)
        if not envelope:  # Older saved fixture boards also requested summary odds.
            envelope = lookup(store, day, "morning", "am", "getFixturesByDate", {**args,"withOdds":True})
        if not envelope:
            gaps["missing fixture board"] += 1
            continue
        slate = sorted(fixtures(envelope["data"], day, league), key=lambda f: (f["ko"], f["id"]))
        slate = [f for f in slate if utc(f["ko"]) > utc(envelope["at"])]
        if not slate:
            continue
        args = dict(games=[f["id"] for f in slate], pageSize=40, hitRateFrom=0, oddsFrom=1.01,
                    includeStale=False, hitRateScope="competition", useSupersub=False)
        screen = lookup(store, day, "morning", "am", "getPropScreener", args)
        if not screen:
            gaps["missing original player screen"] += 1
            continue
        if screen["data"].get("pagination", {}).get("hasNextPage"):
            gaps["partial league screen"] += 1
        for f in slate:
            snap = lookup(store, day, "morning", "am", "getMatchOdds", dict(matchId=f["id"], markets=MARKETS))
            if not snap or not board_matches(f, snap["data"]):
                gaps["unverified original fixture odds"] += 1
                continue
            raw = [r for r in screen["data"].get("data", []) if identity(r.get("matchId"))==identity(f["id"])]
            timed = []
            lag = max(0, (utc(snap["at"])-utc(screen["at"])).total_seconds()/60)
            for r in raw:
                age = screen_age(r)
                timed.append({**r, "bestOddsAgeMinutes": age+lag} if age is not None else r)
            age_limit = 60 - max(0, (stop-utc(snap["at"])).total_seconds()/60)
            offered = [p for p in contracts(f, snap["data"], timed, age_limit) if p["stat"]=="tackles"]
            for p in offered:
                hits = [r for r in raw if r.get("statType")=="tackles" and
                        identity(r.get("playerId"))==identity(p["player"]) and r.get("line")==p["line"]
                        and r.get("oddsType")==p["direction"]]
                candidates.append((dict(p, at=snap["at"], lock=board["at"]), hits))
                found[p["id"]] = True
            for r in raw:
                if r.get("statType")=="tackles" and not any(identity(p["player"])==identity(r.get("playerId"))
                        and p["direction"]==r.get("oddsType") and p["line"]==r.get("line") for p in offered):
                    gaps["screen row without a qualifying fresh exact price"] += 1
                    excluded.append(dict(matchId=f["id"],source="morning screen",player=r.get("playerId"),
                                         line=r.get("line"),side=r.get("oddsType"),book=r.get("bestBookmakerName"),
                                         price=r.get("bestOdds"),ageAtSource=r.get("bestOddsAgeMinutes",r.get("bestOddsAge")),
                                         at=screen["at"],reason="no qualifying fresh exact price"))
            for market in snap["data"].get("markets",[]):
                if market.get("name")!="Player Tackles":
                    continue
                for offer in market.get("outcomes",[]):
                    label=offer.get("label","")
                    if any(norm(label)==norm(f"{p['playerName']} {p['direction']} {p['line']}") for p in offered):
                        continue
                    excluded.append(dict(matchId=f["id"],source="morning board",label=label,
                                         best=offer.get("best"),at=snap["at"],
                                         reason="unmapped player, unsupported contract or unverified fresh price"))
    if len(found)!=len(candidates):
        raise ValueError("Duplicate original tackle contract")
    return candidates, dict(gaps), excluded


def historical_values(history, row, p):
    stat = history.get("requestedStat") or {}
    if stat.get("statType")!="tackles" or not stat.get("column"):
        return [], "unverified tackle field"
    col = stat["column"]
    clubs = (history.get("span") or {}).get("teams") or []
    single = len(clubs)==1 and norm(clubs[0])==norm(row["teamName"])
    rows = ([dict(zip(history["matchColumns"], v)) for v in history.get("matchRows", [])]
            if "matchColumns" in history else history.get("matches", []))
    values = []
    seen = set()
    for v in rows:
        if not v.get("date") or v["date"]>=p["ko"][:10]:
            return [], "invalid history chronology"
        if not v.get("team") and not single:
            return [], "unresolved historical club"
        if v.get("team") and norm(v["team"])!=norm(row["teamName"]):
            continue
        mid = identity(v.get("matchId"))
        if not mid or mid in seen or mid==identity(p["matchId"]):
            return [], "duplicate or unresolved historical fixture"
        seen.add(mid)
        count = v.get(col)
        if type(count)!=int or count<0:
            return [], "missing tackle count"
        values.append(count)
    if not 10<=len(values)<=20:
        return [], "insufficient verified starts"
    return values, "single-club span" if any(not v.get("team") for v in rows) else "per-row club"


def opening_role(p,document):
    xi=document.get("lineups") or {}
    if not p.get("teamId") or identity(xi.get("matchId"))!=identity(p["matchId"]):
        return None
    for side in ("home","away"):
        team=xi.get(side) or {}
        if identity(team.get("teamId"))!=identity(p["teamId"]) or team.get("status")!="confirmed":
            continue
        roster=team.get("players") or []
        ids=[identity(person.get("id")) for person in roster]
        if len(set(ids))!=11 or len(ids)!=11 or "" in ids:
            return None
        target=identity(p["player"])
        return roster[ids.index(target)].get("position") if target in ids else "nonstarter"
    return None


def final_count(p,doc):
    data=doc.get("data") or {}
    match=data.get("matches") or {}
    if (match.get("status")!="finished" or identity(match.get("id"))!=identity(p["matchId"])
        or match.get("kickoffTimestamp")!=int(utc(p["ko"]).timestamp())
        or any(norm((data.get(s+"Team") or {}).get("name",""))!=norm(p[s]) for s in ("home","away"))):
        return None
    players=doc.get("players") or {}
    for side in ("home","away"):
        team=players.get(side) or {}
        if identity(team.get("teamId"))!=identity(p["teamId"]):
            continue
        rows=[r for r in team.get("rows",[]) if identity(r.get("playerId"))==identity(p["player"])]
        if len(rows)!=1:
            return None
        value=rows[0].get("tackles")
        if value is None and "a stat missing from a row is 0" in players.get("shown","").lower():
            value=0
        minutes=rows[0].get("minutes")
        if type(value)==int and value>=0 and type(minutes) in (int,float) and 0<minutes<=130:
            return dict(tackles=value,minutes=minutes)
    return None


def resolve(store,api,day,locks):
    grouped=defaultdict(list)
    for lock in locks:
        for p in lock["records"]:
            if p.get("teamId") and p["ko"][:10]<day:
                grouped[p["matchId"]].append(p)
    answers={}
    read=Reads(store,api,day,"cm-settle",24)
    for fid,group in sorted(grouped.items()):
        path=f"{PREFIX}/results/{identity(fid)}.json"
        saved=store.get(path)
        if saved:
            answers.update(saved)
            continue
        xi=read.read("getLineups",dict(matchId=fid),"xi")
        if not xi:
            continue
        roles={p["id"]:opening_role(p,xi["data"]) for p in group}
        doc=None
        if any(role in ROLES for role in roles.values()):
            args=dict(matchId=fid,include=["players","teamStats"],allPlayers=True)
            doc=(lookup(store,day,"settle","ft","getMatchDetails",args)
                 or read.read("getMatchDetails",args,"final"))
        subset={}
        for p in group:
            role=roles[p["id"]]
            result=final_count(p,doc["data"]) if doc and role in ROLES else None
            subset[p["id"]]=dict(role=role,result=result,xiAt=xi["at"],resultAt=doc["at"] if doc else None)
        answers.update(subset)
        if all(v["role"] and (v["role"] not in ROLES or v["result"]) for v in subset.values()):
            store.put(path,subset,replace=False)
    return answers


def freeze(store,api,day,board):
    path=f"{PREFIX}/{day}/observations.json"
    if store.get(path) is not None:
        return
    offered,gaps,excluded=original_opportunities(store,day,board)
    read=Reads(store,api,day,"cm-history",20)
    history={}
    saved=[]
    for quote,rows in sorted(offered,key=lambda x:(x[0]["ko"],x[0]["id"])):
        key=quote["league"]+"|"+quote["player"]
        if len(rows)==1 and key not in history and utc(timestamp())<utc(quote["ko"]):
            args=dict(playerId=quote["player"],statType="tackles",limit=20,appearances="starts",
                      competitionId=LEAGUES[quote["league"]][0])
            history[key]=(lookup(store,day,"morning","am","getPlayerStats",args)
                          or read.read("getPlayerStats",args,"cm"))
        record=dict(quote=quote,screen=rows,historyKey=key)
        if len(rows)==1:
            quote["teamId"]=rows[0].get("teamId")
            evidence=history.get(key)
            if evidence and utc(evidence["at"])<utc(quote["ko"]):
                values,quality=historical_values(evidence["data"],rows[0],quote)
                record["historyStatus"]=quality
                if values:
                    hits=sum(won(quote,v,0) for v in values)
                    record["priorHits"]=hits
                    record["priorStarts"]=len(values)
                    record["historyProbability"]=(hits+0.5)/(len(values)+1)
        saved.append(record)
    at=timestamp()
    for record in saved:
        if utc(record["quote"]["ko"])<=utc(at):
            record.pop("historyProbability",None)
            record["historyStatus"]="late research lock"
    issued=[p for p in board["picks"] if p["stat"]=="tackles"]
    obj=dict(day=day,lockedAt=at,boardAt=board["at"],coverage=gaps,excluded=excluded,
             observations=saved,histories=history,issued=issued)
    obj["sha256"]=hashlib.sha256(json.dumps(obj,sort_keys=True,allow_nan=False).encode()).hexdigest()
    store.put(path,obj,replace=False)


def run():
    now=datetime.now(timezone.utc)
    day=now.date().isoformat()
    if not START<=day<=CLOSE or now.hour<10:
        return
    store=Store()
    receipt=f"{PREFIX}/{day}/observed.json"
    if store.get(receipt):
        return
    report=store.get(REPORT) or {}
    if report.get("pilot")!=START:
        return
    api=Provider(store)
    if day<=LAST:
        board=report.get("days",{}).get(day,{})
        if not board.get("final"):
            return
        freeze(store,api,day,board)
    from statshub_daily_cm import project, summarize
    previous=[]
    locked=[]
    date=datetime.fromisoformat(START).date()
    while date.isoformat()<=min(day,LAST):
        doc=store.get(f"{PREFIX}/{date}/observations.json")
        if doc:
            locked.append(project(doc))
            if date.isoformat()<day:
                previous.append(dict(records=[r["quote"] for r in doc["observations"]]))
        date+=timedelta(days=1)
    answers=resolve(store,api,day,previous)
    # Never regress an earlier verified result if today's provider read is partial.
    date=datetime.fromisoformat(START).date()
    while date.isoformat()<day:
        old=store.get(f"{PREFIX}/{date}/settlement-check.json") or {}
        for key,value in old.items():
            if (value.get("result") and not (answers.get(key) or {}).get("result")) or (
                    value.get("role") and not (answers.get(key) or {}).get("role")):
                answers[key]=value
        date+=timedelta(days=1)
    store.put(f"{PREFIX}/{day}/settlement-check.json",answers)
    store.put(f"{PREFIX}/summary.json",dict(asOf=timestamp(),**summarize(locked,answers)))
    store.put(receipt,dict(at=timestamp(),previousDays=len(previous)),replace=False)


if __name__=="__main__":
    import sys
    if sys.argv[1:]==["--check"]:
        from statshub_daily_cm import summarize
        store=Store()
        report=store.get(REPORT) or {}
        if report.get("pilot")!=START or summarize([], {})["portfolios"]["actual"]["roi"] is not None:
            raise RuntimeError("Private pilot or research accounting check failed")
        print("Private pilot accessible; zero-stake comparison and research imports verified.")
    else:
        run()
