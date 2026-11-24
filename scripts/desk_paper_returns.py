"""Paper returns from immutable pre-match scans. Independent of Telegram delivery."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math

from desk_games import FINAL_HOUR, market_limit, meets_usd_floor, pairs
from drop_desk_history import bind, event_data, outcome, rows, wta_result, wta_scoreboard
from pinnradar_tennis import Store, advance, utc
from price_drop_watch import MAX_GAP, START

BASE = "presentation/drop-paper-v1"
FIRST_DAY = "2026-11-20"
RETIREMENT_RULE = "moneyline-first-completed-set-v1"
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
    # Immutable snapshots captured before the floor retain their original replay rules.
    minimum = snapshot.get("paper_minimum_usd")
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
            limit = market_limit(row, pair)
            eligible_limit = minimum is None or meets_usd_floor(limit, minimum)
            for side, price in enumerate(prices):
                ident = json.dumps([row["fixture"], code, side], ensure_ascii=True)
                key = json.dumps([event_id, row["start"], ident])
                old = prior.get(key, {})
                point = [stamp, price]
                # Keep observing low-limit prices as references, without consuming the entry.
                new = {"last_price": price}
                for field, allowed in (("all", True), ("late", start - FINAL_HOUR <= now)):
                    if not allowed:
                        continue
                    peak = old.get(field)
                    new[field] = point if not peak or price >= peak[1] else peak
                    if not peak or not eligible_limit:
                        continue
                    if minimum is not None:
                        last_price = old.get("last_price")
                        if last_price is None and peak[0] == state.get("observed"):
                            last_price = peak[1]
                        if last_price is None or price >= last_price:
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
                        if minimum is not None:
                            ticket["paper_minimum_usd"] = minimum
                            ticket["reported_market_max_at_detection"] = limit
                        elif "reported_market_max" in pair:
                            ticket["reported_market_max_at_detection"] = pair["reported_market_max"]
                        found.append(ticket)
                windows[key] = new
    state.update(observed=stamp, guards=open_board["guards"], windows=windows, issued=issued)
    return found


def save_grade(ticket, grade):
    result = grade["result"]
    unit_profit = ticket["new"]-1 if result == "Won" else -1 if result == "Lost" else 0
    ticket.update(result=result, score=grade["score"], profit=grade.get("profit", unit_profit),
                  stake=grade.get("settled_stake", 0 if result == "Void" else 1))
    if grade.get("draw_sha256"):
        ticket["draw_sha256"] = grade["draw_sha256"]


def apply_retirement_review(ledger, review, now):
    """Regrade reviewed moneylines at their original odds inside the single scheduled writer."""
    for item in review:
        ticket = ledger["tickets"][item["id"]]
        if (ticket["market"] != "winner" or ticket.get("binding") != item["binding"]
                or ticket["new"] != item["odds"] or ticket["after"] != item["detected"]):
            raise ValueError("Historical retirement review does not match the captured selection")
        grade = outcome(ticket, [item["official_result"]], [], now)
        if grade is None or grade["result"] not in ("Won","Lost"):
            raise ValueError("Retirement needs a verified official winner and completed first set")
        if ticket.get("result") not in (None,"Void",grade["result"]):
            raise ValueError("Retirement review conflicts with an existing W/L")
        save_grade(ticket,grade)
        ticket.update(settlement_rule=RETIREMENT_RULE,verification_sha256=item["evidence_sha256"])


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
                save_grade(t, grade)
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
    return report


def performance_report(days):
    """Aggregate the independent paper controls from daily counts and settled units."""
    report = {"firstDay":FIRST_DAY, "through":max((r["through"] for r in days.values()), default=""), "circuits":{}}
    fields = ("entries","won","lost","halfWon","halfLost","pushes","voids","pending","stake","net")
    for circuit_name in ("ATP", "WTA"):
        def blank():
            return {rule:{**dict.fromkeys(fields,0), "roi":None} for rule in ("all4","late4")}
        life, months = blank(), {}
        first_day = None
        for day, record in sorted(days.items()):
            data = record["circuits"][circuit_name]
            if not data["coveredScans"]:
                continue
            if first_day is None:
                first_day = day
            month = day[:7]
            if month not in months:
                months[month] = blank()
            for totals in (life,months[month]):
                for rule, result in totals.items():
                    for field in fields:
                        result[field] += data["rules"][rule][field]
        for period in [life,*months.values()]:
            for result in period.values():
                result["net"] = round(result["net"],4)
                result["roi"] = round(100*result["net"]/result["stake"],2) if result["stake"] else None
        report["circuits"][circuit_name] = {"firstDay":first_day, "lifetime":life, "months":months}
    return report


def selection_key(ticket):
    return json.dumps([ticket["tour"], ticket["fixture"], ticket["contract"], ticket["side"],
                       ticket["selection"]], ensure_ascii=True, separators=(",", ":"))


def confirmed_moves(receipt, batch):
    """Only an acknowledged message can supply an alert price. Never infer delivery from eligibility."""
    if receipt["state"] != "sent":
        return []
    if (receipt["observed"] != batch["observed"] or type(receipt["message_id"]) is not int
            or not utc(receipt["delivered_at"])):
        raise ValueError("Delivery receipt does not match its scan")
    wanted = set(receipt["move_ids"])
    found = [m for m in batch["moves"] if m["move_id"] in wanted]
    if len(found) != len(wanted) or {m["move_id"] for m in found} != wanted:
        raise ValueError("Incomplete delivery evidence")
    confirmed = []
    for m in found:
        if not (utc(m["before"]) < utc(m["after"]) < utc(m["start"])) or min(m["new"],m["old"]) <= 1:
            raise ValueError("Invalid delivered odds or timing")
        if 100 * (1/m["new"] - 1/m["old"]) < 4 - 1e-10:
            continue
        if "contract" not in m:  # Original winner-only format.
            side = sorted((m["player"],m["opponent"])).index(m["player"])
            m = dict(m, contract="winner", side=side, selection=m["player"])
        selection = {k:m[k] for k in ("fixture","contract","side","tour","selection","player","opponent","league",
                                      "new","after","start","move_id") if k in m}
        selection.update(sent=receipt["delivered_at"], message=receipt["message_id"])
        confirmed.append(selection)
    return confirmed


def update_receipts(store, day, saved):
    import re
    from pinnradar_tennis import BUCKET
    folder = day.replace("-", "/")
    prefix = "drop-deliveries-v2/" + folder
    reply = store.request("POST", "/object/list/" + BUCKET, json={
        "prefix":prefix+"/", "limit":200, "sortBy":{"column":"name","order":"asc"}})
    store.require(reply)
    files = reply.json()
    if len(files) >= 200:
        raise ValueError("Incomplete receipt listing")
    for row in files:
        name = row["name"]
        if name in saved or not re.fullmatch(r"\d{6}-\d{6}\.json", name):
            continue
        receipt = store.get(prefix+"/"+name)
        if not receipt:
            raise ValueError("Missing listed receipt")
        if receipt["state"] == "sent":
            batch = store.get("drop-scans-v2/"+folder+"/"+name)
            saved[name] = confirmed_moves(receipt,batch)


def compact_ticket(t):
    return {k:t[k] for k in ("fixture","contract","side","tour","selection","player","opponent","league",
                              "new","after","result","stake","profit","settlement_rule") if k in t}


def alert_grade(t, odds):
    result = t.get("result", "Pending")
    if result not in ("Pending","Void","Push","Won","Lost","Half won","Half lost"):
        raise ValueError("Unrecognised paper settlement")
    if result == "Won":
        return odds - 1
    if result == "Half won":
        return (odds - 1)/2
    return {"Lost":-1,"Half lost":-.5}.get(result,0)


def rolling_report(days, end, through):
    start = (date.fromisoformat(end)-timedelta(days=29)).isoformat()
    confirmed, tickets, outcomes = {}, {}, {}
    for day, data in sorted(days.items()):
        outcomes.update(data.get("outcomes", {}))
        for batch in data["receipts"].values():
            for sent in batch:
                key = selection_key(sent)
                if key not in confirmed or utc(sent["sent"]) < utc(confirmed[key]["sent"]):
                    confirmed[key] = sent
        for t in data["tickets"]:
            key = selection_key(t)
            if key in tickets:
                raise ValueError("Duplicate rolling paper contract")
            tickets[key] = t
    def row(t, at, odds, sent):
        return {"selection":t["selection"],"fixture":t["player"]+" vs "+t["opponent"],
                "league":t["league"],"at":at,"odds":odds,"result":t.get("result","Pending"),"sent":sent}
    reports = {}
    for tour in ("ATP","WTA"):
        paper, alerts, paper_rows, alert_rows = [], [], [], []
        for key,t in tickets.items():
            if circuit(t["tour"]) == tour and start <= t["after"][:10] <= end:
                paper.append(t)
                paper_rows.append(row(t,t["after"],t["new"],key in confirmed))
        for key, sent in confirmed.items():
            if circuit(sent["tour"]) != tour or not start <= sent["sent"][:10] <= end:
                continue
            verified = outcomes.get(sent["move_id"])
            paired = tickets.get(key,{})
            result = paired.get("result")
            if verified:
                if verified["message_id"] != sent["message"] or verified["alerted_price"] != sent["new"]:
                    raise ValueError("Settlement does not match delivered odds and receipt")
                if result and result != verified["result"] and paired.get("settlement_rule") != RETIREMENT_RULE:
                    result = None  # A conflict stays visible as pending until resolved.
                else:
                    result = result or verified["result"]
            t = dict(sent,result=result or "Pending")
            t.update(profit=alert_grade(t,sent["new"]), stake=0 if t["result"] in ("Void","Pending") else 1)
            alerts.append(t)
            alert_rows.append(row(t,sent["sent"],sent["new"],True))
        covered = sorted(d for d,v in days.items() if start <= d <= end and v["coverage"].get(tour,0))
        reports[tour] = {"version":2,"tour":tour,"start":start,"end":end,"through":through,
                         "firstCovered":next(iter(covered),None),"coveredDays":len(covered),
                         "all":summary(paper),"telegram":summary(alerts),
                         "rows":sorted(paper_rows,key=lambda r:r["at"],reverse=True),
                         "sentRows":sorted(alert_rows,key=lambda r:r["at"],reverse=True)}
    return reports


def publish_rolling(store, daily, loaded, dirty, now):
    """A private, rebuildable projection; the site reads one summary/row packet per tour."""
    through = max(r["through"] for r in daily.values())
    end = now.date()
    # Include an overlap for exact contracts first sent just before the date boundary.
    # It also retains any matching paper settlement for these early deliveries.
    first = max(START.date(), end-timedelta(days=36))
    cache_path = BASE+"/rolling-cache-v2.json"
    old = store.get(cache_path) or {}
    days = {}
    for offset in range((end-first).days+1):
        day = (first+timedelta(days=offset)).isoformat()
        day_report = daily.get(day)
        data = old.get(day, {"receipts":{}, "tickets":[], "coverage":{}})
        revision = hashlib.sha256(json.dumps(day_report,sort_keys=True).encode()).hexdigest()
        if day_report and (day in dirty or data.get("revision") != revision):
            ledger = loaded.get(day) or store.get(f"{BASE}/ledger/{day}.json")
            if not ledger or ledger["through"] != day_report["through"]:
                raise ValueError("Rolling view missing its verified daily ledger")
            data.update(revision=revision, coverage=ledger["covered"],
                        tickets=[compact_ticket(t) for t in ledger["tickets"].values() if t["rule"]=="all4"])
        # Retry across midnight, backfill after downtime, and periodically reconcile older receipts.
        if (data.get("checked","") <= day or day >= (end-timedelta(days=1)).isoformat()
                or (date.fromisoformat(day).toordinal()%30 == (now.hour*4 + now.minute//15)%30)):
            update_receipts(store,day,data["receipts"])
            data["checked"] = end.isoformat()
        if data["receipts"]:
            # Match by the delivered move ID, including selections absent from the paper ledger.
            # Re-read pending results and periodically pick up verified corrections.
            ids = {m["move_id"] for batch in data["receipts"].values() for m in batch}
            settled = data.get("outcomes",{})
            if ids - settled.keys() or data.get("gradedDay") != end.isoformat():
                outcomes = store.get("presentation/outcomes/"+day+".json") or {}
                data["outcomes"] = {mid:{k:outcomes[mid][k] for k in ("result","message_id","alerted_price")}
                                    for mid in ids & outcomes.keys()}
                data["gradedDay"] = end.isoformat()
        days[day] = data
    for tour, report in rolling_report(days,end.isoformat(),through).items():
        store.put(f"{BASE}/rolling-30-v2/{tour.lower()}.json",report,replace=True)
    store.put(cache_path,days,replace=True)




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
    if state.get("retirement_rule") != RETIREMENT_RULE:
        review = store.get(f"{BASE}/reviews/{RETIREMENT_RULE}.json")
        if review and review.get("rule") == RETIREMENT_RULE:
            for reviewed_day, items in review["days"].items():
                apply_retirement_review(ledger_for(reviewed_day), items, now)
                dirty.add(reviewed_day)
            state["retirement_rule"] = RETIREMENT_RULE
    # Seed once from the existing public-summary projections, including fully settled dates.
    fresh_performance = "performance_days" not in state
    daily = state.setdefault("performance_days", {})
    if fresh_performance:
        older = date.fromisoformat(FIRST_DAY)
        while older <= min(day,now.date()):
            key = older.isoformat()
            if key not in dirty:
                existing = store.get(f"{BASE}/summary/{key}.json")
                if existing:
                    daily[key] = existing
            older += timedelta(days=1)
    pending = set(state["pending_days"])
    for d in sorted(pending | dirty):
        ledger = ledger_for(d)
        changed = grade_due(ledger["tickets"].values(),now)
        if changed or d in dirty:
            daily[d] = publish_day(store,d,ledger)
            dirty.add(d)
            fresh_performance = True
        if any("result" not in t for t in ledger["tickets"].values()):
            pending.add(d)
        else:
            pending.discard(d)
    if fresh_performance and daily:
        store.put(f"{BASE}/performance.json", performance_report(daily), replace=True)
    state["pending_days"] = sorted(pending)
    store.put(path,state,replace=True)
    if daily:
        publish_rolling(store, daily, ledgers, dirty, now)
    return used


if __name__ == "__main__":
    print("Processed paper-return scan slots:", project(Store(), datetime.now(timezone.utc)))
