"""11am private booking and fouls research. The daily scan never places a bet."""
import os
import re
import sys
import time

from requests.exceptions import ConnectionError, Timeout
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from statshub_daily_board import LINK, REPORT, Reads, board_matches
from statshub_daily_contracts import exact_quote, identity, norm, utc
from johnny_cards_calendar import calendar
from statshub_daily_focus import flank, number
from statshub_daily_io import Provider, RemoteError, Store, http, send_digest, telegram_private, timestamp

LONDON = ZoneInfo("Europe/London")
FLOOR = 4.0


def edition_key(day, part):
    return f"johnny/editions/{day}/{part}.json"


class JohnnyStore(Store):
    def put(self, name, value, replace=True):
        # These objects have a single writer per phase, or use create-if-absent.
        # Receipts, shared Admin data and OAuth rotation retain their original contracts.
        if not name.startswith(("johnny/editions/", "johnny/days-expanded/", "johnny/rehearsals/")):
            return super().put(name, value, replace)

        missing = object()
        for attempt in range(3):
            try:
                return super().put(name, value, replace)
            except (Timeout, ConnectionError, RemoteError) as error:
                if isinstance(error, RemoteError) and error.status_code not in (408, 429, 500, 502, 503, 504):
                    raise
                saved = self.get(name, missing)
                if saved == value:
                    return True
                if not replace and saved is not missing:
                    return False
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)


def private_store():
    # The cloud CPU can spend minutes on the guide before reusing its storage connection.
    # Transport retries are for storage reads. Checkpoint writes reconcile by object name above.
    base = os.environ["SUPABASE_URL"].rstrip("/") + "/storage/v1/"
    retry = Retry(total=3, read=3, connect=3, status=3, backoff_factor=1,
                  allowed_methods={"GET","HEAD"}, status_forcelist=(408,429,500,502,503,504))
    http.mount(base,HTTPAdapter(max_retries=retry))
    return JohnnyStore()


def data(reader, tool, args):
    packet = reader.read(tool, args, "morning")
    return (packet or {}).get("data") or {}


def profile(reader, team, fixture, venue):
    doc = data(reader, "getTeamPerformance", dict(teamId=team["id"], competitionId=fixture["competitionId"],
                                              venue=venue, limit=10))
    totals = doc.get("totals") or {}
    own = (totals.get("stats") or {}).get("yellowCards") or {}
    against = (totals.get("opponentStats") or {}).get("yellowCards") or {}
    if totals.get("games") and number(own.get("avg")) and number(against.get("avg")):
        return dict(games=totals["games"], own=own["avg"], opponent=against["avg"], window=doc.get("context", ""))
    return None


def triage(reader, f):
    doc = data(reader, "getMatchDetails", {"matchId": f["id"]}).get("data") or {}
    match = doc.get("matches") or {}
    if (identity(match.get("id")) != identity(f["id"]) or match.get("status") != "scheduled"
        or match.get("kickoffTimestamp") != int(utc(f["ko"]).timestamp())
        or identity((doc.get("competition") or {}).get("competitionId")) != identity(f["competitionId"])):
        return {**f, "gap": "fixture, start or status unverified"}
    t = {**f, "teams": {}, "profiles": {}, "venue": (doc.get("venues") or {}).get("name"), "ref": None}
    for side in ("home", "away"):
        team = doc.get(side + "Team") or {}
        if not team.get("id") or norm(team.get("name", "")) != norm(f[side]):
            return {**f, "gap": "team identity unverified"}
        t["teams"][side] = team
        t["profiles"][side] = profile(reader, team, f, side)
    ref = doc.get("referees") or {}
    if ref.get("id") and match.get("seasonId"):
        sample = data(reader, "getReferee", dict(refereeId=ref["id"], seasonId=match["seasonId"],
                      competitionId=f["competitionId"], recentGames=10))
        figures = (((sample.get("record") or {}).get("recentGames") or {}).get("totals") or {})
        if figures.get("games") and number(figures.get("yellowCardsPerGame")):
            t["ref"] = dict(name=ref.get("name"), games=figures["games"], avg=figures["yellowCardsPerGame"])
    from johnny_cards_weather import weather
    t["conditions"] = weather(t)
    return t


