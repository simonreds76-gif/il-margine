"""Private research leads from player reports and same-line bookmaker comparisons."""
import re
from statistics import median

from statshub_daily_contracts import LEAGUES, PLAYER_PRICE_MIN, PLAYER_STATS, identity, norm, utc


def sample(report, label, direction):
    record=next((s for s in report.get("samples",[]) if s.get("label")==label),{})
    hits,starts=record.get("hits"),record.get("starts")
    if type(hits)!=int or type(starts)!=int or not 0<=hits<=starts or starts<10:
        return None
    # For an integer count at a half-line, under and over are complements.
    return (hits if direction=="over" else starts-hits,starts)


def player_evidence(row,fixture,report):
    match=report.get("fixture") or {}
    bet=report.get("bet") or {}
    changes=report.get("changes") or {}
    available=report.get("availability") or {}
    if (norm(report.get("player",""))!=norm(row["playerName"]) or
        bet.get("statType")!=row["statType"] or bet.get("line")!=row["line"] or
        not isinstance(match.get("isHome"),bool) or
        norm(row.get("teamName",""))!=norm(fixture["home" if match["isHome"] else "away"]) or
        identity(match.get("competitionId"))!=identity(LEAGUES[fixture["league"]][0]) or
        match.get("kickoffTimestamp")!=int(utc(fixture["ko"]).timestamp()) or
        any(norm(match.get(side,""))!=norm(fixture[side]) for side in ("home","away")) or
        available.get("lineup") not in ("in the predicted XI","in the confirmed XI") or
        not changes.get("currentPosition") or (changes.get("startsAtClub") or 0)<10):
        return None
    role=changes["currentPosition"]
    labels=["Last 20 starts","In this competition","At "+role,"Home starts" if match.get("isHome") else "Away starts"]
    groups=[sample(report,label,row["oddsType"]) for label in labels]
    if not all(groups): return None
    return dict(groups=groups,role=role,lineup=available["lineup"],venue=labels[-1].split()[0].lower())


def odds_comparison(row,fixture,snapshot):
    filters=snapshot.get("filtersApplied") or {}
    freshness=filters.get("prices") or ""
    if (identity(filters.get("matchId"))!=identity(fixture["id"]) or
        not re.search(r"prices older than 6 hours are left out",freshness,re.I)):
        return None
    matches=[r for r in snapshot.get("data",[]) if identity(r.get("playerId"))==identity(row["playerId"]) and
             r.get("marketKey")==row["statType"] and r.get("line")==row["line"] and
             str(r.get("marketType","")).lower()==row["oddsType"] and
             all(norm(r.get(side+"Team",""))==norm(fixture[side]) for side in ("home","away"))]
    if len(matches)!=1: return None
    books={}
    for entry in matches[0].get("bookmakers",[]):
        name,odds=entry.get("bookmaker"),entry.get("odd")
        if not name or type(odds) not in (int,float) or not 1<odds<=100: continue
        if name in books and books[name]!=odds: return None
        books[name]=odds
    if not books: return None
    return dict(best=max(books.values()),books=books,median=median(books.values()),freshness=freshness)


def strength(evidence,odds):
    # Rank consistency across overlapping samples. This is not an EV estimate.
    return min(h/n for h,n in evidence["groups"])-1/odds


def scouting(reader,cases,picks,clock):
    issued={(identity(p["matchId"]),identity(p["player"])) for p in picks}
    pool=[(r,f,trial) for _,r,f,trial in cases if (identity(f["id"]),identity(r["playerId"])) not in issued]
    checked=0; possibles=[]
    # Keep some of the existing matchup budget for exact bookmaker odds.
    for start in range(0,min(len(pool),6*(reader.limit//2)),6):
        group=pool[start:start+6]
        args=[dict(matchId=f["id"],playerId=r["playerId"],statType=r["statType"],line=r["line"]) for r,f,_ in group]
        response=reader.read("checkBet",{"bets":args},"player-report")
        if not response: continue
        doc=response["data"]
        reports=doc.get("bets",[doc] if len(group)==1 else [])
        if len(reports)!=len(group): continue
        for (row,f,trial),report in zip(group,reports):
            if report.get("error"): continue
            evidence=player_evidence(row,f,report)
            if not evidence: continue
            checked+=1
            score=strength(evidence,trial["odds"])
            if score>0: possibles.append((score,row,f,evidence))
    leads={}
    for _,row,f,evidence in sorted(possibles,key=lambda item:-item[0]):
        if utc(f["ko"])<=utc(clock()): continue
        args=dict(matchId=f["id"],search=row["playerName"],market=[row["statType"]],line=row["line"],
                  includeStale=False,minBookmakers=1,minOdds=1.01,maxOdds=100,limit=5)
        snap=reader.read("getOutliers",args,"same-line")
        if not snap or not 0<=(utc(clock())-utc(snap["at"])).total_seconds()<=3600: continue
        comparison=odds_comparison(row,f,snap["data"])
        if not comparison or comparison["best"]<PLAYER_PRICE_MIN: continue
        odds=comparison["best"]; rank=strength(evidence,odds)
        key=(identity(f["id"]),identity(row["playerId"]))
        if rank<=0 or (key in leads and rank<=leads[key]["rank"]): continue
        books=comparison["books"]; names=" / ".join(k for k,v in books.items() if v==odds)
        recent,league,role,venue=(f"{h}/{n}" for h,n in evidence["groups"])
        label=f"{row['playerName']} {row['oddsType']} {row['line']:g} {PLAYER_STATS[row['statType']]}"
        reference=f", Bet365 {books['Bet365']:.2f}" if 'Bet365' in books else ""
        market_note=(f"{len(books)} bookmaker listings, median {comparison['median']:.2f}{reference}."
                     if len(books)>1 else "One bookmaker in the comparison.")
        text=(f"{f['home']} v {f['away']} · {label} @ {odds:.2f} {names}. Break-even {100/odds:.1f}%. "
              f"Last 20 club starts {recent}, league {league}, {evidence['role']} {role}, {evidence['venue']} {venue}. "
              f"{market_note} Checked {snap['at'][11:16]} UTC. "
              f"Opponent: {row['matchup']}. Recheck the starting XI and offered odds before posting.")
        leads[key]=dict(label=label,fixture=f["id"],player=row["playerId"],rank=rank,checkedAt=snap["at"],
                        evidence=evidence,comparison=comparison,text=text,kickoff=f["ko"])
    return dict(checked=checked,candidates=len(pool),leads=sorted(
        (p for p in leads.values() if utc(p["kickoff"])>utc(clock())),key=lambda p:-p["rank"]))
