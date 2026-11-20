"""Bounded, private morning screen, pre-kickoff rechecks and separate paper cohorts."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
import requests

from statshub_daily_contracts import (LEAGUES, PLAYER_STATS, PLAYER_PRICE_MIN, PLAYER_POLICY, contracts, fixtures, identity,
    load_history, norm, player_case, screen_age, utc, won)
from statshub_daily_focus import FOCUS_LIMIT, add_focus, opponent_recheck
from statshub_daily_io import Provider, Store, send_digest, timestamp

START="2026-11-20"
LAST="2026-11-23"
CLOSE="2026-11-24"
REPORT="daily/report.json"
LINK="https://ilmargine.bet/admin/statshub-daily"
PRICE_FILTERS=["player shots","player tackles","player fouls"]

def screen_request(ids,page):
    return dict(games=ids,statTypes=list(PLAYER_STATS),page=page,pageSize=40,hitRateOption="L15",
                sortColumn="L15",hitRateFrom=0,oddsFrom=PLAYER_PRICE_MIN,oddsTo=100,
                includeStale=False,hitRateScope="competition",lineupFilterType="predicted",useSupersub=False)

class Reads:
    def __init__(self,store,api,day,phase,limit):
        self.store=store
        self.api=api
        self.prefix=f"evidence/{day}/{phase}"
        self.log=store.get(self.prefix+"/calls.json",[])
        self.keys={entry["key"] for entry in self.log}
        self.limit=limit
        self.errors=0

    def read(self,name,args,slot):
        key=hashlib.sha256(json.dumps([slot,name,args],sort_keys=True).encode()).hexdigest()
        path=self.prefix+"/"+key+".json"
        if key not in self.keys and len(self.log)>=self.limit: return None
        cached=self.store.get(path)
        if cached is not None:
            return cached
        if len(self.log)>=self.limit: return None
        self.log.append(dict(tool=name,at=timestamp(),key=key))
        self.keys.add(key)
        self.store.put(self.prefix+"/calls.json",self.log)
        try:
            response=self.api.read(name,args)
        except (RuntimeError,ValueError,TimeoutError,requests.RequestException):
            self.errors+=1
            return None
        observed=dict(data=response,at=timestamp())
        self.store.put(path,observed)
        return observed

def board_matches(f,doc):
    ctx=doc.get("context","")
    expected=utc(f["ko"]).strftime("%d %b %Y, %H:%M UTC").lstrip("0")
    header=ctx.split(" · ",1)[0]
    return norm(header)==norm(f["home"]+" v "+f["away"]) and expected in ctx and not re.search(r"postponed|cancelled|abandoned|in.play|full time",ctx,re.I)

def screened_players(read,fs):
    rows=[]; notes=[]
    groups={league:[f["id"] for f in fs if f["league"]==league] for league in LEAGUES}
    groups={league:ids for league,ids in groups.items() if ids}
    for page in (1,2):
        for league,ids in list(groups.items()):
            args=screen_request(ids,page)
            result=read.read("getPropScreener",args,"am")
            if not result:
                notes.append(league+" player screen unavailable")
                del groups[league]
                continue
            data=result["data"]
            for r in data.get("data",[]):
                row={**(data.get("everyRow") or {}),**r,"screenObservedAt":result["at"]}
                if row.get("statType") in PLAYER_STATS and row.get("playerId") and row.get("teamId"):
                    rows.append(row)
            if not data.get("pagination",{}).get("hasNextPage"): del groups[league]
    notes.extend(league+" player screen partial" for league in groups)
    return rows,notes

def player_screen(p,r):
    if not r.get("inPredictedLineup") or not r.get("teamName") or not r.get("teamId"): return False
    opposite="under" if p["direction"]=="over" else "over"
    matchup=r.get("matchup") or ""
    return bool(matchup and f"favours the {opposite}" not in matchup.lower()
                and (r.get("hitRateL15") or 0)/100>1/p["odds"])

def row_key(r):
    return (identity(r.get("matchId")),identity(r.get("playerId")),r.get("statType"),r.get("oddsType"),r.get("line"))

def pick_key(p):
    return (identity(p["matchId"]),identity(p["player"]),p["stat"],p["direction"],p["line"])

def distinct_players(picks):
    ranked=sorted(picks,key=lambda p:(-p["odds"]/p["minimum"],p["ko"],p["id"]))
    chosen={}
    for p in ranked:
        chosen.setdefault((identity(p["matchId"]),identity(p["player"])),p)
    return list(chosen.values())

def dated_movement(reader,fixture,row,clock,slot,max_age):
    args=dict(matchId=fixture["id"],playerId=row["playerId"],movementMarket=row["statType"],
              movement=True,line=row["line"],selection=row["oddsType"])
    snap=reader.read("getMatchOdds",args,slot)
    if not snap: return []
    doc=snap["data"]
    if not board_matches(fixture,doc) or doc.get("movementMarket")!=row["statType"]: return []
    quotes=[]
    for item in doc.get("rows",[]):
        if (identity(item.get("playerId"))!=identity(row["playerId"]) or item.get("line")!=row["line"]
            or item.get("selection")!=row["oddsType"]): continue
        # A recent change proves a recent observation. An old change gives no such evidence.
        date=item.get("lastMove") or item.get("firstSeenAt")
        if not date or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}",date): continue
        age=(utc(snap["at"])-utc(date+"+00:00")).total_seconds()/60
        elapsed=max(0,(utc(clock())-utc(snap["at"])).total_seconds()/60)
        if not 0<=age<=max_age-elapsed: continue
        value={**row,"bestOdds":item.get("current"),"bestBookmakerName":item.get("bookmaker"),"bestOddsAgeMinutes":age}
        quotes.extend(dict(p,at=snap["at"]) for p in contracts(fixture,{},[value],max_age-elapsed))
    return quotes

def morning(read,day,clock=timestamp,focus_read=None):
    found={}; notes=[]; league_counts={}
    for league,(competition,_) in LEAGUES.items():
        req=read.read("getFixturesByDate",dict(date=day,days=1,timeZone="Europe/London",competitionId=competition),"am")
        if not req:
            notes.append(league+" fixture board unavailable")
            continue
        obj=req["data"]; rows=fixtures(obj,day,league)
        if obj.get("fixtureCount")!=len(rows): notes.append(league+" fixture board partially parsed")
        league_counts[league]=len(rows)
        for f in rows:
            if utc(f["ko"])>utc(clock()): found[identity(f["id"])]=f
    fs=sorted(found.values(),key=lambda f:(f["ko"],f["league"],f["id"]))
    players,gaps=screened_players(read,fs)
    notes+=gaps
    by_key={row_key(r):r for r in players}
    offers={}
    def retain(p,at):
        if p["side"]!="player" or p["stat"] not in PLAYER_STATS or p["odds"]<PLAYER_PRICE_MIN: return
        key=pick_key(p)
        if key not in by_key: return
        if key not in offers or p["odds"]>offers[key]["odds"]: offers[key]=dict(p,at=at)

    verified=set()
    for f in fs:
        members=[r for k,r in by_key.items() if k[0]==identity(f["id"])]
        for r in members:
            at=r["screenObservedAt"]; elapsed=max(0,(utc(clock())-utc(at)).total_seconds()/60)
            for p in contracts(f,{},[r],60-elapsed): retain(p,at)
        snap=read.read("getMatchOdds",dict(matchId=f["id"],markets=PRICE_FILTERS),"am")
        if not snap or not board_matches(f,snap["data"]):
            notes.append(f["home"]+" v "+f["away"]+" price board unavailable")
            continue
        verified.add(identity(f["id"]))
        # Rows here identify players only. Prices from the screener retain their own observation time.
        identifiers=[dict(matchId=r["matchId"],playerId=r["playerId"],playerName=r["playerName"],statType=r["statType"]) for r in members]
        elapsed=max(0,(utc(clock())-utc(snap["at"])).total_seconds()/60)
        for p in contracts(f,snap["data"],identifiers,60-elapsed): retain(p,snap["at"])

    cases=[]
    for key,r in by_key.items():
        f=found.get(key[0])
        if not f or key[0] not in verified or key[3] not in ("over","under") or type(key[4]) not in (int,float) or key[4]%1!=0.5: continue
        indicative=r.get("bestOdds")
        quoted=offers.get(key)
        odds=max(indicative if type(indicative) in (int,float) else 0,(quoted or {}).get("odds",0))
        if odds<PLAYER_PRICE_MIN: continue
        p=dict(ko=f["ko"],side="player",direction=key[3],stat=key[2],odds=odds,line=key[4])
        if player_screen(p,r): cases.append((key,r,f,p))
    cases.sort(key=lambda c:(c[0] not in offers,-(c[1]["hitRateL15"]/100-1/c[3]["odds"]),c[0]))
    picks=[]; histories={}; lines_checked=set(); checked=0; no_price=0
    for key,r,f,trial in cases:
        hk=(key[1],key[2],f["league"])
        if hk not in histories:
            args=dict(playerId=r["playerId"],statType=key[2],limit=20,appearances="starts",competitionId=LEAGUES[f["league"]][0])
            hist=read.read("getPlayerStats",args,"am")
            histories[hk]=hist["data"] if hist else {}
        hist=histories[hk]
        if not hist: continue
        checked+=1
        if not player_case(trial,r,hist): continue
        priced=offers.get(key)
        line_key=(key[0],key[4])
        if (not priced or priced["odds"]<trial["minimum"]) and line_key not in lines_checked:
            lines_checked.add(line_key)
            snap=read.read("getMatchOdds",dict(matchId=f["id"],markets=PRICE_FILTERS,line=key[4]),"am")
            if snap and board_matches(f,snap["data"]):
                ids=[{name:v[name] for name in ("matchId","playerId","playerName","statType")}
                     for k,v in by_key.items() if k[0]==key[0]]
                elapsed=max(0,(utc(clock())-utc(snap["at"])).total_seconds()/60)
                for p in contracts(f,snap["data"],ids,60-elapsed): retain(p,snap["at"])
            priced=offers.get(key)
        if not priced or priced["odds"]<trial["minimum"]:
            for p in dated_movement(read,f,r,clock,"am",60): retain(p,p["at"])
            priced=offers.get(key)
        if not priced or priced["odds"]<trial["minimum"]:
            no_price+=1
            continue
        if player_screen(priced,r) and player_case(priced,r,hist):
            priced["label"]=f"{r['playerName']} · {key[3]} {key[4]:g} {PLAYER_STATS[key[2]]}"
            picks.append(priced)
    now=utc(clock())
    current=[p for p in picks if utc(p["ko"])>now and p["age"]+(now-utc(p["at"])).total_seconds()/60<=60]
    ordered=distinct_players(current)
    counts=", ".join(f"{name} {n}" for name,n in league_counts.items())
    summary=(f"{counts}. {len(by_key)} player lines screened; {checked}/{len(cases)} preliminary lines had their individual history checked. "
             f"{len(offers)} exact fresh prices at {PLAYER_PRICE_MIN:.2f} or higher; {no_price} history qualifiers lacked a verified qualifying price.")
    if notes: summary+="\n"+" · ".join(notes)
    board=dict(picks=ordered,policy=PLAYER_POLICY,fixtures=len(fs),coverage=summary,at=clock(),final=True,delivery="pending",
               completeBoards=(len(league_counts)==5 and len(verified)==len(fs) and not any("unavailable" in s or "partially parsed" in s for s in notes)))
    if focus_read is not None and ordered:
        try:
            add_focus(board,focus_read,fs,list(offers.values()),clock,board_matches)
        except (ValueError,TypeError,KeyError,RuntimeError,TimeoutError,requests.RequestException):
            board["coverage"]+="\nDetailed matchup review unavailable."
    return board

def note(status,text,**values):
    return dict(status=status,note=text,at=timestamp(),**values)

def starter(p,doc):
    xi=doc.get("lineups") or {}
    if identity(xi.get("matchId"))!=identity(p["matchId"]): return None
    for side in ("home","away"):
        squad=xi.get(side) or {}
        if identity(squad.get("teamId"))!=identity(p.get("teamId")) or squad.get("status")!="confirmed": continue
        ids={identity(person.get("id")) for person in squad.get("players",[])}
        if len(ids)==11 and "" not in ids: return identity(p["player"]) in ids
    return None

def recheck(read,picks,now):
    grouped=defaultdict(list)
    for p in picks:
        mins=(utc(p["ko"])-now).total_seconds()/60
        if not p.get("check") or p["check"]["status"]=="hold":
            if 0<mins<=57 and (not p.get("check") or (mins<=30 and p.get("checks",0)<2)):
                grouped[p["matchId"]].append(p)
            elif mins<=0 and not p.get("check"):
                p["check"]=note("hold","Pre-kickoff verification window missed.")
    for fid,group in grouped.items():
        first=group[0]
        f={**first,"id":fid}
        slot=now.strftime("%H:%M")
        quotes=read.read("getMatchOdds",dict(matchId=fid,markets=list(dict.fromkeys(p["market"] for p in group))),slot)
        rows=[dict(matchId=fid,playerId=p["player"],playerName=p.get("playerName"),statType=p["stat"]) for p in group if p["player"]]
        lineups=read.read("getLineups",dict(matchId=fid),slot) if rows else None
        valid=quotes and board_matches(f,quotes["data"])
        age_limit=30-max(0,(utc(timestamp())-utc(quotes["at"])).total_seconds()/60) if valid else 0
        quotes_by_id={p["id"]:dict(p,at=quotes["at"]) for p in contracts(f,quotes["data"],rows,age_limit)} if valid else {}
        missing_players=[p for p in group if p["player"] and p["id"] not in quotes_by_id]
        if valid and missing_players:
            params=dict(games=[fid],players=sorted({p["player"] for p in missing_players}),hitRateFrom=0,
                        oddsFrom=1.01,includeStale=False,useSupersub=False,hitRateScope="competition",pageSize=40)
            extra=read.read("getPropScreener",params,slot)
            if extra:
                age_limit=30-max(0,(utc(timestamp())-utc(extra["at"])).total_seconds()/60)
                for q in contracts(f,{},extra["data"].get("data",[]),age_limit): quotes_by_id[q["id"]]=dict(q,at=extra["at"])
        for p in group:
            p["checks"]=p.get("checks",0)+1
            q=quotes_by_id.get(p["id"])
            if valid and not q and p.get("stat") in PLAYER_STATS:
                row=dict(playerName=p["playerName"],playerId=p["player"],matchId=fid,line=p["line"],
                         oddsType=p["direction"],statType=p["stat"])
                q=max(dated_movement(read,f,row,timestamp,slot,30),key=lambda item:item["odds"],default=None)
            if q and q["age"]+(utc(timestamp())-utc(q["at"])).total_seconds()/60>30: q=None
            named=starter(p,lineups["data"]) if p["player"] and lineups else None
            if utc(timestamp())>=utc(p["ko"]): check=note("hold","Verification finished after kickoff.")
            elif named is False: check=note("pass","Player is outside the confirmed starting XI.")
            elif not q: check=note("hold","Exact contract, schedule or fresh price unavailable.")
            elif q["odds"]<p["minimum"]: check=note("pass","Exact line fell below the morning price floor.",odds=q["odds"],book=q["book"])
            elif p["player"] and named is None: check=note("hold","Official starting XI unavailable.",odds=q["odds"],book=q["book"])
            else:
                check=note("ready","Official starter and price verified." if p["player"] else "Exact team or match price verified.",odds=q["odds"],book=q["book"])
                p.setdefault("ready",check)
            if lineups and p.get("focusOpponent"):
                check["note"]+=opponent_recheck(p,lineups["data"])
            p["check"]=check

def outcome(p,doc):
    data=doc.get("data") or {};match=data.get("matches") or {}
    if (match.get("status")!="finished" or identity(match.get("id"))!=identity(p["matchId"])
        or any(norm((data.get(side+"Team") or {}).get("name",""))!=norm(p[side]) for side in ("home","away"))
        or match.get("kickoffTimestamp")!=int(utc(p["ko"]).timestamp())): return None
    if p["side"]=="player":
        players=doc.get("players") or {}
        roster=next((players.get(s) for s in ("home","away") if identity((players.get(s) or {}).get("teamId"))==identity(p["teamId"])),None)
        persons=[r for r in (roster or {}).get("rows",[]) if identity(r.get("playerId"))==identity(p["player"])]
        # A complete appearance is unambiguous across standard and substitution variants.
        if len(persons)!=1 or (persons[0].get("minutes") or 0)<90: return None
        value=persons[0].get(p["stat"])
        if value is None and "a stat missing from a row is 0" in players.get("shown","").lower() and p["stat"] in ("shots","shotsOnTarget","goals","assists"): value=0
        if type(value) not in (int,float): return None
        hit=won(p,value,0)
    elif p["stat"] in ("goals","result","btts","doubleChance","handicap"):
        final=(doc.get("score") or {}).get("final","")
        if not isinstance(final,str) or not re.fullmatch(r"\d+-\d+",final): return None
        hit=won(p,*map(int,final.split("-")))
    else:
        stats=doc.get("teamStats") or {}
        if list(map(norm,stats.get("columns",[])))!=[norm(p["home"]),norm(p["away"])]: return None
        pair=stats.get("fullTime",{}).get(p["stat"])
        if not isinstance(pair,list) or len(pair)!=2 or not all(type(x)==int and x>=0 for x in pair): return None
        hit=won(p,*pair)
    return "win" if hit else "loss"

def csv_outcome(p,history):
    from statshub_daily_contracts import ALIASES
    if p["side"]=="player": return None
    names=[norm(ALIASES.get(p[s],p[s])) for s in ("home","away")]
    matches=[r for d,r in history if d==p["ko"][:10] and r.get("Time")==p["ko"][11:16]
        and [norm(r["HomeTeam"]),norm(r["AwayTeam"])]==names]
    if len(matches)!=1:return None
    # football-data.co.uk kickoff times use UK local time. The November pilot is on GMT.
    cols={"shots":("HS","AS"),"shotsOnTarget":("HST","AST"),"corners":("HC","AC"),
        "fouls":("HF","AF"),"btts":("FTHG","FTAG"),"result":("FTHG","FTAG"),
        "goals":("FTHG","FTAG"),"handicap":("FTHG","FTAG"),"doubleChance":("FTHG","FTAG")}.get(p["stat"])
    r=matches[0]
    if not cols or not all((r.get(k) or "").isdigit() for k in cols):return None
    return "win" if won(p,*(int(r[k]) for k in cols)) else "loss"

def settle(read,picks,day):
    grouped=defaultdict(list)
    for p in picks:
        if not p.get("result") and p["ko"][:10]<day: grouped[p["matchId"]].append(p)
    histories={}
    for fid,group in sorted(grouped.items(),key=lambda item:not any(p["side"]=="player" for p in item[1])):
        doc=read.read("getMatchDetails",dict(matchId=fid,include=["players","teamStats"],allPlayers=True),"ft")
        for p in group:
            result=outcome(p,doc["data"]) if doc else None
            source="StatsHub final box score"
            if not doc and p["side"]!="player":
                if p["league"] not in histories: histories[p["league"]]=load_history(p["league"],day)
                result=csv_outcome(p,histories[p["league"]])
                source="Football-Data league final, both teams and exact kickoff"
            if result:
                p.update(result=result,settledAt=doc["at"] if doc else timestamp(),resultSource=source)
                if p.get("ready"): p["readyResult"]=result
            else:
                p["settlementNote"]="Awaiting exact final statistic, full participation or bookmaker ruling."

def accounting(picks):
    lines=[]
    for label,key in (("Morning","result"),("First verified pre-kickoff","readyResult")):
        cohort=[p for p in picks if key=="result" or p.get("ready")]
        decided=[p for p in cohort if p.get(key) in ("win","loss")]
        wins=sum(p[key]=="win" for p in decided)
        pnl=sum((p if key=="result" else p["ready"])["odds"] if p[key]=="win" else 0 for p in decided)-len(decided)
        roi=f"{100*pnl/len(decided):+.1f}%" if decided else "pending"
        lines.append(f"{label}: {wins}W/{len(decided)-wins}L · {len(cohort)-len(decided)} pending · {len(decided)}u settled · {pnl:+.2f}u · ROI {roi}.")
    return "\n".join(lines)

def digest(day,board):
    header=f"StatsHub Daily · {day}\n{board['fixtures']} upcoming fixtures · {len(board['picks'])} individual player props"
    blocks=[header+("\nCorrection: withdraw the earlier match and team selections." if board.get("corrected") else "")]
    for i,p in enumerate(board["picks"],1):
        blocks.append(f"{i}. {p['fixture']} · {p['ko'][11:16]} UK\n{p['label']} @ {p['odds']:.2f} {p['book']} (minimum {p['minimum']:.2f})\nChecked {p['at'][11:16]} UK · quote age {p['age']:.0f} min\n{p['why']}\n{p['risk']}")
    if not board["picks"]: blocks.append("No verified candidates from the assessed markets.")
    blocks.append(board["coverage"]+"\nPrice and lineup rechecks: "+LINK)
    parts=[]; current=""
    for block in blocks:
        if len((current+"\n\n"+block).encode("utf-16-le"))//2>3500 and current:
            parts.append(current); current="StatsHub Daily · continued"
        current+=("\n\n" if current else "")+block
    if current: parts.append(current)
    return parts

def run():
    now=datetime.now(timezone.utc);day=now.date().isoformat()
    if not START<=day<=CLOSE or now.hour<10: return
    store=Store();api=Provider(store)
    report=store.get(REPORT)
    if not report or report.get("pilot")!=START: raise RuntimeError("Private report unavailable")
    days=report["days"]
    prior=days.get(day,{})
    corrected=bool(prior and (prior.get("policy")!=PLAYER_POLICY or prior.get("corrected")))
    if day<=LAST and (not prior.get("final") or prior.get("policy")!=PLAYER_POLICY):
        if prior and prior.get("policy")!=PLAYER_POLICY:
            store.put(f"archive/{day}-before-player-counts.json",prior,replace=False)
        board=morning(Reads(store,api,day,"morning",40),day,focus_read=Reads(store,api,day,"matchups",FOCUS_LIMIT))
        board["corrected"]=corrected
        board["final"]=board["completeBoards"] or now.strftime("%H:%M")>="10:40"
        days[day]=board
        report.update(updated=timestamp(),status="Matchweek in progress")
        store.put(REPORT,report)
    before=json.dumps(report,sort_keys=True)
    all_picks=[p for board in days.values() for p in board["picks"]]
    if day in days:
        recheck(Reads(store,api,day,"recheck",12),days[day]["picks"],now)
        if days[day].get("focusWatch"):
            from statshub_daily_focus import recheck_watches
            try:
                recheck_watches(days[day],Reads(store,api,day,"watch-recheck",12),now,timestamp,board_matches)
            except (ValueError,TypeError,KeyError,RuntimeError,TimeoutError,requests.RequestException):
                days[day]["watchWarning"]="Matchup recheck unavailable."
    if report.get("settlementDay")!=day and any(not p.get("result") and p["ko"][:10]<day for p in all_picks):
        settle(Reads(store,api,day,"settle",8),all_picks,day)
        report["settlementDay"]=day
    report["summary"]=accounting(all_picks)
    if day==CLOSE: report["status"]="Pilot closed · unresolved settlements retained for review"
    if json.dumps(report,sort_keys=True)!=before:
        report["updated"]=timestamp()
        store.put(REPORT,report)
    if day in days and days[day]["final"] and days[day].get("delivery")!="sent":
        send_digest(store,day+"-"+PLAYER_POLICY,digest(day,days[day]))
        days[day]["delivery"]="sent"
        report["updated"]=timestamp()
        store.put(REPORT,report)