def same_player(short, full):
    if not short or not full:
        return False
    if norm(short) == norm(full):
        return True
    first, sep, surname = short.partition(" ")
    given, _, family = full.partition(" ")
    return bool(sep and len(first.rstrip(".")) == 1 and norm(first) == norm(given)[:1] and norm(surname) == norm(family))


def distinct_opponent(player, other):
    rival = flank(player, other)
    if rival:
        return rival
    # Only identify central assignments where the two listed roles are unique opposites.
    role = player.get("position")
    direct = {"CDM": "CAM", "CAM": "CDM", "LCDM": "RCAM", "RCDM": "LCAM",
              "RCAM": "LCDM", "LCAM": "RCDM"}
    eligible = [p for p in other.get("players", []) if role in direct and p.get("position") == direct[role]]
    return eligible[0] if len(eligible) == 1 and eligible[0].get("id") else None


def starting_cases(reader, f):
    xi = data(reader, "getLineups", {"matchId": f["id"]}).get("lineups") or {}
    if identity(xi.get("matchId")) != identity(f["id"]):
        return [], "starting elevens unavailable"
    players = []
    for side, opposite in (("home", "away"), ("away", "home")):
        team, other = xi.get(side) or {}, xi.get(opposite) or {}
        if identity(team.get("teamId")) != identity(f["teams"][side]["id"]) or team.get("status") not in ("predicted", "confirmed"):
            continue
        rival_ok = identity(other.get("teamId")) == identity(f["teams"][opposite]["id"]) and other.get("status") in ("predicted","confirmed")
        for p in team.get("players") or []:
            if p.get("id") and p.get("name"):
                players.append(dict(player=p, side=side, lineup=team["status"],
                                    rival=distinct_opponent(p, other) if rival_ok else None))
    verified = []
    for i in range(0, len(players), 6):
        group = players[i:i+6]
        args = [dict(matchId=f["id"], playerId=r["player"]["id"], statType="yellowCards", line=0.5) for r in group]
        doc = data(reader, "checkBet", {"bets": args})
        for case in group:
            matched = [r for r in doc.get("bets", []) if same_player(case["player"]["name"], r.get("player", ""))
                       and (r.get("fixture") or {}).get("isHome") is (case["side"] == "home")]
            if len(matched) != 1:
                continue
            rep = matched[0]
            bet, fixture = rep.get("bet") or {}, rep.get("fixture") or {}
            if (rep.get("settled") or rep.get("matchStatus") in ("finished","live","cancelled","postponed")
                or bet.get("statType") != "yellowCards" or bet.get("line") != 0.5
                or fixture.get("kickoffTimestamp") != int(utc(f["ko"]).timestamp())
                or identity(fixture.get("competitionId")) != identity(f["competitionId"])
                or any(norm(fixture.get(s,"")) != norm(f[s]) for s in ("home","away"))):
                continue
            groups = {s["label"]: [s.get("hits"), s.get("starts")] for s in rep.get("samples", [])
                      if type(s.get("starts")) is int and type(s.get("hits")) is int and 0 <= s["hits"] <= s["starts"] and s["starts"] > 0}
            if "In this competition" not in groups or "Last 20 starts" not in groups:
                continue
            verified.append({**case, "name": rep["player"], "groups": groups, "availability": rep.get("availability")})
    ids = {identity(c["player"]["id"]) for c in verified}
    for c in players:
        if identity(c["player"]["id"]) not in ids:
            verified.append({**c, "name":c["player"]["name"], "groups":{}, "availability":None})
    return verified, f"{len(ids)} player histories verified from {len(players)} listed starters"


