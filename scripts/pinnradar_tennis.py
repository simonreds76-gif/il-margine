"""Private quarter-hour snapshots of the PinnRadar ATP and Challenger pre-match board."""
import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests
import price_drop_watch as watch
import desk_games

BOOK = "Pinnacle"
SOURCE = "PinnRadar"
BUCKET = "tennis-price-moves-private"
BASE = "https://pinnradar.com"
VERSION = 1
MAX_GAP = timedelta(minutes=40)


def utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None


def quote(value):
    try:
        price = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return price if math.isfinite(price) and price > 1 else None


def valid_limit_amount(raw):
    if isinstance(raw, bool):
        return None
    try:
        amount = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(amount) or amount < 0:
        return None
    return amount


def reported_market_max(market):
    """Only a maximum attached to this exact priced object travels with a selection."""
    amount = valid_limit_amount(market.get("max"))
    if amount is None:
        return None
    limit = {"amount": amount}
    currency = market.get("currency")
    if isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency):
        limit["currency"] = currency
    return limit


def period_limits(period):
    """Keep separately named period caps for later verification of their meaning and units."""
    metadata = period.get("meta")
    if not isinstance(metadata, dict):
        return {}
    limits = {}
    for field, raw in metadata.items():
        if field.startswith("max_"):
            amount = valid_limit_amount(raw)
            if amount is not None:
                limits[field] = amount
    return limits


def game_market_sample(board, matches, observed):
    parents={(m["league"],m["start"],frozenset((m["home"],m["away"]))):m for m in matches.values()}
    samples={}
    def odds(value):
        try: return math.isfinite(float(value)) and float(value)>1
        except (TypeError,ValueError): return False
    for event in board["events"]:
        if not isinstance(event,dict) or event.get("event_type")!="prematch" or str(event.get("sport_id"))!="2" or event.get("is_have_odds") is not True:continue
        names=[str(event.get(s) or "") for s in ("home","away")]
        if not all(n.endswith(" (Games)") for n in names):continue
        names=[n.removesuffix(" (Games)") for n in names]
        try:
            stamp=datetime.fromisoformat(event["starts"].replace("Z","+00:00"))
            if stamp.tzinfo is None or stamp<=observed:continue
            stamp=stamp.astimezone(timezone.utc).isoformat()
        except (TypeError,ValueError,KeyError,AttributeError):continue
        m=parents.get((event.get("league_name"),stamp,frozenset(names)))
        if not m:continue
        parent_id=str(event.get("parent_id") or "")
        if parent_id not in ("","0",m["id"]):continue
        periods=event.get("periods")
        p=periods.get("num_0") if isinstance(periods,dict) else None
        if not isinstance(p,dict) or str(p.get("number",0))!="0" or str(p.get("status","")).lower() not in ("o","open","1"):continue
        key=m["id"]
        if key in samples:
            samples[key]=None
            continue
        record={"home":names[0],"away":names[1],"start":m["start"],"tour":m["tour"],"games_id":str(event.get("event_id") or "")}
        caps = period_limits(p)
        if caps:
            record["period_limits"] = caps
        for market,field,first,second in (("spreads","hdp","home","away"),("totals","points","over","under")):
            lines={}
            ladder=p.get(market)
            for k,v in (ladder.items() if isinstance(ladder,dict) else ()):
                if not isinstance(v,dict) or v.get("is_suspended") or v.get("suspended"):continue
                try:line=float(v[field])
                except (ValueError,TypeError,KeyError):continue
                try: agrees=float(k)==line
                except (ValueError,TypeError):agrees=False
                if not agrees or not math.isfinite(line) or (market=="totals" and line<12) or not all(odds(v.get(s)) for s in (first,second)):continue
                lines[str(line)]=[float(v[first]),float(v[second])]
                limit = reported_market_max(v)
                if limit is not None:
                    record.setdefault("limits", {}).setdefault(market, {})[str(line)] = limit
            record[market]=lines
        samples[key]=record
    return {k:v for k,v in samples.items() if v and (v["spreads"] or v["totals"])}


