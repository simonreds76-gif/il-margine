"""Evaluate the private quote locks without modifying the pilot or sending messages."""
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from statshub_daily_board import player_screen
from statshub_daily_contracts import player_case, price_floor, utc, won
from statshub_daily_observations import PREFIX, ROLES, historical_values, opening_role, final_count


def project(evidence):
    expected=evidence["sha256"]
    content={k:v for k,v in evidence.items() if k!="sha256"}
    if hashlib.sha256(json.dumps(content,sort_keys=True,allow_nan=False).encode()).hexdigest()!=expected:
        raise ValueError("Original private receipt integrity failure")
    issued={p["id"]:p for p in evidence["issued"]}
    rows=[]
    for item in evidence["observations"]:
        q=item["quote"]
        r=decision(q,item["screen"],evidence["histories"].get(item["historyKey"]),issued)
        if utc(evidence["lockedAt"])>=utc(q["ko"]):
            r.update(reason="research lock after kickoff",candidate=None,probability=None)
        if r["probability"]!=item.get("historyProbability") and r["reason"]!="issued price parity failure":
            raise ValueError("Probability does not reproduce sealed pre-match forecast")
        rows.append(r)
    return dict(day=evidence["day"],missingIssued=sorted(set(issued)-{r["id"] for r in rows}),records=rows)


def decision(p, rows, evidence, issued):
    baseline = issued.get(p["id"])
    record = dict(p, actual=baseline is not None, candidate=None, probability=None)
    if baseline and any(baseline.get(k)!=p.get(k) for k in ("book","odds","at","matchId","line","direction","player")):
        record["reason"] = "issued price parity failure"
        return record
    if len(rows)!=1:
        record["reason"] = "missing or ambiguous original screen"
        return record
    row = rows[0]
    record.update(teamId=row["teamId"], matchup=row.get("matchup"), l15=row.get("hitRateL15"))
    if not evidence or utc(evidence["at"])>=utc(p["ko"]):
        record["reason"] = "no pre-match player history"
        return record
    vals, source = historical_values(evidence["data"], row, p)
    if not vals:
        record["reason"] = source
        return record
    hits = sum(won(p,v,0) for v in vals)
    floor = price_floor(hits,len(vals))
    roster = bool(row.get("inPredictedLineup") or row.get("startedLastGame"))
    recent = (row.get("hitRateL15") or 0)/100 > 1/p["odds"]
    # Replay unmodified production functions separately from the candidate.
    screen_pass = player_screen(p,rows) is not None
    literal_history = player_case(dict(p), row, evidence["data"])
    replay = screen_pass and literal_history
    candidate = roster and recent and p["odds"]>=floor
    against = f"favours the {'under' if p['direction']=='over' else 'over'}" in (row.get("matchup") or "").lower()
    if replay!=record["actual"]:
        reason = "replay differs from issued decision"
    elif not roster:
        reason = "starter screen"
    elif not recent:
        reason = "recent hit-rate screen"
    elif p["odds"]<floor:
        reason = "historical price floor"
    elif not literal_history:
        reason = "original history parser or source format"
    elif not row.get("matchup"):
        reason = "missing matchup"
    elif against:
        reason = "opponent veto only"
    else:
        reason = "passed"
    record.update(historyAt=evidence["at"], starts=len(vals), hits=hits, historySource=source,
                  floor=floor if math.isfinite(floor) else None, probability=(hits+0.5)/(len(vals)+1),
                  candidate=candidate, literalHistory=literal_history, replay=replay, reason=reason)
    return record


def calibration(pairs):
    if not pairs:
        return dict(n=0,brier=None,logLoss=None)
    n=len(pairs)
    bins=[]
    for i in range(5):
        group=[(p,y) for p,y in pairs if i/5<=p<(i+1)/5]
        if group:
            bins.append(dict(lower=i/5,n=len(group),forecast=sum(p for p,y in group)/len(group),
                             hit=sum(y for p,y in group)/len(group)))
    return dict(n=n,forecast=sum(p for p,y in pairs)/n,hit=sum(y for p,y in pairs)/n,
                brier=sum((p-y)**2 for p,y in pairs)/n,
                logLoss=-sum(math.log(p if y else 1-p) for p,y in pairs)/n,bins=bins)


def summarize(locks,outcomes):
    records=[r for lock in locks for r in lock["records"]]
    reasons=Counter(r["reason"] for r in records)
    roles=Counter()
    samples=defaultdict(list)
    net=defaultdict(list)
    portfolios={k:dict(selected=0,wins=0,losses=0,stake=0,profit=0.) for k in ("actual","candidate")}
    decisions=Counter()
    common=0
    kept_groups=defaultdict(lambda:dict(n=0,wins=0,profit=0.))
    for r in records:
        result=outcomes.get(r["id"]) or {}
        role=result.get("role")
        roles[role or "awaiting verified opening role"]+=1
        if role not in ROLES or r["probability"] is None or r.get("replay")!=r["actual"]:
            continue
        common+=1
        state=("kept" if r["actual"] and r["candidate"] else "removed" if r["actual"] else
               "added" if r["candidate"] else "neither")
        decisions[state]+=1
        for k,s in portfolios.items():
            s["selected"]+=int(r[k])
        obs=result.get("result")
        if not obs:
            continue
        hit=int(won(r,obs["tackles"],0))
        pair=(r["probability"],hit)
        for label in ("all","accepted" if r["actual"] else "rejected",r["reason"]):
            samples[label].append(pair)
        if obs["minutes"]<90:
            continue
        unit=r["odds"]-1 if hit else -1.
        for label in (state,"veto only" if r["reason"]=="opponent veto only" else "other causes"):
            g=kept_groups[label]
            g["n"]+=1
            g["wins"]+=hit
            g["profit"]+=unit
        for k,s in portfolios.items():
            if r[k]:
                s["wins"]+=hit
                s["losses"]+=1-hit
                s["stake"]+=1
                s["profit"]+=unit
        net[r["matchId"]].append(unit*(int(r["candidate"])-int(r["actual"])))
    for s in portfolios.values():
        s.update(pending=s["selected"]-s["stake"],roi=s["profit"]/s["stake"] if s["stake"] else None)
    all_diff=[x for group in net.values() for x in group]
    interval=None
    if len(net)>=20:
        rng=random.Random(20261118)
        clusters=[(sum(g),len(g)) for g in net.values()]
        samples_boot=[]
        for _ in range(2000):
            draw=rng.choices(clusters,k=len(clusters))
            samples_boot.append(sum(x for x,n in draw)/sum(n for x,n in draw))
        samples_boot.sort()
        interval=[samples_boot[49],samples_boot[1949]]
    return dict(morningDays=[l["day"] for l in locks],quoteContracts=len(records),
                pricedFixtures=len({r["matchId"] for r in records}),pricedNoBets=sum(not r["actual"] for r in records),
                missingIssued=sum(len(l["missingIssued"]) for l in locks),reasons=dict(reasons),roles=dict(roles),
                completeCommonCM=common,groups=dict(decisions),settledCommon=len(all_diff),settledFixtures=len(net),
                netIfPlayedByGroup=dict(kept_groups),
                calibration={k:calibration(samples[k]) for k in sorted({"all","accepted","rejected"}|samples.keys())},
                portfolios=portfolios,deltaPerSettledOpportunity=sum(all_diff)/len(all_diff) if all_diff else None,
                deltaFixtureInterval=interval)