def stat_sample(reader, f, pid, stat, club):
    doc = data(reader, "getPlayerStats", dict(playerId=pid, statType=stat, appearances="starts", limit=20,
               competitionId=f["competitionId"]))
    req, span = doc.get("requestedStat") or {}, doc.get("span") or {}
    clubs = span.get("teams") or []
    if (req.get("statType") != stat or len(clubs) != 1 or norm(clubs[0]) not in
        {norm(club.get("name","")), norm(club.get("shortName",""))} or not span.get("to") or span["to"] >= f["ko"][:10]):
        return None
    total = req.get("total")
    minutes = (doc.get("totals") or {}).get("minutes")
    n = doc.get("games")
    if not number(total) or not number(minutes) or not minutes or type(n) is not int or not 1 <= n <= 20:
        return None
    hits = req.get("gamesWith") or {}
    columns = doc.get("matchColumns") or []
    if stat in columns:
        vals = [row[columns.index(stat)] for row in doc.get("matchRows",[]) if len(row)==len(columns)]
        if len(vals)==n and all(number(v) for v in vals):
            hits = {f"{k}+":sum(v>=k for v in vals) for k in (1,2,3)}
    return dict(total=total, minutes=minutes, starts=n, per90=round(90*total/minutes,2),
                fromDate=span.get("from"), through=span["to"], hits=hits)


def offers(doc, f, case, at, now):
    if not board_matches(f, doc) or utc(f["ko"]) <= now:
        return []
    found = []
    names = set(case.get("priceAliases",[norm(case["name"]),norm(case["player"]["name"])]))
    for m in doc.get("markets", []):
        market = m.get("name","").lower()
        if market not in ("player to be booked", "player fouls committed", "player fouls"):
            continue
        for o in m.get("outcomes", []):
            match = re.fullmatch(r"(.+) Over (\d+\.5)", o.get("label", ""))
            if not match or norm(match[1]) not in names:
                continue
            card = market == "player to be booked"
            line = float(match[2])
            if line not in ((0.5,) if card else (0.5,1.5,2.5)):
                continue
            age = (now-utc(at)).total_seconds()/60
            q = exact_quote(o, float("inf")) if age >= 0 else None
            if q:
                found.append(dict(kind="booking" if card else "fouls", line=line, at=at,
                                  books=o.get("books"), average=o.get("average"), **q))
    return found


def investigate(reader, f, clock, analyst):
    cases, note = starting_cases(reader, f)
    f["screen"] = note
    f["screened"] = [dict(name=c["name"], role=c["player"].get("position"), groups=c["groups"]) for c in cases]
    f["cases"] = []
    if not cases:
        return
    f["teamNews"] = data(reader,"getTeamNews",{"matchId":f["id"]})
    aliases = {}
    for c in cases:
        for name in {norm(c["name"]),norm(c["player"]["name"])}:
            aliases.setdefault(name,set()).add(identity(c["player"]["id"]))
    for c in cases:
        c["priceAliases"] = [n for n in {norm(c["name"]),norm(c["player"]["name"])} if len(aliases[n])==1]
    selected = analyst.select_players(f, cases)
    for c in selected:
        p, side = c["player"], c["side"]
        opp = "away" if side == "home" else "home"
        c["committed"] = stat_sample(reader,f,p["id"],"fouls",f["teams"][side])
        rival = c["rival"]
        c["drawn"] = stat_sample(reader,f,rival["id"],"foulsWon",f["teams"][opp]) if rival else None
        f["cases"].append(c)
    f["frozenAt"] = clock()
    packet = reader.read("getMatchOdds", dict(matchId=f["id"], markets=["player to be booked","player fouls"]), "morning") or {}
    for c in f["cases"]:
        c["offers"] = offers(packet.get("data") or {}, f, c, packet["at"], utc(clock())) if packet.get("at") else []
        for q in c["offers"]:
            if norm(q["book"])=="bet365":
                q["rules"] = ("Standard pre-match named player, must start, on-field yellow or red qualifies; "
                              "yellow-only history understates this broader definition." if q["kind"]=="booking"
                              else "Standard named-player fouls committed, starter participation; an infringement resulting in a free kick or penalty.")
                q["rulesReference"] = ("https://help.bet365.com/s/en/sports/how-is-my-bet-settled" if q["kind"]=="booking"
                                       else "https://help.bet365.com/s/en/sportsrules/soccer/match-statistics")
                q["rulesChecked"] = "2026-11-23"
        card = max((q for q in c["offers"] if q["kind"]=="booking"),key=lambda q:q["odds"],default=None)
        c["booking"] = card
    analyst.assess(f)