def board_rows(board, observed):
    if not isinstance(board, dict) or str(board.get("sport_id")) != "2" or not isinstance(board.get("events"), list):
        raise ValueError("Missing full tennis board")
    rows, counts, conflicts, fixtures = {}, Counter(), set(), {}
    period_status = Counter()
    explicit_live_ids, explicit_live_pairs = set(), set()
    for event in board["events"]:
        if not isinstance(event, dict):
            raise ValueError("Invalid board event")
        if str(event.get("sport_id")) == "2" and event.get("event_type") == "live":
            sides = tuple(sorted(str(event.get(k) or "").strip().casefold() for k in ("home", "away")))
            if all(sides) and sides[0] != sides[1]:
                explicit_live_pairs.add((str(event.get("league_name") or "").strip().casefold(), sides))
                if event.get("event_id"): explicit_live_ids.add(str(event["event_id"]))
        league = str(event.get("league_name") or "").strip()
        circuit = re.match(r"^(ATP|WTA)(?:\s|$)", league, re.I)
        if not circuit:
            counts["other_tour"] += 1
            continue
        names = [str(event.get(side) or "").strip() for side in ("home", "away")]
        if (len(set(n.casefold() for n in names)) != 2 or not all(names)
                or re.search(r"doubles|outright|special|\(games\)|\(sets\)|/| & |\btbd\b|winner of|^qualifier$", " ".join([league, *names]), re.I)
                or any(re.fullmatch(r"(?:qualifier|bye|q\d?|-)", n, re.I) for n in names)):
            counts["non_match_winner_or_placeholder"] += 1
            continue
        event_id, start = str(event.get("event_id") or ""), utc(event.get("starts"))
        if (not event_id.isdigit() or int(event_id) == 0 or str(event.get("sport_id")) != "2"
                or event.get("event_type") != "prematch" or not start or start <= observed):
            counts["unverified_prematch"] += 1
            continue
        p0 = (event.get("periods") or {}).get("num_0") or {}
        market = p0.get("money_line") or {}
        prices = [quote(market.get(side)) for side in ("home", "away")]
        status = str(p0.get("status", "")).lower()
        period_status[status[:24]] += 1
        if (event.get("is_have_odds") is not True or not all(prices) or quote(market.get("draw"))
                or str(p0.get("number", 0)) != "0" or status not in {"open", "o", "1"}
                or market.get("is_suspended") is True or market.get("suspended") is True):
            counts["unavailable_or_unverified_market"] += 1
            continue
        identity = [league.casefold(), *sorted(n.casefold() for n in names)]
        uid = hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode()).hexdigest()[:32]
        tour = circuit[1].upper()
        if tour == "ATP" and "challenger" in league.lower():
            tour = "Challenger"
        elif tour == "WTA" and re.match(r"^WTA\s+125k?\b", league, re.I):
            tour = "WTA 125"
        row = dict(id=event_id, fixture=uid, league=league, tour=tour,
                   home=names[0], away=names[1], home_price=prices[0], away_price=prices[1],
                   start=start.isoformat(), event_updated_at=event.get("updated_at"))
        limit = reported_market_max(market)
        if limit is not None:
            row["reported_market_max"] = limit
        caps = period_limits(p0)
        if caps:
            row["match_period_limits"] = caps
        if event_id in rows and rows[event_id] != row:
            conflicts.add(event_id)
        if uid in fixtures and fixtures[uid] != event_id:
            conflicts.update((event_id, fixtures[uid]))
        fixtures[uid]=event_id
        rows[event_id]=row
    in_play_fixtures = {
        hashlib.sha256(json.dumps([league, *pair], ensure_ascii=False).encode()).hexdigest()[:32]
        for league, pair in explicit_live_pairs
    }
    for eid, row in list(rows.items()):
        pair = tuple(sorted((row["home"].casefold(),row["away"].casefold())))
        if eid in explicit_live_ids or (row["league"].casefold(),pair) in explicit_live_pairs:
            in_play_fixtures.add(row["fixture"])
            del rows[eid]
            counts["confirmed_in_play"] += 1
    for eid in conflicts:
        rows.pop(eid, None)
    counts["ambiguous_event_ids"]=len(conflicts)
    for eid, sample in game_market_sample(board, rows, observed).items():
        rows[eid]["contracts"] = desk_games.contracts(sample)
        if "period_limits" in sample:
            rows[eid]["games_period_limits"] = sample["period_limits"]
    return {"schema":VERSION,"source":SOURCE,"bookmaker":BOOK,"observed":observed.isoformat(),
            "paper_minimum_usd":desk_games.MINIMUM_USD,
            "events_received":len(board["events"]), "excluded":dict(counts),
            "in_play_fixtures":sorted(in_play_fixtures), "period_status_counts":dict(period_status),"events":rows}


