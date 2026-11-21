"""Paper returns from immutable pre-match scans. Independent of Telegram delivery."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math

from desk_games import FINAL_HOUR, pairs
from drop_desk_history import bind, event_data, outcome, rows, wta_result, wta_scoreboard
from pinnradar_tennis import Store, advance, utc
from price_drop_watch import MAX_GAP, START

BASE = "presentation/drop-paper-v1"
FIRST_DAY = "2026-11-20"
RULES = (("all4", 4, False), ("all45", 4.5, False),
         ("late4", 4, True), ("late45", 4.5, True))


def circuit(tour):
    return "WTA" if tour in ("WTA", "WTA 125") else "ATP"


def advance_paper(state, snapshot):
    stamp = snapshot["observed"]
    now = utc(stamp)
    previous = utc(state.get("observed"))
    if now < START or (previous and now <= previous):
        return []
    open_board, _ = advance({"observed": state.get("observed"), "guards": state.get("guards", {})},
                            snapshot, track_first=False)
    continuous = previous is not None and now - previous <= MAX_GAP
    prior = state.get("windows", {}) if continuous else {}
    windows = {}
    issued = {k: v for k, v in state.get("issued", {}).items() if utc(v) + timedelta(days=7) > now}
    found = []
    for event_id, row in open_board["events"].items():
        start = utc(row["start"])
        if now >= start:
            continue
        first, second = sorted((row["home"], row["away"]))
        for code, pair in pairs(row):
            prices = pair["prices"]
            if len(prices) != 2 or not all(math.isfinite(p) and p > 1 for p in prices):
                continue
            for side, price in enumerate(prices):
                ident = json.dumps([row["fixture"], code, side], ensure_ascii=True)
                key = json.dumps([event_id, row["start"], ident])
                old = prior.get(key, {})
                point = [stamp, price]
                new = {}
                for field, allowed in (("all", True), ("late", start - FINAL_HOUR <= now)):
                    if not allowed:
                        continue
                    peak = old.get(field)
                    new[field] = point if not peak or price >= peak[1] else peak
                    if not peak:
                        continue
                    rise = 100 * (1 / price - 1 / peak[1])
                    for rule, threshold, late in RULES:
                        if late != (field == "late") or rise < threshold - 1e-10:
                            continue
                        token = hashlib.sha256((rule + ident).encode()).hexdigest()
                        if token in issued:
                            continue
                        issued[token] = row["start"]
                        if stamp[:10] < FIRST_DAY:
                            continue
                        player, opponent = (second, first) if side and code != "winner" and pair["market"] != "totals" else (first, second)
                        if code == "winner":
                            player, opponent = pair["labels"][side], pair["labels"][1-side]
                        ticket = {k:row[k] for k in ("fixture", "league", "start", "tour")}
                        ticket.update(id=token, rule=rule, before=peak[0], old=peak[1], after=stamp,
                                      new=price, contract=code, market=pair["market"], side=side,
                                      player=player, opponent=opponent, selection=pair["labels"][side])
                        if "line" in pair:
                            ticket["line"] = -pair["line"] if side and pair["market"] == "spreads" else pair["line"]
                        found.append(ticket)
                windows[key] = new
    state.update(observed=stamp, guards=open_board["guards"], windows=windows, issued=issued)
    return found


def grade_due(tickets, now):
    by_group = defaultdict(list)
    for t in tickets:
        if "result" in t or utc(t["start"]) > now:
            continue
        previous = utc(t.get("checked"))
        interval = timedelta(hours=24 if now - utc(t["start"]) > timedelta(days=7) else 1)
        if previous and now - previous < interval:
            continue
        by_group[t["start"][:10], circuit(t["tour"])].append(t)
    for (day, tour), group in by_group.items():
        if tour == "WTA":
            events = wta_scoreboard(day)
        else:
            tours, schedule, games, names = event_data(group)
        for t in group:
            if tour == "WTA":
                matched = wta_result(t, events)
                grade = None
                if matched:
                    t["binding"], grade = matched
            else:
                t["binding"] = t.get("binding") or bind(t, tours, schedule, games, names)
                grade = outcome(t, games, schedule, now)
            t["checked"] = now.isoformat()
            if grade:
                result = grade["result"]
                profit = grade.get("profit", t["new"]-1 if result == "Won" else -1 if result == "Lost" else 0)
                t.update(result=result, score=grade["score"], profit=profit,
                         stake=grade.get("settled_stake", 0 if result == "Void" else 1))
    return bool(by_group)


def summary(tickets):
    fixtures = {t["fixture"] for t in tickets}
    count = defaultdict(int)
    for t in tickets:
        count[t.get("result", "Pending")] += 1
    stake = sum(t.get("stake", 0) for t in tickets)
    net = sum(t.get("profit", 0) for t in tickets)
    return dict(entries=len(tickets), fixtures=len(fixtures), won=count["Won"], lost=count["Lost"],
                halfWon=count["Half won"], halfLost=count["Half lost"], pushes=count["Push"],
                voids=count["Void"], pending=count["Pending"], stake=stake, net=round(net,4),
                roi=round(100*net/stake,2) if stake else None)


def publish_day(store, day, ledger):
    tickets = list(ledger["tickets"].values())
    report = {"day":day, "through":ledger["through"], "scans":ledger["scans"], "circuits":{}}
    for tour in ("ATP", "WTA"):
        group = [t for t in tickets if circuit(t["tour"]) == tour]
        report["circuits"][tour] = {"coveredScans":ledger["covered"].get(tour,0),
                                    "rules":{r:summary([t for t in group if t["rule"] == r]) for r,_,_ in RULES}}
    store.put(f"{BASE}/ledger/{day}.json", ledger, replace=True)
    store.put(f"{BASE}/summary/{day}.json", report, replace=True)


def project(store, now, limit=6):
    path = BASE + "/state.json"
    state = store.get(path) or {"day":START.date().isoformat(), "pending_days":[]}
    day = date.fromisoformat(state["day"])
    ledgers = {}
    def ledger_for(d):
        if d not in ledgers:
            ledgers[d] = store.get(f"{BASE}/ledger/{d}.json") or {"tickets":{}, "scans":0, "covered":{}, "through":""}
        return ledgers[d]
    used = 0
    dirty = set()
    while day <= now.date() and used < limit:
        prefix = "snapshots/" + day.strftime("%Y/%m/%d")
        names = [n for n in rows(store,prefix) if n > state.get("slot","")]
        for name in names[:limit-used]:
            snap = store.get(prefix+"/"+name)
            if not snap:
                raise ValueError("Saved scan missing")
            stamp = snap["observed"]
            detected_day = stamp[:10]
            tickets = advance_paper(state, snap)
            if detected_day >= FIRST_DAY:
                ledger = ledger_for(detected_day)
                if stamp > ledger["through"]:
                    ledger["through"] = stamp
                    ledger["scans"] += 1
                    for tour in {circuit(r["tour"]) for r in snap["events"].values()}:
                        ledger["covered"][tour] = ledger["covered"].get(tour,0) + 1
                for ticket in tickets:
                    ledger["tickets"].setdefault(ticket["id"], ticket)
                dirty.add(detected_day)
            used += 1
            state["slot"] = name
        if used >= limit or day == now.date():
            break
        day += timedelta(days=1)
        state.update(day=day.isoformat(), slot="")
    pending = set(state["pending_days"])
    for d in sorted(pending | dirty):
        ledger = ledger_for(d)
        changed = grade_due(ledger["tickets"].values(),now)
        if changed or d in dirty:
            publish_day(store,d,ledger)
        if any("result" not in t for t in ledger["tickets"].values()):
            pending.add(d)
        else:
            pending.discard(d)
    state["pending_days"] = sorted(pending)
    store.put(path,state,replace=True)
    return used


if __name__ == "__main__":
    print("Processed paper-return scan slots:", project(Store(), datetime.now(timezone.utc)))
