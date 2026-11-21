"""Project last observed pre-play odds from exact receipts, verified clocks and schedule-revision tapes."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from math import isfinite

from desk_paper_returns import BASE, circuit, selection_key
from drop_desk_history import normal
from pinnradar_tennis import Store, utc
from desk_start_clocks import refresh_clocks

CLOSE = "presentation/drop-paper-clv-v1/"
PRIVATE = "research/desk-start-clocks-v1/"


def display_key(row):
    return tuple(row[k] for k in ("group", "fixture", "league", "selection", "at", "odds"))


def display(ticket, group):
    return dict(group=group, fixture=ticket["player"]+" vs "+ticket["opponent"], league=ticket["league"],
                selection=ticket["selection"], at=ticket["sent"] if group=="telegram" else ticket["after"],
                odds=ticket["new"])


def closing(ticket, entry, clock, tape):
    after, start = utc(ticket["after"]), utc(clock["start_report"])
    lower = min(start, utc(clock.get("scoreboard_listed_minute",clock["start_report"])))
    upper = start + timedelta(seconds=clock.get("precision_seconds",0))
    if (not after <= entry < lower or not 0 <= (start-after).total_seconds() <= 7*86400
            or ticket["league"] != clock["league"]
            or sorted(map(normal, clock["players"])) != sorted(map(normal,(ticket["player"],ticket["opponent"])))):
        return None
    first,second=sorted((ticket["player"],ticket["opponent"]))
    code=ticket["contract"]
    if code=="winner":
        labels=[first,second]
    else:
        market,value=code.split(":")
        line=float(value)
        if market=="spreads":
            labels=[f"{first} {line:+g} games",f"{second} {-line:+g} games"]
        elif market=="totals":
            labels=[f"Over {line:g} games",f"Under {line:g} games"]
        else:return None
    if labels[ticket["side"]]!=ticket["selection"]:return None
    ticks, events, observations = {}, set(), set()
    day = after.date()
    while day <= (upper+timedelta(minutes=30)).date():
        data = tape(day.isoformat())
        observations.update(utc(t) for t in data.get("slots",{}).values())
        for key, series in data.get("series",{}).items():
            fields = key.split("|")
            if len(fields) not in (3,4) or fields[1] != ticket["fixture"]:
                continue
            if (fields[3] if len(fields)==4 else "winner") != ticket["contract"]:
                continue
            if sorted(series["players"])!=sorted(labels):
                continue
            side=series["players"].index(ticket["selection"])
            for tick in series["quotes"]:
                at, odds = utc(tick[0]), tick[1+side]
                if not after <= at < upper or not isinstance(odds,(int,float)) or not isfinite(odds) or odds<=1:
                    continue
                if at >= lower or (at in ticks and ticks[at] != odds):
                    return None
                ticks[at] = odds
                events.add(fields[0])
        day += timedelta(days=1)
    if len(events)!=1 or ticks.get(after)!=ticket["new"] or not observations or max(observations)<upper:
        return None
    # A missing quarter-hour around the start can conceal a later observation.
    through=min(t for t in observations if t>=upper)
    slots=sorted({int(t.timestamp())//900 for t in observations if after<=t<=through})
    if not slots or slots[-1]-slots[0]+1 != len(slots):
        return None
    last=max(ticks)
    return dict(odds=ticks[last],observed=last.isoformat(),start=start.isoformat(),
                minutes=round((start-last).total_seconds()/60,1),
                change=round(100*(ticket["new"]/ticks[last]-1),6) if last>entry else None)


def run(store, now, write=True):
    days=store.get(BASE+"/rolling-cache-v2.json")
    if not days: raise ValueError("Missing rolling receipt cache")
    issued={"all":{}, "telegram":{}}
    for data in days.values():
        for ticket in data["tickets"]:
            issued["all"][selection_key(ticket)] = ticket
        for batch in data["receipts"].values():
            for ticket in batch:
                k=selection_key(ticket)
                prior=issued["telegram"].get(k)
                if not prior or utc(ticket["sent"])<utc(prior["sent"]):
                    issued["telegram"][k]=ticket
    config=store.get(PRIVATE+"reference.json")
    if not config: raise ValueError("Missing verified timing configuration")
    saved=store.get(PRIVATE+"discovered.json") or {"clocks":{},"checked":{}}
    import copy
    before=copy.deepcopy(saved)
    seed=config["clocks"]
    refresh_clocks(issued["telegram"].values(), config, saved, now)
    if write and before!=saved: store.put(PRIVATE+"discovered.json",saved,replace=True)
    clocks={**saved["clocks"],**seed}
    @lru_cache(maxsize=8)
    def tape(day):
        return store.get("presentation/desk-tapes/"+day+".json") or {}
    results={}
    for tour in ("ATP","WTA"):
        name=CLOSE+tour.lower()+".json"
        prev=store.get(name)
        if prev is None or prev.get("version")!=1 or prev.get("tour")!=tour:
            raise ValueError("Missing or invalid previous close record")
        output={display_key(r):r for r in prev["rows"]}
        for group,tickets in issued.items():
            for ticket in tickets.values():
                clock=clocks.get(ticket["fixture"])
                if not clock or circuit(ticket["tour"])!=tour:continue
                row=display(ticket,group)
                key=display_key(row)
                if key in output:continue
                close=closing(ticket,utc(row["at"]),clock,tape)
                if close: output[key]={**row,"close":close}
        if write and len(output)>len(prev["rows"]):
            store.put(name,{**prev,"rows":[output[k] for k in sorted(output)]},replace=True)
        active=[output.get(display_key(display(t,"telegram"))) for t in issued["telegram"].values()
                if circuit(t["tour"])==tour and 0<=(now.date()-utc(t["sent"]).date()).days<30]
        measured=[r["close"]["change"] for r in active if r and r["close"]["change"] is not None]
        results[tour]=(len(measured),len(active),round(sum(measured)/len(measured),4) if measured else None)
    return results

if __name__=="__main__":
    print(run(Store(),datetime.now(timezone.utc)))
