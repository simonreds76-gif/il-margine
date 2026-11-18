"""Bounded, private morning screen, pre-kickoff rechecks and separate paper cohorts."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
import requests

from statshub_daily_contracts import (LEAGUES, MARKETS, contracts, fixtures, form, identity,
    load_history, norm, player_case, screen_age, team_case, utc, won)
from statshub_daily_io import Provider, Store, send_digest, timestamp

START="2026-11-20"
LAST="2026-11-23"
CLOSE="2026-11-24"
REPORT="daily/report.json"
LINK="https://ilmargine.bet/admin/statshub-daily"

class Reads:
    def __init__(self,store,api,day,phase,limit):
        self.store=store
        self.api=api
        self.prefix=f"evidence/{day}/{phase}"
        self.log=store.get(self.prefix+"/calls.json",[])
        self.limit=limit
        self.errors=0

    def read(self,name,args,slot):
        key=hashlib.sha256(json.dumps([slot,name,args],sort_keys=True).encode()).hexdigest()
        path=self.prefix+"/"+key+".json"
        cached=self.store.get(path)
        if cached is not None:
            return cached
        if len(self.log)>=self.limit: return None
        self.log.append(dict(tool=name,at=timestamp(),key=key))
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
    rows=[]
    incomplete=[]
    # One first page per league before spending requests on individual histories.
    for league in LEAGUES:
        ids=[f["id"] for f in fs if f["league"]==league]
        if not ids: continue
        args=dict(games=ids,pageSize=40,hitRateFrom=0,oddsFrom=1.01,includeStale=False,
                  hitRateScope="competition",useSupersub=False)
        result=read.read("getPropScreener",args,"am")
        if not result:
            incomplete.append(league+" player screen unavailable")
            continue
        data=result["data"]
        rows.extend({**r,"screenObservedAt":result["at"]} for r in data.get("data",[]))
        if data.get("pagination",{}).get("hasNextPage"):
            incomplete.append(league+" player screen partial")
    return rows,incomplete

def player_screen(p,rows):
    hits=[r for r in rows if identity(r.get("matchId"))==identity(p["matchId"]) and
          identity(r.get("playerId"))==identity(p["player"]) and r.get("statType")==p["stat"]
          and r.get("line")==p["line"] and r.get("oddsType")==p["direction"]]
    if len(hits)!=1: return None
    r=hits[0]
    if not (r.get("inPredictedLineup") or r.get("startedLastGame")): return None
    if not r.get("matchup") or f"favours the {'under' if p['direction']=='over' else 'over'}" in r["matchup"].lower(): return None
    if (r.get("hitRateL15") or 0)/100<=1/p["odds"]: return None
    return r

def morning(read,day,clock=timestamp,history_loader=load_history):
    found={}; notes=[]; coverage=Counter()
    league_counts={}
    for league,(competition,_) in LEAGUES.items():
        req=read.read("getFixturesByDate",dict(date=day,days=1,timeZone="Europe/London",competitionId=competition,withOdds=True),"am")
        if not req:
            notes.append(league+" fixture board unavailable")
            continue
        obj=req["data"]
        rows=fixtures(obj,day,league)
        if obj.get("fixtureCount")!=len(rows): notes.append(league+" fixture board partially parsed")
        league_counts[league]=len(rows)
        for f in rows:
            if utc(f["ko"])>utc(clock()): found[f["id"]]=f
    fs=sorted(found.values(),key=lambda f:(f["ko"],f["league"],f["id"]))
    players,player_gaps=screened_players(read,fs)
    notes+=player_gaps
    histories={league:history_loader(league,day) for league in {f["league"] for f in fs}}
    prices=[]; picks=[]; player_checks=[]
    for f in fs:
        snap=read.read("getMatchOdds",dict(matchId=f["id"],markets=MARKETS),"am")
        if not snap or not board_matches(f,snap["data"]):
            notes.append(f["home"]+" v "+f["away"]+" · odds or scheduled kickoff unverified")
            continue
        elapsed=max(0,(utc(clock())-utc(snap["at"])).total_seconds()/60)
        timed_players=[]
        for r in players:
            if identity(r.get("matchId"))!=identity(f["id"]): continue
            age=screen_age(r)
            lag=max(0,(utc(snap["at"])-utc(r["screenObservedAt"])).total_seconds()/60)
            timed_players.append({**r,"bestOddsAgeMinutes":age+lag} if age is not None else r)
        offered=contracts(f,snap["data"],timed_players,60-elapsed)
        coverage["boards"]+=1
        coverage["fresh"]+=len(offered)
        coverage["other"]+=sum(int(m.get("moreOutcomes") or 0) if type(m.get("moreOutcomes"))==int else int(bool(m.get("moreOutcomes"))) for m in snap["data"].get("markets",[]))
        if not offered: notes.append(f["home"]+" v "+f["away"]+" · no verified fresh standard line")
        for p in offered:
            p["at"]=snap["at"]
            if p["side"]=="player":
                row=player_screen(p,players)
                if row: player_checks.append((p,row))
            else:
                if form(p,histories[f["league"]],day) is None:
                    coverage["nohistory"]+=1
                elif team_case(p,histories[f["league"]],day): picks.append(p)
        prices.extend(offered)
    # Validate the largest history/market differences first within the daily source budget.
    player_checks.sort(key=lambda pair:-(pair[1]["hitRateL15"]/100-1/pair[0]["odds"]))
    for p,r in player_checks:
        args=dict(playerId=p["player"],statType=p["stat"],limit=20,appearances="starts",competitionId=LEAGUES[p["league"]][0])
        hist=read.read("getPlayerStats",args,"am")
        if not hist:
            coverage["unverified"]+=1
            continue
        if player_case(p,r,hist["data"]): picks.append(p)
    locked=utc(clock())
    picks={p["id"]:p for p in picks if utc(p["ko"])>locked and
           (locked-utc(p["at"])).total_seconds()/60+p["age"]<=60}
    ordered=sorted(picks.values(),key=lambda p:(-p["odds"]/p["minimum"],p["ko"],p["id"]))
    counts=Counter(p["matchId"] for p in ordered)
    for p in ordered:
        if counts[p["matchId"]]>1: p["risk"]+=" Other selections on this fixture are correlated."
    coverage_text=", ".join(f"{k} {v}" for k,v in league_counts.items())
    summary=(f"{coverage_text}. Verified price boards {coverage['boards']}/{len(fs)}; {len(prices)} fresh, identifiable full-time contracts. "
        f"{coverage['nohistory']} without enough venue history; {coverage['unverified']} player histories unchecked. "
        f"{len(read.log)}/{read.limit} StatsHub reads. Provider coverage is partial; unpriced, unverified and nonstandard contracts are excluded.")
    if notes: summary+="\n"+" · ".join(notes)
    return dict(picks=ordered,fixtures=len(fs),coverage=summary,at=clock(),final=True,
                completeBoards=(len(league_counts)==5 and coverage["boards"]==len(fs)
                    and not any("fixture board partially parsed" in s or "player screen unavailable" in s for s in notes)),delivery="pending")

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
        quotes_by_id={p["id"]:p for p in contracts(f,quotes["data"],rows,30)} if valid else {}
        missing_players=[p for p in group if p["player"] and p["id"] not in quotes_by_id]
        if valid and missing_players:
            params=dict(games=[fid],players=sorted({p["player"] for p in missing_players}),hitRateFrom=0,
                        oddsFrom=1.01,includeStale=False,useSupersub=False,hitRateScope="competition",pageSize=40)
            extra=read.read("getPropScreener",params,slot)
            if extra:
                for q in contracts(f,{"markets":[]},extra["data"].get("data",[]),30): quotes_by_id[q["id"]]=q
        for p in group:
            p["checks"]=p.get("checks",0)+1
            q=quotes_by_id.get(p["id"])
            named=starter(p,lineups["data"]) if p["player"] and lineups else None
            if utc(timestamp())>=utc(p["ko"]): check=note("hold","Verification finished after kickoff.")
            elif named is False: check=note("pass","Player is outside the confirmed starting XI.")
            elif not q: check=note("hold","Exact contract, schedule or fresh price unavailable.")
            elif q["odds"]<p["minimum"]: check=note("pass","Exact line fell below the morning price floor.",odds=q["odds"],book=q["book"])
            elif p["player"] and named is None: check=note("hold","Official starting XI unavailable.",odds=q["odds"],book=q["book"])
            else:
                check=note("ready","Official starter and price verified." if p["player"] else "Exact team or match price verified.",odds=q["odds"],book=q["book"])
                p.setdefault("ready",check)
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
    header=f"StatsHub Daily · {day}\n{board['fixtures']} upcoming fixtures · {len(board['picks'])} private paper candidates"
    blocks=[header]
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
    if day<=LAST and not days.get(day,{}).get("final"):
        board=morning(Reads(store,api,day,"morning",40),day)
        old={p["id"]:p for p in days.get(day,{}).get("picks",[])}
        fresh=[p for p in board["picks"] if p["id"] not in old]
        board["picks"]=[*old.values(),*fresh]
        board["final"]=board["completeBoards"] or now.strftime("%H:%M")>="10:40"
        days[day]=board
        report.update(updated=timestamp(),status="Matchweek in progress")
        store.put(REPORT,report)
    before=json.dumps(report,sort_keys=True)
    all_picks=[p for board in days.values() for p in board["picks"]]
    if day in days:
        recheck(Reads(store,api,day,"recheck",12),days[day]["picks"],now)
    if report.get("settlementDay")!=day and any(not p.get("result") and p["ko"][:10]<day for p in all_picks):
        settle(Reads(store,api,day,"settle",8),all_picks,day)
        report["settlementDay"]=day
    report["summary"]=accounting(all_picks)
    if day==CLOSE: report["status"]="Pilot closed · unresolved settlements retained for review"
    if json.dumps(report,sort_keys=True)!=before:
        report["updated"]=timestamp()
        store.put(REPORT,report)
    if day in days and days[day]["final"] and days[day].get("delivery")!="sent":
        send_digest(store,day,digest(day,days[day]))
        days[day]["delivery"]="sent"
        report["updated"]=timestamp()
        store.put(REPORT,report)
