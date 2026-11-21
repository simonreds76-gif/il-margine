"""Compare exact whole-match games selections, using private, immutable Desk scans and delivery receipts."""
import os
import tempfile
import json
import re
from statistics import median
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "desk-reference-pilot"
from desk_paper_returns import BASE, update_receipts


def stamp(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def is_qual(league):
    return "challenger" in league.lower() and bool(re.search(r"\b(?:qual(?:ifier|ifying|ification|ifications|ifiers|ies|s)?|q[r]?[1-3]|q(?=\s*[-.]))\b", league, re.I))


def decimal(a):
    return 1 + (a / 100 if a >= 100 else -100 / a)


def get_snaps(store, start, end):
    day = (start - timedelta(minutes=20)).date()
    result = []
    while day <= end.date():
        tape = store.get("presentation/desk-tapes/" + day.isoformat() + ".json") or {}
        for name, observed in sorted(tape.get("slots", {}).items()):
            if not start - timedelta(minutes=20) <= stamp(observed) <= end:
                continue
            path = ROOT / "desk" / day.isoformat() / name
            if path.exists():
                snap = json.loads(path.read_bytes())
            else:
                snap = store.get("snapshots/" + day.strftime("%Y/%m/%d") + "/" + name)
                if not snap or snap.get("observed") != observed:
                    continue
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_text(json.dumps(snap, separators=(",", ":")), encoding="utf-8")
            if snap["observed"] == observed:
                result.append(snap)
        day += timedelta(days=1)
    return sorted(result, key=lambda s: s["observed"])


def active_receipts(store, fixtures, first, end):
    cache = store.get(BASE + "/rolling-cache-v2.json") or {}
    day = first.date() - timedelta(days=1)
    while day <= end.date():
        saved = cache.setdefault(day.isoformat(), {}).setdefault("receipts", {})
        update_receipts(store, day.isoformat(), saved)
        day += timedelta(days=1)
    unique = {}
    for day in cache.values():
        for group in day.get("receipts", {}).values():
            for m in group:
                if m["contract"] == "winner" or m["fixture"] not in fixtures or stamp(m["sent"]) > end:
                    continue
                key = m["fixture"], m["contract"], m["side"]
                if key not in unique or stamp(m["sent"]) < stamp(unique[key]["sent"]):
                    unique[key] = m
    return unique


def issued_identity(store, t, scans):
    """Verify original selection and decimal price against the immutable scan that generated the receipt."""
    when = stamp(t["after"])
    day = when.date().isoformat()
    tape = store.get("presentation/desk-tapes/" + day + ".json") or {}
    names = [name for name, dt in tape.get("slots", {}).items() if stamp(dt) == when]
    if len(names) != 1:
        return None
    file = ROOT / "desk" / day / names[0]
    if file.is_file():
        snap = json.loads(file.read_bytes())
    else:
        snap = store.get("snapshots/" + day.replace("-","/") + "/" + names[0])
        if snap is None:
            return None
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(snap,separators=(",",":")),encoding="utf-8")
    rows = [r for r in snap["events"].values() if r["fixture"] == t["fixture"]]
    if len(rows) != 1 or stamp(snap["observed"]) != when:
        return None
    row = rows[0]
    pair = row.get("contracts",{}).get(t["contract"])
    if (not pair or pair["prices"][t["side"]] != t["new"] or pair["labels"][t["side"]] != t["selection"]
            or row["league"] != t["league"] or row["tour"] != t["tour"]
            or {row["home"],row["away"]} != {t["player"],t["opponent"]} or stamp(row["start"]) <= when):
        return None
    latest = [r for s in scans for r in s["events"].values() if r["fixture"] == t["fixture"]]
    if not latest or any(str(r["id"]) != str(row["id"]) or r["tour"] != row["tour"] or r["league"] != row["league"]
                         or {r["home"],r["away"]} != {row["home"],row["away"]} for r in latest):
        return None
    return {"event_id": row["id"], "issued_scan":snap["observed"], "issued_start":row["start"], "latest_start":latest[-1]["start"]}