def detection(previous, current, before, observed):
    if not previous or previous["fixture"] != current["fixture"] or previous["id"] != current["id"] or previous["start"] != current["start"]:
        return None
    start=utc(current["start"])
    if not (0 < (observed-before).total_seconds() <= MAX_GAP.total_seconds()
            and start-timedelta(hours=2) <= before < observed < start):
        return None
    if previous["home"]==current["home"] and previous["away"]==current["away"]:
        old=[previous["home_price"],previous["away_price"]]
    elif previous["away"]==current["home"] and previous["home"]==current["away"]:
        old=[previous["away_price"],previous["home_price"]]
    else:
        return None
    new=[current["home_price"],current["away_price"]]
    old_p=old[1]/sum(old)
    new_p=new[1]/sum(new)
    side=0 if new_p>old_p else 1
    delta=abs(new_p-old_p)*100
    if delta+1e-10 < 3 or new[side]>=old[side]:
        return None
    return dict(source=SOURCE,bookmaker=BOOK,event_id=current["id"],league=current["league"],tour=current["tour"],
                player=current[("home","away")[side]],opponent=current[("away","home")[side]],
                start=current["start"], before=before.isoformat(), after=observed.isoformat(),
                old=old[side],new=new[side],old_opponent=old[1-side],new_opponent=new[1-side],
                old_p=old_p if side==0 else 1-old_p,new_p=new_p if side==0 else 1-new_p,
                move_pp=round(delta,6),minutes_to_start=round((start-observed).total_seconds()/60,3),
                result="Pending", cohort="prospective observation",telegram_sent=False)


def advance(state, snap, *, track_first=True):
    now=utc(snap["observed"])
    prior_observed=utc(state.get("observed"))
    if prior_observed and now<=prior_observed:
        return state, []
    old=state.get("events",{})
    # Keep continuity evidence even across temporarily missing events. Prices can
    # only be compared when the event was present on both consecutive boards.
    guards={k:v for k,v in state.get("guards",{}).items() if utc(v["start"])+timedelta(days=7)>now}
    for uid in snap.get("in_play_fixtures", []):
        guard = guards.get(uid, {"start":snap["observed"], "issued":False})
        guards[uid] = {**guard, "blocked":True}
    moves=[]
    open_rows = {}
    for eid,row in snap["events"].items():
        uid=row["fixture"]
        last=guards.get(uid,{})
        changed=last.get("start") and last["start"]!=row["start"]
        blocked=bool(last.get("blocked") or (changed and now>=utc(last["start"])))
        if not blocked:
            open_rows[eid]=row
        issued=bool(last.get("issued"))
        if track_first and not blocked and not issued and prior_observed and not changed:
            move=detection(old.get(eid),row,prior_observed,now)
            if move:
                moves.append((uid,move))
                issued=True
        guards[uid]=dict(start=row["start"],blocked=blocked,issued=issued)
    return dict(schema=VERSION,observed=snap["observed"],source=SOURCE,bookmaker=BOOK,
                events=open_rows,guards=guards),moves


class Store:
    def __init__(self):
        url=os.environ["SUPABASE_URL"].rstrip("/")
        u=urlsplit(url)
        if u.scheme!="https" or not (u.hostname or "").endswith(".supabase.co") or u.path or u.username or u.query:
            raise ValueError("Unexpected private store")
        self.base=url+"/storage/v1"
        key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.headers={"apikey":key,"Authorization":"Bearer "+key}
        meta=self.request("GET","/bucket/"+BUCKET)
        if self.missing(meta):
            result=self.request("POST","/bucket",json={"id":BUCKET,"name":BUCKET,"public":False})
            self.require(result)
            meta=self.request("GET","/bucket/"+BUCKET)
        self.require(meta)
        obj=meta.json()
        if obj.get("public") is not False or obj.get("id")!=BUCKET:
            raise ValueError("Unverified private bucket")

    def request(self,verb,path,headers=None,**args):
        return requests.request(verb,self.base+path,headers={**self.headers,**(headers or {})},
                                timeout=20,allow_redirects=False,**args)

    @staticmethod
    def require(r):
        if not 200<=r.status_code<300: raise RuntimeError(f"Private storage HTTP {r.status_code}")

    @staticmethod
    def missing(r):
        if r.status_code not in (400,404): return False
        try: obj=r.json()
        except ValueError: return False
        return str(obj.get("statusCode"))=="404" or obj.get("error") in {"not_found","NoSuchKey","NoSuchBucket"} or str(obj.get("message","")).lower() in {"object not found","bucket not found"}

    def get(self,path):
        r=self.request("GET","/object/authenticated/"+BUCKET+"/"+path)
        if self.missing(r): return None
        self.require(r)
        return r.json()

    def put(self,path,data,replace=False):
        r=self.request("POST","/object/"+BUCKET+"/"+path,headers={"x-upsert":str(replace).lower(),"cache-control":"no-store"},json=data)
        if not replace and r.status_code in (400,409) and any(s in r.text.lower() for s in ("duplicate","already exists")): return False
        self.require(r)
        return True

    def verify_snapshot(self, path, snap):
        if self.get(path) != snap:
            raise RuntimeError("Authenticated snapshot read-back failed")
        with requests.get(self.base+"/object/public/"+BUCKET+"/"+path, stream=True,
                          timeout=15, allow_redirects=False) as response:
            if response.status_code not in (400,401,403,404):
                raise RuntimeError(f"Unexpected anonymous storage status {response.status_code}")
        print("Private snapshot read-back verified. Anonymous read denied.")