def scan(reader, day, analyst, clock=timestamp, save=None, previous=None):
    def checkpoint(stage):
        report = dict(day=day, at=clock(), calendar=leagues, slate=reviewed, reads=len(reader.log),
                      failures=reader.errors, stage=stage, guideSHA256=analyst.digest,
                      method="Johnny Poker public combined edition 1.0")
        if save:
            save(report)
        return report

    if previous and previous.get("day")==day and previous.get("guideSHA256")==analyst.digest and previous.get("stage") in ("ranked","finished"):
        reviewed, leagues = previous["slate"], previous["calendar"]
    else:
        reviewed, leagues = calendar(reader, day, utc(clock()))
        checkpoint("calendar")
        if not any(not window["gap"] for window in leagues) and not reviewed:
            raise RuntimeError("Calendar unavailable; a no-picks report would be misleading")
        for i, f in enumerate(reviewed):
            if len(reader.log) >= 140:
                f["gap"] = "daily allowance reserved for detailed player checks"
            else:
                reviewed[i] = triage(reader, f)
        eligible = [f for f in reviewed if not f.get("gap")]
        selected = {f["id"]: rank for rank, f in enumerate(analyst.select_fixtures(eligible), start=1)}
        for f in reviewed:
            f["reviewState"] = ("unavailable" if f.get("gap") else
                                "selected" if f["id"] in selected else "reserve")
            if f["id"] in selected:
                f["priority"] = selected[f["id"]]
        checkpoint("ranked")
    for f in sorted(reviewed, key=lambda item: item.get("priority", 1000)):
        if f.get("reviewState") != "selected":
            continue
        if utc(f["ko"]) <= utc(clock()):
            f.update(reviewState="unavailable", gap="scheduled kickoff passed")
        else:
            try:
                investigate(reader, f, clock, analyst)
                missing = not f.get("screened")
                f["reviewState"] = "unavailable" if missing else "complete"
                if missing:
                    f["gap"] = f.get("screen") or "player evidence unavailable"
            except (ValueError, KeyError, TypeError) as error:
                f.update(reviewState="unavailable", gap="Player assessment incomplete ("+type(error).__name__+")", cases=[])
                reader.errors += 1
        f["verdictAt"] = clock()
        checkpoint("ranked")
    return checkpoint("finished")