def pair_prices(m, aligned):
    market = m.get("type")
    if market not in ("total", "spread") or m.get("period") != 0:
        return
    parts = str(m.get("key", "")).split(";")
    if len(parts) != 4 or parts[:3] != ["s", "0", "s" if market == "spread" else "ou"]:
        return
    line = float(parts[-1])
    first_home = aligned["home"] == min(aligned.values())
    order = ("over", "under") if market == "total" else (("home", "away") if first_home else ("away", "home"))
    canonical = line if market == "total" or first_home else -line
    pair = (("totals" if market == "total" else "spreads") + ":" + format(canonical or 0, "g"))
    odds = {p["designation"]: p for p in m.get("prices", []) if "designation" in p}
    legs = []
    for side in order:
        p = odds.get(side, {})
        expected = -line if side == "away" else line
        value = p.get("price")
        if (m.get("status") != "open" or p.get("points") != expected or not isinstance(value, (int, float))
                or abs(value) < 100):
            legs.append(None)
        else:
            legs.append(value)
    return pair, legs


def rate(before, after):
    return round(100 * (1 / after - 1 / before), 4)


def compare(path, *, store, until=None):
    frames = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.endswith("\n"):
                frames.append(json.loads(line))
    if not frames:
        raise ValueError("Empty capture")
    first = stamp(frames[0]["received"])
    last = stamp(frames[-1]["received"])
    end = min(stamp(until),last) if until else last
    scans = get_snaps(store, first, end)
    events = {}
    for snap in scans:
        for row in snap["events"].values():
            events[str(row["id"])] = row
    fixtures = {e["fixture"] for e in events.values()}
    alerts = active_receipts(store, fixtures, first, end)
    paths = defaultdict(list)
    meta, versions, by_child = {}, {}, {}
    matched = set()
    qualifiers = set()
    provider_qualifiers = set()
    gaps = []
    arrival_lags = []
    snapshot_end = None

    def add(key, dt, source_at, value, typ):
        if not paths[key] or paths[key][-1][2] != value:
            paths[key].append((dt, source_at, value, typ))

    for item in frames:
        dt, frame = stamp(item["received"]), item["frame"]
        if dt > end:
            break
        typ = frame["type"]
        if typ == "missed" or typ == "error" or typ == "feed" and frame.get("state", frame.get("status")) != "up":
            gaps.append({"utc": dt.isoformat(), "type": typ})
            break
        data = frame.get("data", {})
        if typ == "odds" and (data.get("sport_id") != 2 or not data.get("topic","").endswith("/pre")):
            continue
        if typ == "snapshot" and frame.get("final"):
            snapshot_end = dt
        source_at = datetime.fromtimestamp(data["ts"] / 1000, timezone.utc) if data.get("ts") else None
        if source_at:
            arrival_lags.append((dt-source_at).total_seconds())
        for rec in frame.get("events", []) if typ == "snapshot" else ([data["rec"]] if typ == "odds" and data.get("rec") else []):
            child = str(rec["id"])
            info = meta.setdefault(child, {})
            info.update({k:rec[k] for k in ("parentId","units","league","participants","type","startTime","isLive","status") if k in rec})
            if (info.get("units")=="Games" and info.get("type")=="matchup" and info.get("status")=="pending"
                    and not info.get("isLive") and is_qual(info.get("league",{}).get("name",""))
                    and info.get("startTime") and stamp(info["startTime"])>dt
                    and any(m.get("period")==0 and m.get("type") in ("spread","total") and m.get("status")=="open" for m in rec.get("markets",[]))):
                provider_qualifiers.add(child)
            row = events.get(str(info.get("parentId")))
            if not row or info.get("units") != "Games" or info.get("type") != "matchup":
                continue
            named = {p["alignment"]:p["name"].removesuffix(" (Games)") for p in info.get("participants", []) if p.get("name","").endswith(" (Games)")}
            if (set(named) != {"home","away"} or set(named.values()) != {row["home"],row["away"]}
                    or info.get("league",{}).get("name") != row["league"]):
                continue
            fixture = row["fixture"]
            periods = rec.get("periods", [])
            period_rows = periods.values() if isinstance(periods,dict) else periods
            whole = next((p for p in period_rows if p.get("period") == 0), {})
            if (data.get("op") in {"del","remove"} or info.get("isLive") or info.get("status") != "pending"
                    or whole.get("status","open") != "open" or stamp(info["startTime"]) <= dt):
                for key in by_child.get(child,set()):
                    add(key,dt,source_at,None,typ)
                continue
            if stamp(info["startTime"]) != stamp(row["start"]):
                continue
            matched.add(fixture)
            if is_qual(row["league"]):
                qualifiers.add(fixture)
            for m in rec.get("markets", []):
                result = pair_prices(m,named)
                if not result:
                    continue
                code, prices = result
                if m.get("cutoffAt") and stamp(m["cutoffAt"]) <= dt:
                    prices = [None, None]
                ver = m.get("version")
                if ver is not None:
                    version_key = child,m["key"]
                    if ver < versions.get(version_key,-1):
                        continue
                    versions[version_key] = ver
                for side,value in enumerate(prices):
                    key = fixture,code,side
                    by_child.setdefault(child,set()).add(key)
                    add(key,dt,source_at,value,typ)
    if not snapshot_end:
        raise ValueError("Incomplete opening snapshot")
    cutoff = min(end,stamp(gaps[0]["utc"])) if gaps else end
    overlapping = [s for s in scans if snapshot_end <= stamp(s["observed"]) <= cutoff]
    samples = defaultdict(list)
    rows_by_key = {}
    for s in overlapping:
        dt = stamp(s["observed"])
        for row in s["events"].values():
            if row["fixture"] in s.get("in_play_fixtures",[]) or stamp(row["start"]) <= dt:
                continue
            for code, pair in row.get("contracts",{}).items():
                for i,v in enumerate(pair["prices"]):
                    key = row["fixture"],code,i
                    ix = bisect_right([p[0] for p in paths.get(key,[])],dt)-1
                    p = paths[key][ix] if ix >= 0 else None
                    push = round(decimal(p[2]),6) if p and p[2] is not None else None
                    samples[key].append({"utc":dt.isoformat(),"desk":v,"stream":push,
                                         "stream_last_change_observed":p[0].isoformat() if p else None,
                                         "stream_last_change_source":p[1].isoformat() if p and p[1] else None})
                    rows_by_key[key] = row,pair["labels"][i]
    details = []
    for key,t in alerts.items():
        identity = issued_identity(store,t,scans)
        if not identity:
            details.append({"selection":t["selection"],"alert_odds":t["new"],"excluded":"original identity or odds unverified"})
            continue
        if key in rows_by_key and rows_by_key[key][1] != t["selection"]:
            raise ValueError("Alert label mismatch")
        history = paths.get(key,[])
        prior = None
        changes = []
        for dt,origin,value,typ in history:
            if dt < stamp(t["sent"]):
                prior = value
                continue
            if prior is not None and value is not None and value != prior:
                before, after = decimal(prior), decimal(value)
                changes.append({"received":dt.isoformat(),"source":origin.isoformat() if origin else None,
                                "from":round(before,6),"to":round(after,6),"pp":rate(before,after)})
            prior = value
        details.append({"selection":t["selection"],"contract":t["contract"],"fixture":t["fixture"],"event":t["league"],"sent":t["sent"],
                        "alert_odds":t["new"],"identity":identity,"first":next((round(decimal(v),6) for tm,_,v,_ in history if tm>=stamp(t["sent"]) and v is not None),None),
                        "drops":sum(c["pp"]>0 for c in changes),"drifts":sum(c["pp"]<0 for c in changes),
                        "moves":changes,"scans":[s for s in samples.get(key,[]) if stamp(s["utc"])>=stamp(t["sent"])]})
    examples = []
    counts = Counter()
    partial_counts = Counter()
    partial_alerts = []
    prior = next((s for s in reversed(scans) if stamp(s["observed"])<snapshot_end),None)
    if prior and overlapping and stamp(overlapping[0]["observed"])-stamp(prior["observed"]) <= timedelta(minutes=20):
        finish=stamp(overlapping[0]["observed"])
        for row in prior["events"].values():
            if row["fixture"] in prior.get("in_play_fixtures",[]):
                continue
            for code,pair in row.get("contracts",{}).items():
                for side,old_price in enumerate(pair["prices"]):
                    key=row["fixture"],code,side
                    observed=samples.get(key,[])
                    ticks=[p for p in paths.get(key,[]) if p[0]<=finish]
                    if (not observed or stamp(observed[0]["utc"])!=finish or observed[0]["stream"] is None
                            or not ticks or ticks[0][3]!="snapshot" or any(p[2] is None for p in ticks)):
                        continue
                    drops=sum(decimal(p[2])>decimal(q[2]) for p,q in zip(ticks,ticks[1:]))
                    drifts=sum(decimal(p[2])<decimal(q[2]) for p,q in zip(ticks,ticks[1:]))
                    partial_counts.update(sides=1,drops=drops,drifts=drifts)
                    if drops and drifts and old_price==observed[0]["desk"]:
                        partial_counts["two_way_desk_flat"]+=1
                    if key in alerts and stamp(alerts[key]["sent"])<=ticks[0][0]:
                        partial_alerts.append({"selection":alerts[key]["selection"],"desk_before":old_price,
                                               "desk_after":observed[0]["desk"],"drops":drops,"drifts":drifts})
    differences=[abs(rate(s["desk"],s["stream"])) for series in samples.values() for s in series if s["stream"] is not None]
    for key, points in samples.items():
        path_points = paths.get(key,[])
        for a,b in zip(points,points[1:]):
            beginning,finish=stamp(a["utc"]),stamp(b["utc"])
            if not (timedelta(minutes=10)<=finish-beginning<=timedelta(minutes=20)) or any(v["stream"] is None for v in (a,b)):
                continue
            between = [p for p in path_points if beginning<p[0]<=finish]
            if any(p[2] is None for p in between):
                counts["interrupted_line_intervals"]+=1
                continue
            moves = [a["stream"], *[round(decimal(p[2]),6) for p in between]]
            d=sum(x>y for x,y in zip(moves,moves[1:]))
            u=sum(x<y for x,y in zip(moves,moves[1:]))
            counts["side_intervals"]+=1
            counts["drops"]+=d
            counts["drifts"]+=u
            if d or u:
                counts["sides_with_stream_changes"]+=1
                desk_direction=(b["desk"]>a["desk"])-(b["desk"]<a["desk"])
                stream_direction=(moves[-1]>moves[0])-(moves[-1]<moves[0])
                if stream_direction and desk_direction==stream_direction:
                    counts["same_net_direction_on_desk"]+=1
                elif desk_direction==0:
                    counts["desk_endpoints_flat_on_moving_side"]+=1
                else:
                    counts["other_net_direction_on_desk"]+=1
            peak = moves[0]
            largest = 0
            for price in moves[1:]:
                largest=max(largest,100*(1/price-1/peak))
                peak=max(peak,price)
            if largest>4+1e-9:
                counts["stream_over_4pp_intervals"]+=1
                if 100*(1/b["desk"]-1/a["desk"])<=4+1e-9:
                    counts["stream_over_4pp_desk_endpoints_did_not_cross"]+=1
            if d and u:
                counts["two_way_side_intervals"]+=1
                if a["desk"]==b["desk"]:
                    counts["two_way_desk_flat"]+=1
                row, label = rows_by_key[key]
                examples.append({"league":row["league"],"fixture":row["home"]+" vs "+row["away"],"selection":label,
                                 "alerted":key in alerts and stamp(alerts[key]["sent"])<=beginning,"desk":[a["desk"],b["desk"]],
                                 "scans":[a["utc"],b["utc"]],"stream":moves})
    return {"start":first.isoformat(),"last_frame":last.isoformat(),"gaps":gaps,"overlap_scans":[s["observed"] for s in overlapping],
            "median_frame_delay_s":round(median(arrival_lags),2) if arrival_lags else None,
            "median_absolute_price_difference_pp":round(median(differences),4) if differences else None,
            "matched_fixtures":len(matched),"matched_challenger_fixtures":len({r["fixture"] for r in events.values() if r["fixture"] in matched and "challenger" in r["league"].lower()}),
            "matched_challenger_qualifying":len(qualifiers),"stream_challenger_qualifying":len(provider_qualifiers),
            "desk_challenger_qualifying":len({r["fixture"] for r in events.values() if is_qual(r["league"])}),
            "stream_seeded_sides":len([k for k,v in paths.items() if v]),"paired_scan_sides":sum(p["stream"] is not None for a in samples.values() for p in a),
            "desk_scan_sides":sum(len(a) for a in samples.values()),"intervals":dict(counts),"alerted_lines":details,"two_way_examples":examples,
            "opening_partial_interval":{"first_scan":prior["observed"] if prior else None,"stream_from":snapshot_end.isoformat(),
                                        "second_scan":overlapping[0]["observed"] if overlapping else None,"counts":dict(partial_counts),"alerts":partial_alerts}}
