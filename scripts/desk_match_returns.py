"""One paper unit per match, with independent all-drop and confirmed-alert records."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import copy
import os
import time
from uuid import uuid4
import requests

from desk_closing import CLOSE, display, display_key
from desk_games import match_rank
from desk_paper_returns import BASE, RETIREMENT_RULE, alert_grade, circuit, selection_key, summary
from pinnradar_tennis import Store, utc
from price_drop_watch import START

ROOT = BASE + "/first-match-v1"
GROUPS = ("all", "telegram")
REGISTERED = "2026-11-22T21:54:53.063875+00:00"


class ReportingStore(Store):
    """Use the successful writes from this scan when building its downstream reports."""
    def __init__(self):
        super().__init__()
        self.revision = uuid4().hex
        self.writes = {}

    def request(self,verb,path,headers=None,**kwargs):
        # Repeating a replace writes the identical report under the scheduled single writer.
        safe = verb=="GET" or (verb=="POST" and (path.startswith("/object/list/")
               or (path.startswith("/object/") and (headers or {}).get("x-upsert")=="true")))
        attempts = 3 if safe else 1
        for attempt in range(attempts):
            try:
                reply = super().request(verb,path,headers=headers,**kwargs)
                if reply.status_code not in (408,429,500,502,503,504,520,521,522,523,524) or attempt+1==attempts:
                    return reply
                reply.close()
            except (requests.Timeout,requests.ConnectionError):
                if attempt+1==attempts:
                    raise
            time.sleep(2**attempt)

    def get(self,path):
        if path in self.writes:
            return copy.deepcopy(self.writes[path])
        if path.startswith("presentation/"):
            return super().get(path+"?revision="+self.revision)
        return super().get(path)

    def put(self,path,data,replace=False):
        ok = super().put(path,data,replace)
        if ok and replace and (path.startswith((BASE+"/ledger/","presentation/outcomes/",CLOSE))
                or path in (BASE+"/rolling-cache-v2.json",BASE+"/rolling-30-v2/atp.json")):
            self.writes[path] = copy.deepcopy(data)
        return ok


def settlement_health(locks, now):
    fixtures = {}
    for group in GROUPS:
        for key,item in locks[group].items():
            if item.get("result")!="Pending" or now - utc(item["start"]) < timedelta(hours=24):
                continue
            row = fixtures.setdefault(key, {"tour":circuit(item["tour"]), "start":item["start"],
                "players":[item["player"],item["opponent"]], "event":item["league"], "groups":[]})
            row["groups"].append(group)
    return {"checked":now.isoformat(),"overdue":sorted(fixtures.values(),key=lambda t:t["start"])}


def first_scan(candidates, hydrate):
    first = min(utc(c["after"]) for c in candidates)
    simultaneous = [hydrate(c) for c in candidates if utc(c["after"]) == first]
    # The canonical market/line string and side are fixed before observing results.
    return min(simultaneous, key=match_rank)


def settle(chosen, paper, verified):
    result = paper.get("result")
    if verified:
        if verified["message_id"] != chosen["message"] or verified["alerted_price"] != chosen["new"]:
            raise ValueError("Delivered selection and settlement disagree")
        if result and result != verified["result"] and paper.get("settlement_rule") != RETIREMENT_RULE:
            result = "Pending"
        else:
            result = result or verified["result"]
    # A cache miss on retry cannot reopen a settled first-scan selection.
    if not verified and not result:
        result = chosen.get("result")
    result = result or "Pending"
    return dict(chosen, result=result, profit=alert_grade({"result":result}, chosen["new"]),
                stake=int(result not in ("Void", "Pending")))


def build(store, now, write=False):
    days = store.get(BASE+"/rolling-cache-v2.json")
    previous = store.get(ROOT+"/state.json")
    if not days or min(days) > (previous["through"][:10] if previous else START.date().isoformat()):
        raise ValueError("First-scan history is incomplete; rebuild from saved days")
    through = (store.get(BASE+"/rolling-30-v2/atp.json") or {})["through"]
    if not utc(through) or utc(through)>now:
        raise ValueError("Invalid source observation time")
    if previous and utc(previous["through"]) > utc(through):
        raise ValueError("Source projection is older than match record")
    end = utc(through).date()
    locks = previous["locks"] if previous else {g:{} for g in GROUPS}
    coverage = previous["coverage"] if previous else {}
    candidates = {g:defaultdict(list) for g in GROUPS}
    paper, outcomes, delivered = {}, {}, set()
    for day, data in sorted(days.items()):
        coverage[day] = data["coverage"]
        outcomes.update(data.get("outcomes", {}))
        for t in data["tickets"]:
            paper[selection_key(t)] = t
            candidates["all"][t["fixture"]].append(t)
        for name, batch in data["receipts"].items():
            for t in batch:
                delivered.add(selection_key(t))
                candidates["telegram"][t["fixture"]].append(dict(t, batch_day=day, batch_name=name))

    @lru_cache(maxsize=6)
    def ledger(day):
        raw = store.get(f"{BASE}/ledger/{day}.json") or {}
        return {selection_key(t):t for t in raw.get("tickets",{}).values() if t["rule"]=="all4"}

    @lru_cache(maxsize=8)
    def moves(day, name):
        raw = store.get("drop-scans-v2/"+day.replace("-","/")+"/"+name)
        return {t["move_id"]:t for t in raw["moves"]}

    def hydrate(t):
        if "old" in t and "before" in t and "start" in t:
            return t
        if "move_id" in t:
            raw = moves(t["batch_day"],t["batch_name"])[t["move_id"]]
        else:
            raw = ledger(t["after"][:10])[selection_key(t)]
        for field in ("fixture","after","new"):
            if t[field] != raw[field]:
                raise ValueError("Archived candidate identity or odds disagree")
        return dict(t, **{k:raw[k] for k in ("old","before","start")})

    for group in GROUPS:
        for fixture, items in candidates[group].items():
            lock = locks[group].get(fixture)
            earliest = min(utc(t["after"]) for t in items)
            if lock and utc(lock["after"]) < earliest:
                continue
            # Cache the identity of every first-scan candidate. Later scans cannot replace a lock.
            initial = [t for t in items if utc(t["after"])==earliest]
            signature = sorted([t["contract"],t["side"],t["new"],t.get("move_id","")] for t in initial)
            if lock and utc(lock["after"])==earliest and lock["candidates"]==signature:
                continue
            winner = first_scan(initial,hydrate)
            if lock and (lock["after"],selection_key(lock),lock["new"]) != (winner["after"],selection_key(winner),winner["new"]):
                raise ValueError("Late evidence conflicts with an already frozen match entry")
            locks[group][fixture] = dict(winner,candidates=signature)

    @lru_cache(maxsize=8)
    def old_outcomes(day):
        return store.get("presentation/outcomes/"+day+".json") or {}

    for group in GROUPS:
        for fixture, t in locks[group].items():
            key = selection_key(t)
            paired = paper.get(key)
            verified = outcomes.get(t.get("move_id"))
            stamp = t["after"][:10]
            if stamp < min(days):
                if t.get("result") not in (None,"Pending"):
                    continue
                paired = ledger(stamp).get(key)
                if group=="telegram":
                    verified = old_outcomes(t["batch_day"]).get(t["move_id"])
            t["was_sent"] = t.get("was_sent",False) or key in delivered
            locks[group][fixture] = settle(t, paired or {}, verified)

    reports = {}
    start = end - timedelta(days=29)
    for tour in ("ATP","WTA"):
        closes = store.get(CLOSE+tour.lower()+".json")
        closing = {display_key(r):r["close"] for r in closes["rows"]} if closes else {}
        active = {g:[t for t in locks[g].values() if circuit(t["tour"])==tour] for g in GROUPS}

        def score(items, group):
            result = summary(items)
            changes = [closing.get(display_key(display(t,group)),{}).get("change") for t in items]
            measured = [c for c in changes if c is not None]
            result["clv"] = (dict(measured=len(measured),mean=sum(measured)/len(measured) if measured else None)
                             if closes else None)
            return result

        def period(items):
            return {"all4":score(items,"all"),"late4":score([t for t in items if
                utc(t["before"]) >= utc(t["start"])-timedelta(hours=1)],"all")}

        observed = sorted(d for d,v in coverage.items() if v.get(tour) and d<=end.isoformat())
        by_day, by_month = defaultdict(list), defaultdict(list)
        for t in active["all"]:
            d = utc(t["after"]).date().isoformat()
            by_day[d].append(t)
            by_month[d[:7]].append(t)
        report = {"version":1,"tour":tour,"start":start.isoformat(),"end":end.isoformat(),"through":through,
                  "firstCovered":next((d for d in observed if d>=start.isoformat()),None),
                  "coveredDays":sum(d>=start.isoformat() for d in observed),
                  "firstDay":next(iter(observed),None), "lifetime":period(active["all"]),
                  "months":{m:period(by_month[m]) for m in sorted({d[:7] for d in observed})},
                  "days":{d:period(by_day[d]) for d in observed}}
        for group, row_field in (("all","rows"),("telegram","sentRows")):
            items = [t for t in active[group] if start<=utc(t.get("sent",t["after"])).date()<=end]
            report[group] = score(items,group)
            report[row_field] = sorted((dict(display(t,group),result=t["result"],sent=t["was_sent"],
                                              reconstructed=utc(t["after"])<utc(REGISTERED))
                                        for t in items), key=lambda r:r["at"],reverse=True)
        reports[tour] = report
    if write:
        for tour, report in reports.items():
            store.put(ROOT+"/"+tour.lower()+".json",report,replace=True)
        store.put(ROOT+"/state.json",dict(through=through,locks=locks,coverage=coverage),replace=True)
        health = settlement_health(locks,now)
        store.put(ROOT+"/settlement-health.json",health,replace=True)
        message = f"{len(health['overdue'])} unique fixtures still need a result at least 24h after their scheduled start."
        print(message)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as summary_file:
                print("### Drop Shot Desk settlement health\n"+message,file=summary_file)
                for row in health["overdue"]:
                    print(f"- {row['tour']} · {row['start']} · {' / '.join(row['groups'])}",file=summary_file)
    return reports


if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-all",action="store_true")
    args = parser.parse_args()
    store,now = ReportingStore(),datetime.now(timezone.utc)
    if args.refresh_all:
        import drop_desk_history, desk_paper_returns, desk_closing
        drop_desk_history.project(store,now)
        desk_paper_returns.project(store,now)
        desk_closing.run(store,now)
    for tour, result in build(store,now,write=True).items():
        print(tour, result["all"]["entries"], "paper matches;", result["telegram"]["entries"], "confirmed")