def lines(report, as_of=None):
    calendar = report["calendar"]
    complete = sum(not l["gap"] for l in calendar)
    result = [f"Booking and fouls scan · {report['day']}", f"{len(report['slate'])} upcoming fixtures. Five European leagues, Champions League and covered South American competitions.",
              f"Through 11am London tomorrow. {complete}/{len(calendar)} calendar windows verified."]
    for f in sorted(report["slate"], key=lambda x: ("screen" not in x,x["ko"])):
        label = f["home"] + " v " + f["away"]
        if as_of is not None and utc(f["ko"]) <= as_of:
            result.append(label + " · scheduled kickoff passed before delivery.")
            continue
        if "screen" not in f or f.get("gap"):
            result.append(label + " · " + f.get("gap","fixture screened; reserve for player research"))
            continue
        result.append(label + " · " + f["screen"])
        for c in f["cases"]:
            q, own, opp = c["booking"], c["committed"], c["drawn"]
            odds = f"{q['odds']:.2f} {q['book']}" if q else "odds unavailable"
            sample = c["groups"].get("In this competition")
            row = f"{c['verdict']} · {c['name']} · {c['lineup']} {c['player'].get('position') or 'starter'} · {odds}."
            if q:
                row += f" Odds age {q['age']:g} min at check."
            if sample:
                row += f" Booked in {sample[0]}/{sample[1]} league starts."
            if own:
                row += f" Committed {own['total']} fouls in {own['minutes']} min."
                if all(k in own["hits"] for k in ("1+","2+","3+")):
                    row += " Reached 1+/2+/3+ in " + "/".join(str(own["hits"][k]) for k in ("1+","2+","3+")) + f" of {own['starts']} starts."
            if opp:
                row += f" {c['rival']['name']} drew {opp['total']} in {opp['minutes']} min."
            else:
                row += " Direct opponent or fouls-drawn sample unverified."
            foul = [f"{int(o['line']+0.5)}+ at {o['odds']:.2f} {o['book']}" for o in c["offers"] if o["kind"]=="fouls"]
            if foul:
                row += " Fouls " + ", ".join(foul) + "."
            row += " Fouls verdict " + c["foulsVerdict"] + "."
            row += " " + c["reason"]
            result.append(row)
    if not report["slate"] and complete==len(calendar):
        result.append("No upcoming matches in the covered competitions before the next edition.")
    for l in calendar:
        if l["gap"]:
            result.append(l["league"] + " · " + l["gap"])
    if report["failures"]:
        result.append(f"{report['failures']} data checks unavailable.")
    return result


def publish(store, report):
    key = report["day"]
    rows = lines(report, as_of=utc(timestamp()))
    index = store.get(REPORT)
    if not isinstance(index, dict) or not isinstance(index.get("days"), dict):
        raise RuntimeError("Private Admin index unavailable")
    old = index["days"].get(key)
    if old and old.get("policy")!="johnny-bookings":
        raise RuntimeError("Existing report for the day belongs to another policy")
    index["days"][key] = dict(at=report["at"],policy="johnny-bookings",fixtures=len(report["slate"]),
                               picks=[],coverage="\n".join(rows[1:]),final=all(not x["gap"] for x in report["calendar"]))
    index.update(updated=report["at"],status="Johnny's daily booking and fouls scan · 11am London",
                 summary="Morning research. Predicted starters, unverified odds and missing evidence are labelled. No ticket is assumed placed.")
    store.put(REPORT,index)
    ordered = rows[:2] + [row for row in rows[2:] if row.startswith("BET · ")] + [row for row in rows[2:] if not row.startswith("BET · ")]
    summary = []
    for row in ordered:
        if sum(len(s)+1 for s in summary) + len(row) > 3650:
            break
        summary.append(row)
    if len(summary)<len(ordered):
        summary.append("More cases and coverage notes in the private report.")
    message = "\n".join(summary)+"\nFull private report "+LINK
    receipt_key = "receipts/johnny-"+key+"-0.json"
    receipt = store.get(receipt_key, {})
    if receipt.get("state") == "sent" and receipt.get("message_id"):
        endpoint, chat = telegram_private()
        response = http.post(endpoint+"/editMessageText", json=dict(chat_id=chat,
                      message_id=receipt["message_id"], text=message,
                      link_preview_options={"is_disabled":True}), timeout=20)
        if not response.ok and not (response.status_code==400 and "message is not modified" in response.text.lower()):
            raise RuntimeError(f"Could not update existing private digest (HTTP {response.status_code})")
    else:
        send_digest(store, "johnny-"+key, [message])
    store.put("johnny/confirmed-expanded/"+key+".json", {"reportedAt":report["at"]})