def requested_quarter(now, requested):
    slot = now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)
    if not requested:
        return slot
    target = utc(requested)
    if (target is None or target.minute % 15 or
            target.strftime("%Y-%m-%dT%H:%M:00Z") != requested):
        raise ValueError("Expected an exact UTC quarter-hour")
    return slot if target == slot else None


def run():
    requested = os.getenv("DROP_SHOT_SCHEDULED_SLOT")
    now = datetime.now(timezone.utc)
    slot = requested_quarter(now, requested)
    if slot is None:
        print("Skipped delayed clock request outside its quarter-hour.")
        return
    store = Store()
    path=slot.strftime("%Y/%m/%d/%H%M.json")
    snap=store.get("snapshots/"+path)
    if snap is None:
        attempt = {
            "utc": now.isoformat(), "slot": slot.isoformat(),
            "trigger": "hosted_clock" if requested else os.getenv("GITHUB_EVENT_NAME", "local"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
        }
        if not store.put("attempts/"+path, attempt):
            raise RuntimeError("Quarter hour already attempted without a stored snapshot. Next slot can retry.")
        response=requests.get(BASE+"/kit/v1/prematch/fixtures",params={"sport_id":2},
                              headers={"x-portal-apikey":os.environ["PINNRADAR_KEY"]},
                              timeout=25,allow_redirects=False)
        if response.status_code!=200: raise RuntimeError(f"PinnRadar HTTP {response.status_code}. No same-slot retry.")
        snap=board_rows(response.json(),datetime.now(timezone.utc))
        if not store.put("snapshots/"+path,snap): snap=store.get("snapshots/"+path)
    else:
        print("Reusing the saved quarter-hour snapshot. No provider call.")
    if os.getenv("VERIFY_PRIVATE_SNAPSHOT")=="true":
        store.verify_snapshot("snapshots/"+path,snap)
    if snap["excluded"].get("unavailable_or_unverified_market",0) and not snap["events"]:
        raise ValueError(f"No verified match-winner rows; period status counts: {snap['period_status_counts']}")
    last=store.get("latest.json") or {}
    # Recover a saved snapshot if a prior job stopped between storage and projection.
    last_seen=utc(last.get("observed"))
    backlog=[]
    for offset in (2,1):
        past=slot-timedelta(minutes=15*offset)
        if last_seen is None or last_seen<past+timedelta(minutes=15):
            prior=store.get("snapshots/"+past.strftime("%Y/%m/%d/%H%M.json"))
            if prior and (not last_seen or utc(prior["observed"])>last_seen): backlog.append(prior)
    for item in [*backlog,snap]:
        fresh_pilot=utc(item["observed"])>=watch.START
        next_state,moves=advance(last,item,track_first=not fresh_pilot)
        if next_state is last: continue
        if fresh_pilot:
            blocked={k for k,v in next_state["guards"].items() if v["blocked"]}
            batch=desk_games.compare(last,item,next_state,blocked)
            store.put("drop-scans-v2/"+watch.object_key(item["observed"]),batch)
        for fixture,move in moves:
            store.put(f"moves/{move['start'][:4]}/{fixture}.json",move)
        store.put("latest.json",next_state,replace=True)
        last=next_state
    counts=Counter(v["tour"] for v in snap["events"].values())
    print(f"Private capture {snap['observed']}: ATP {counts['ATP']}, Challenger {counts['Challenger']}, WTA {counts['WTA']}, WTA 125 {counts['WTA 125']}.")
    if utc(snap["observed"])>=watch.START:
        key="drop-scans-v2/"+watch.object_key(snap["observed"])
        batch=store.get(key)
        if batch is None:
            raise RuntimeError("Saved scan lacks its committed movement batch; cannot deliver.")
        mode=os.getenv("PRIVATE_DROP_DELIVERY","off")
        delivery="off"
        if mode=="verify":
            watch.private_chat()
            delivery="private direct chat verified"
        elif mode=="send":
            delivery=watch.deliver({**batch, "moves":desk_games.alert_moves(batch)},store,
                                   now=datetime.now(timezone.utc),dispatch_clock=lambda: datetime.now(timezone.utc))
        print(f"Matched fixtures {batch['compared_pairs']}; observed shortenings {len(batch['moves'])}; Telegram {delivery}.")


if __name__=="__main__":
    run()