def plan():
    preview = os.environ.get("MODE","preview")=="preview"
    now = datetime.now(LONDON)
    day = (os.environ.get("PREVIEW_DAY","").strip() if preview else "") or now.date().isoformat()
    store = private_store()
    prior = {} if preview else store.get(edition_key(day,"research"), {})
    active = preview or (8 <= now.hour < 11 and prior.get("stage") != "finished")
    needs_engine = False
    if active:
        reader = Reads(store,Provider(store),day,"johnny-preview" if preview else "johnny",212)
        if prior.get("stage") == "ranked":
            needs_engine = any(f.get("reviewState") == "selected" for f in prior["slate"])
        else:
            games, windows = calendar(reader, day, now)
            needs_engine = bool(games or any(w["gap"] for w in windows)) or preview
    with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as output:
        print("active="+str(active).lower(),file=output)
        print("engine="+str(needs_engine).lower(),file=output)


def run():
    now = datetime.now(LONDON)
    preview = os.environ.get("MODE","preview")=="preview"
    day = os.environ.get("PREVIEW_DAY","").strip() if preview else ""
    day = day or now.date().isoformat()
    if not preview and not 8 <= now.hour < 11:
        return
    store = private_store()
    path = edition_key(day,"research")
    prior = None if preview else store.get(path)
    if preview or not prior or prior.get("stage") != "finished":
        phase = "johnny-preview" if preview else "johnny"
        reader = Reads(store,Provider(store),day,phase,212)
        from johnny_cards_review import Analyst
        with Analyst(store) as analyst:
            report = scan(reader,day,analyst,previous=prior,
                          save=None if preview else lambda doc: store.put(path,doc))
            report["guideSHA256"] = analyst.digest
            if preview:
                test = analyst.ask("Rehearsal only. A fictitious player's standard booking single is 3.00 decimal. The projected opposing winger drew nine fouls in 640 minutes. No fouls odds or operator rules were supplied. Using the full guide, identify the booking decision at this price, and whether a separate profitable fouls bet can already be recommended. Copy only the verified fouls-drawn numerator and minutes.",
                     {}, {"type":"object","properties":{"booking":{"type":"string","enum":["BET","WATCH","PASS"]},"foulsBet":{"type":"boolean"},"foulsDrawn":{"type":"integer"},"minutes":{"type":"integer"}},"required":["booking","foulsBet","foulsDrawn","minutes"],"additionalProperties":False},150)
                if test!={"booking":"PASS","foulsBet":False,"foulsDrawn":9,"minutes":640}:
                    raise RuntimeError("Full-prompt rehearsal failed the price-floor or fouls-evidence check")
                report["syntheticCheckPassed"] = True
            report["promptCalls"] = analyst.calls
        if preview:
            store.put("johnny/rehearsals/"+day+".json",report)
        else:
            store.put(path,report)
    else:
        report = prior
    print(f"Calendar windows {sum(not r['gap'] for r in report['calendar'])}/{len(report['calendar'])}; upcoming {len(report['slate'])}; detailed {sum('screen' in f for f in report['slate'])}; reads {report['reads']}; unavailable {report['failures']}; full-prompt calls {report['promptCalls']}; original guide SHA256 {report['guideSHA256']}")


if __name__=="__main__":
    if "--calendar" in sys.argv:
        now = datetime.now(LONDON)
        day = now.date().isoformat()
        store = private_store()
        reader = Reads(store, Provider(store), day, "johnny-calendar-check", 32)
        matches, windows = calendar(reader, day, now)
        print(f"{len(matches)} eligible fixtures; {sum(not w['gap'] for w in windows)}/{len(windows)} calendar windows verified")
        from collections import Counter
        for league, count in sorted(Counter(f["league"] for f in matches).items()):
            print(f"{league}: {count}")
        if not windows or any(w["gap"] for w in windows):
            raise RuntimeError("Incomplete fixture calendar rehearsal")
    elif "--plan" in sys.argv:
        plan()
    else:
        run()
