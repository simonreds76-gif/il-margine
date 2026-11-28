"""List the leading foul committers in upcoming matches assigned to high-booking referees."""
import argparse
import json
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite, sqrt
import os
import re
from time import monotonic, sleep
from zoneinfo import ZoneInfo

import requests
from johnny_cards_calendar import CLOSED, ROW, senior_fixture
from statshub_daily_contracts import LEAGUES, identity, norm
from statshub_daily_io import Provider, RemoteError, Store, http, payload, telegram_private

UK = ZoneInfo("Europe/London")
UTC = timezone.utc
MIN_REF_GAMES = 10
MIN_YELLOWS = 4.0
MIN_MINUTES = 270
PREFIX = "referee-bookings/v1"
SCREEN_VERSION = 2


class Missing(Exception):
    """One fixture or data source could not be verified."""


class Reads:
    def __init__(self, api, max_reads=220, seconds=1200):
        self.api = api
        self.calls = 0
        self.max_reads = max_reads
        self.deadline = monotonic() + seconds
        self.stopped = None
        self.by_tool = Counter()

    def read(self, name, **args):
        if self.stopped or self.calls >= self.max_reads or monotonic() >= self.deadline:
            raise Missing(self.stopped or "scan budget reached")
        self.calls += 1
        self.by_tool[name] += 1
        try:
            doc = self.api.read(name, args)
        except RemoteError as exc:
            if exc.status_code in (401, 403, 429):
                self.stopped = f"provider HTTP {exc.status_code}"
            raise Missing(self.stopped or f"{name} unavailable (HTTP {exc.status_code})") from None
        except (RuntimeError, ValueError, requests.RequestException, StopIteration) as exc:
            raise Missing(f"{name} unavailable ({type(exc).__name__})") from None
        if not isinstance(doc, dict):
            raise Missing(f"{name} did not return an object")
        if doc.get("error"):
            description = str(doc["error"]).lower()
            if any(term in description for term in ("rate limit", "quota exceeded", "daily limit", "too many requests")):
                self.stopped = "provider allowance reached"
            raise Missing(self.stopped or f"{name} returned an error")
        return doc


def edition_window(day):
    start = datetime.combine(day, time(9), UK)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def league_calendar(reader, league, cid, day):
    midnight = datetime.combine(day, time(), UTC)
    for args in ({"date":str(day)}, {"startOfDay":int(midnight.timestamp()),
                                     "endOfDay":int((midnight + timedelta(days=1)).timestamp())}):
        try:
            board = reader.read("getFixturesByDate", competitionId=cid, timeZone="UTC", **args)
            games = []
            seen = set()
            for line in board.get("fixturesSummary", "").splitlines():
                if "[competitionId " in line:
                    group = re.search(r"\[competitionId ([\w.-]+)\]", line)
                    if not group or identity(group[1]) != identity(cid):
                        raise Missing("calendar returned another competition")
                elif line.startswith("- "):
                    m = ROW.match(line)
                    if not m or identity(m[4]) in seen:
                        raise Missing("calendar row incomplete or duplicated")
                    seen.add(identity(m[4]))
                    if CLOSED.search(line):
                        continue
                    ko = datetime.fromisoformat(f"{day}T{m[1]}:00+00:00")
                    lineup = re.search(r"\| lineups (confirmed|predicted|none)\b", line, re.I)
                    games.append(dict(id=m[4], home=m[2], away=m[3], ko=ko.isoformat(),
                                      league=league, competitionId=cid, core=True,
                                      calendarLineup=lineup[1].lower() if lineup else None))
            if len(seen) != board.get("fixtureCount"):
                raise Missing("calendar count mismatch")
            return games
        except Missing:
            if "date" not in args:
                raise


def discover(reader, start, end):
    games, gaps = {}, []
    for league, (cid, _) in LEAGUES.items():
        for day in dict.fromkeys([start.date(), end.date()]):
            try:
                for f in league_calendar(reader, league, cid, day):
                    if start <= datetime.fromisoformat(f["ko"]) < end:
                        games[identity(f["id"])] = f
            except Missing as exc:
                gaps.append(f"{league} {day}: {exc}")

    # The worldwide index covers each assigned referee's next advertised game.
    # An absent competition or a missing appointment is never a negative screen.
    page = 1
    while True:
        try:
            doc = reader.read("getRefereesList", upcomingFixturesOnly=True, last20GamesOnly=True,
                              sortField="next_game_timestamp", sortDirection="asc", minGames=0, limit=30, page=page)
            pagination = doc.get("pagination", {})
            if pagination.get("page") != page or not isinstance(doc.get("data"), list):
                raise Missing("assignment index incomplete")
            past_window = False
            for ref in doc["data"]:
                m = re.fullmatch(r"(.+?) v (.+) \((.+)\), (\w{3} \d{1,2} \w{3} \d{4}, \d\d:\d\d) UTC", ref.get("nextGame") or "")
                if not m or not ref.get("nextMatchId"):
                    gaps.append("worldwide assignment without a usable fixture or start")
                    continue
                ko = datetime.strptime(m[4], "%a %d %b %Y, %H:%M").replace(tzinfo=UTC)
                past_window |= ko >= end
                if start <= ko < end:
                    f = dict(id=ref["nextMatchId"], home=m[1], away=m[2], league=m[3],
                             ko=ko.isoformat(), core=False, indexYellows=ref.get("yellowsPerGame"))
                    if senior_fixture(f):
                        existing = games.setdefault(identity(f["id"]), f)
                        if existing["ko"] == f["ko"] and all(norm(existing[s]) == norm(f[s]) for s in ("home","away")):
                            existing["indexYellows"] = ref.get("yellowsPerGame")
                            if ref.get("id") and ref.get("name"):
                                previous = existing.get("appointment")
                                record = {"id":ref["id"], "name":ref["name"]}
                                if previous and previous != record:
                                    existing["appointmentConflict"] = True
                                existing["appointment"] = record
            if past_window or not pagination.get("hasNextPage"):
                break
            if not doc["data"]:
                raise Missing("empty assignment page")
            page += 1
        except (Missing, ValueError) as exc:
            gaps.append(f"worldwide appointments page {page}: {exc}")
            break
    return sorted(games.values(), key=lambda f:(not f["core"], -(f.get("indexYellows") or 0), f["ko"], f["id"])), gaps


def referee_sample(reader, ref, day):
    cutoff = day - timedelta(days=365)
    low, high, n, best = 0, 51, 50, None
    inside, outside = day, None
    interpolated = False
    while high-low > 1:
        doc = reader.read("getReferee", refereeId=ref["id"], recentGames=n)
        profile = doc.get("profile", {}).get("data", {})
        recent = doc.get("record", {}).get("recentGames", {})
        totals = recent.get("totals", {})
        games, yellows = totals.get("games"), totals.get("yellowCards")
        if identity(profile.get("id")) != identity(ref["id"]) or type(games) is not int or not 0 <= games <= n:
            raise Missing("referee sample unavailable")
        if not games:
            break
        dates = re.search(r"(\d{4}-\d\d-\d\d) to (\d{4}-\d\d-\d\d)", recent.get("context",""))
        if dates:
            first, last = map(date.fromisoformat, dates.groups())
        else:
            rows = recent.get("games", [])
            if len(rows) != games or any(not v.get("kickoff") for v in rows):
                raise Missing("referee sample dates unavailable")
            first, last = min(date.fromisoformat(v["kickoff"][:10]) for v in rows), max(date.fromisoformat(v["kickoff"][:10]) for v in rows)
        if last > day or first > last or type(yellows) is not int or yellows < 0:
            raise Missing("referee sample inconsistent")
        # Where the published newest games cross the cutoff, the dated rows
        # determine the entire in-window sample in one read.
        rows = recent.get("games") or []
        dated = [(date.fromisoformat(r["kickoff"][:10]), r.get("yellowCards"), r.get("matchId"))
                 for r in rows if isinstance(r, dict) and r.get("kickoff")]
        if (first < cutoff and len(dated) == len(rows) and dated and dated[0][0] == last
                and len({r[2] for r in dated}) == len(dated) and all(r[2] for r in dated)
                and all(type(r[1]) is int and r[1]>=0 for r in dated)
                and all(a[0]>=b[0] for a,b in zip(dated,dated[1:])) and dated[-1][0] < cutoff
                and (len(rows)==games or "newest" in recent.get("context","").lower())):
            kept = [r for r in dated if r[0]>=cutoff]
            if not kept:
                return None
            count=sum(r[1] for r in kept)
            return dict(games=len(kept),yellows=count,mean=count/len(kept),
                        first=str(kept[-1][0]),last=str(kept[0][0]),capped=False)
        if first >= cutoff:
            best = dict(games=games, yellows=yellows, mean=yellows/games, first=str(first), last=str(last), capped=games==50)
            low = n
            inside = first
            if n == 50:
                break
        else:
            high = min(n, games)
            outside = first
        if high-low > 1 and outside and inside > outside and not interpolated:
            # Dates choose the next probe only. Every accepted total comes
            # from verified dates and the adjacent out-of-window boundary.
            estimate = low + round((high-low)*(inside-cutoff).days/(inside-outside).days)
            n = max(low+1,min(high-1,estimate))
            interpolated = True
        else:
            n = (low+high)//2
    return best


def rank_players(reader, f, details, teams):
    xi = reader.read("getLineups", matchId=f["id"]).get("lineups") or {}
    if not xi.get("available") or identity(xi.get("matchId")) != identity(f["id"]):
        raise Missing("expected or confirmed lineups unavailable")
    ranked = []
    for side in ("home", "away"):
        lineup, team = xi.get(side) or {}, teams[side]
        starters = {identity(p.get("id")):p for p in lineup.get("players", []) if p.get("id")}
        if (identity(lineup.get("teamId")) != identity(team["id"]) or len(starters) != 11
                or lineup.get("status") not in ("confirmed","predicted")):
            raise Missing("incomplete expected or confirmed XI")
        params = dict(stageId=details["competition"]["stageId"], seasonId=details["matches"]["seasonId"],
                      teamId=team["id"], stat="fouls", rankBy="perGame", minMinutes=MIN_MINUTES, minAppearances=3, limit=35)
        doc = reader.read("getTopStatLeaders", **params)
        filters = doc.get("filtersApplied") or {}
        if (filters.get("stat") != "fouls" or identity(filters.get("teamId")) != identity(team["id"])
                or identity(filters.get("seasonId")) != identity(params["seasonId"]) or not isinstance(doc.get("data"),list)):
            raise Missing("team foul history unverified")
        side_rows = []
        for p in doc["data"]:
            starter = starters.get(identity(p.get("playerId")))
            if not starter or identity(p.get("teamId")) != identity(team["id"]):
                continue
            minutes, apps, count = p.get("minutesPlayed"), p.get("appearances"), p.get("statValue")
            if not all(type(v) is int for v in (minutes, apps, count)) or minutes < MIN_MINUTES or apps < 3 or count < 0:
                continue
            side_rows.append(dict(id=p["playerId"], player=p["playerName"], team=team["name"], side=side,
                                  lineup=lineup["status"], fouls=count, apps=apps, minutes=minutes,
                                  perGame=count/apps, per90=90*count/minutes))
        if not side_rows:
            raise Missing("no eligible foul history on one side")
        ranked.extend(side_rows)
    return sorted(ranked, key=lambda p:(-p["perGame"], -p["per90"], -p["minutes"], p["id"]))[:3], len(ranked)


def exact_fixture(f, data):
    m = data.get("matches") or {}
    start = datetime.fromisoformat(f["ko"])
    return (identity(m.get("id")) == identity(f["id"]) and m.get("status") == "scheduled"
            and m.get("kickoffTimestamp") == int(start.timestamp())
            and (not f.get("competitionId") or identity(data.get("competition",{}).get("competitionId")) == identity(f["competitionId"]))
            and all(data.get(s+"Team",{}).get("id") and norm(data[s+"Team"]["name"]) == norm(f[s]) for s in ("home","away")))


def match_context(reader, f):
    data = reader.read("getMatchDetails", matchId=f["id"]).get("data") or {}
    if not exact_fixture(f,data):
        raise Missing("fixture identity, kickoff or pre-match status unverified")
    ref = data.get("referees") or {}
    if not ref.get("id"):
        raise Missing("no assigned referee")
    return data, ref


def matching_fixture(a, b):
    return (identity(a.get("id")) == identity(b.get("id")) and a["ko"] == b["ko"]
            and all(norm(a[s]) == norm(b[s]) for s in ("home","away")))


class RefereeReads:
    """Reuse a referee response between the full-slate pass and exact date checks."""
    def __init__(self, reader):
        self.reader = reader
        self.responses = {}

    def read(self, name, refereeId, recentGames):
        key = (identity(refereeId), recentGames)
        if key not in self.responses:
            self.responses[key] = self.reader.read(name, refereeId=refereeId, recentGames=recentGames)
        return self.responses[key]


class NeedsDates(Exception):
    pass


def saved_only(cache):
    class Saved:
        def read(self, name, refereeId, recentGames):
            key = (identity(refereeId), recentGames)
            if key not in cache.responses:
                raise NeedsDates
            return cache.responses[key]
    return Saved()


def screen(reader, day, preview=False, previous=None, checkpoint=None, resume=None):
    now = datetime.now(UTC)
    if resume:
        reader.calls = resume["reads"]
        reader.by_tool.update(resume["readsByTool"])
        return finish_screen(reader,day,preview,resume["fixtures"],resume["calendarGaps"],{},
                             resume["started"],checkpoint,resume["stage"])
    start, end = edition_window(day)
    fixtures, gaps = discover(reader, start, end)
    if preview:
        # Exercise both calendar routes without consuming a weekend's full allowance.
        fixtures = [f for core in (True, False) for f in [g for g in fixtures if g["core"] == core][:2]]
    old = {identity(f["id"]):f for f in (previous or {}).get("fixtures",[])}
    discovered = {identity(f["id"]) for f in fixtures}
    for key, prior in old.items():
        if key not in discovered:
            fixtures.append(dict(prior, status="absent from current fixture list", carried=True))
    contexts, refine, qualified = {}, [], []
    cache = RefereeReads(reader)
    def classify(f, ref_reader):
        sample = f["refSample"] = referee_sample(ref_reader, f["appointment"], day)
        if not sample or sample["games"] < MIN_REF_GAMES:
            return "insufficient dated referee history"
        return "below referee threshold" if sample["mean"] < MIN_YELLOWS else "qualified referee"

    def record_status(f, status):
        f["status"] = status
        if status == "qualified referee":
            qualified.append(f)

    for f in fixtures:
        try:
            if f.get("carried"):
                continue
            if datetime.fromisoformat(f["ko"]) <= now:
                raise Missing("kickoff passed")
            key = identity(f["id"])
            if not f.get("appointment") or f.get("appointmentConflict"):
                data, ref = match_context(reader,f)
                contexts[key], f["appointment"] = data, ref
            ref = f["appointment"]
            f["referee"] = ref["name"]
            prior = old.get(key)
            if prior and matching_fixture(prior,f) and norm(prior.get("referee","")) == norm(ref["name"]) and (
                    not prior.get("appointment") or identity(prior["appointment"]["id"]) == identity(ref["id"])):
                sample = prior.get("refSample")
                if sample:
                    f["refSample"] = sample
                    if prior["status"] == "reviewed":
                        f.update(status="reviewed", players=prior["players"], eligibleStarters=prior.get("eligibleStarters",0))
                        continue
                    if sample["games"] < MIN_REF_GAMES or sample["mean"] < MIN_YELLOWS:
                        record_status(f, "insufficient dated referee history" if sample["games"] < MIN_REF_GAMES else "below referee threshold")
                        continue
                    record_status(f,"qualified referee")
                    continue
            cache.read("getReferee", refereeId=ref["id"], recentGames=50)
            try:
                record_status(f, classify(f,saved_only(cache)))
            except NeedsDates:
                f["status"] = "referee dates need verification"
                refine.append(f)
        except Missing as exc:
            f["status"] = str(exc)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError):
            f["status"] = "unexpected fixture data format"

    # Give the already-qualified games enough remaining reads for a fixture
    # identity check, both elevens, and one team-level foul table per side.
    def reserve():
        existing = sum(len(f.get("players",[])) for f in fixtures if f.get("status")=="reviewed")
        return existing + (existing+11)//12 + sum(7 if identity(f["id"]) in contexts else 8 for f in qualified)
    for f in refine:
        if reader.max_reads - reader.calls <= reserve():
            break
        try:
            record_status(f,classify(f,cache))
        except (Missing, ValueError, KeyError, TypeError) as exc:
            f["status"] = str(exc) if isinstance(exc,Missing) else "referee history format unavailable"

    return finish_screen(reader,day,preview,fixtures,gaps,contexts,now.isoformat(),checkpoint)


def finish_screen(reader,day,preview,fixtures,gaps,contexts,started,checkpoint,stage=None):
    def snapshot(stage):
        report=dict(day=str(day),preview=preview,screenVersion=SCREEN_VERSION,started=started,
                    fixtures=fixtures,calendarGaps=gaps,reads=reader.calls,readsByTool=dict(reader.by_tool),stage=stage)
        if checkpoint:
            checkpoint(stage,report)
        return report

    if stage is None:
        snapshot("referees")
    qualified=[f for f in fixtures if f.get("status")=="qualified referee" and stage!="players"]
    for f in sorted(qualified,key=lambda f:(not f["core"],f.get("calendarLineup")=="none",-(f.get("indexYellows") or 0),f["ko"])):
        try:
            if datetime.fromisoformat(f["ko"]) <= datetime.now(UTC):
                raise Missing("kickoff passed")
            data = contexts.get(identity(f["id"]))
            if data is None:
                data,ref = match_context(reader,f)
                if identity(ref["id"]) != identity(f["appointment"]["id"]):
                    f.pop("refSample",None)
                    raise Missing("referee appointment changed")
            teams = {s:data[s+"Team"] for s in ("home","away")}
            players,count = rank_players(reader,f,data,teams)
            f.update(players=players,eligibleStarters=count,status="reviewed")
        except (Missing, KeyError, TypeError, ValueError) as exc:
            f["status"] = str(exc) if isinstance(exc,Missing) else "player evidence format unavailable"
    if stage!="players":
        snapshot("players")
    check_cards(reader,fixtures)
    return dict(day=str(day),preview=preview,screenVersion=SCREEN_VERSION,started=started,
                completed=datetime.now(UTC).isoformat(),fixtures=fixtures,calendarGaps=gaps,
                reads=reader.calls,readsByTool=dict(reader.by_tool))


def use_remaining(reader,report):
    """Reclaim unused player lookups when lineups or foul records were unavailable."""
    reader.calls=report["reads"]
    reader.by_tool.update(report["readsByTool"])
    fixtures=report["fixtures"]
    now=datetime.now(UTC)
    for f in fixtures:
        if datetime.fromisoformat(f["ko"])<=now or f["status"]!="reviewed":
            continue
        for p in f["players"]:
            if not p.get("cards") and "unavailable" in p.get("historyStatus",""):
                try:
                    p["cards"]=card_record(reader,p,now)
                    p.pop("historyStatus",None)
                    p["cardAssessment"]=assess_card(p["cards"],p.get("cardPrice"))
                except (Missing,KeyError,TypeError,ValueError):
                    pass

    pending=[f for f in fixtures if f.get("status") in ("referee dates need verification","getReferee unavailable (HTTP 502)")
             and f.get("appointment") and datetime.fromisoformat(f["ko"])>now]
    cache=RefereeReads(reader)
    while pending and reader.max_reads-reader.calls>=8 and not reader.stopped:
        ready=[]
        while pending and reader.max_reads-reader.calls>=8*(len(ready)+1) and not reader.stopped:
            f=pending.pop(0)
            try:
                sample=f["refSample"]=referee_sample(cache,f["appointment"],date.fromisoformat(report["day"]))
                if not sample or sample["games"]<MIN_REF_GAMES:
                    f["status"]="insufficient dated referee history"
                elif sample["mean"]<MIN_YELLOWS:
                    f["status"]="below referee threshold"
                else:
                    f["status"]="qualified referee"
                    ready.append(f)
            except (Missing,ValueError,KeyError,TypeError) as exc:
                f["status"]=str(exc) if isinstance(exc,Missing) else "referee history format unavailable"
        if ready:
            # Only newly qualified fixtures enter the player and card checks.
            finish_screen(reader,date.fromisoformat(report["day"]),report["preview"],ready,[],{},report["started"],None,"referees")
    report.update(remainingChecked=True,reads=reader.calls,readsByTool=dict(reader.by_tool),completed=datetime.now(UTC).isoformat())
    return report


def booking_odds(reader, batch):
    prices = {}
    page = 1
    wanted = {(identity(f["id"]), identity(p["id"])):(f,p) for f,p in batch}
    while True:
        doc = reader.read("getPropScreener", games=list(dict.fromkeys(f["id"] for f,p in batch)),
                          players=list(dict.fromkeys(p["id"] for f,p in batch)), statTypes=["yellowCards"],
                          type="over", hitRateFrom=0, hitRateTo=100, oddsFrom=1.01, oddsTo=1000,
                          includeStale=False, useSupersub=False, lineupFilterType="predicted", pageSize=40, page=page)
        info=doc.get("pagination",{})
        if info.get("currentPage")!=page or not isinstance(doc.get("data"),list):
            raise Missing("booking odds response incomplete")
        for item in doc["data"]:
            row={**(doc.get("everyRow") or {}),**item}
            key=identity(row.get("matchId")),identity(row.get("playerId"))
            if key not in wanted or (row.get("statType"),row.get("oddsType"),row.get("line"))!=("yellowCards","over",0.5):
                continue
            f,p=wanted[key]
            if (norm(row.get("teamName",""))!=norm(p["team"]) or norm(row.get("playerName",""))!=norm(p["player"])
                    or (row.get("inPredictedLineup") is False and not row.get("inConfirmedLineup"))):
                continue
            odds,book=row.get("bestOdds"),row.get("bestBookmakerName")
            if type(odds) in (float,int) and isfinite(odds) and odds>1 and isinstance(book,str) and book.strip():
                if key not in prices or odds>prices[key]["odds"]:
                    prices[key]=dict(odds=odds,book=book,observed=datetime.now(UTC).isoformat())
        if info.get("hasNextPage") is False:
            return prices
        if info.get("hasNextPage") is not True or not doc["data"] or page>=5:
            raise Missing("booking odds pagination incomplete")
        page+=1


def card_record(reader,p,now):
    doc=reader.read("getPlayerStats",playerId=p["id"],statType="yellowCards",line=0.5,
                    appearances="played",clubOnly=True,limit=20)
    stat=doc.get("requestedStat",{})
    games=doc.get("games")
    cols=doc.get("matchColumns",[])
    rows=[dict(zip(cols,r)) for r in doc.get("matchRows",[]) if len(r)==len(cols)]
    if (stat.get("statType")!="yellowCards" or type(games) is not int or not 0<games<=20
            or len(rows)!=games or len({r.get("matchId") for r in rows if r.get("matchId")})!=games
            or any(not r.get("date") or date.fromisoformat(r["date"])>=now.date()
                   or type(r.get("yellowCards")) is not int or r["yellowCards"]<0
                   or type(r.get("started")) is not bool or not (r.get("minutes") or 0)>0 for r in rows)):
        raise Missing("dated yellow-card appearances unavailable")
    hits=sum(r["yellowCards"]>0 for r in rows)
    cards=sum(r["yellowCards"] for r in rows)
    if (cards!=stat.get("total") or hits!=stat.get("overLine",{}).get("over")
            or stat.get("overLine",{}).get("line")!=0.5):
        raise Missing("yellow-card totals disagree")
    starts=[r for r in rows if r["started"]]
    return dict(games=games,cards=cards,booked=hits,perAppearance=cards/games,
                starts=len(starts),bookedStarts=sum(r["yellowCards"]>0 for r in starts))


def assess_card(record,price):
    if not record or not price:
        return "incomplete"
    n,h=record["games"],record["booked"]
    if n<10 or record["starts"]<5:
        return "small sample"
    p=h/n
    required=1/price["odds"]
    if min(p,record["bookedStarts"]/record["starts"]) <= required:
        return "record below or level with odds"
    # One-sided 90% Wilson bound on the observed booking frequency.
    z=1.281552
    lower=(p+z*z/(2*n)-z*sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
    return "possible value" if lower>required else "uncertain edge"


def check_cards(reader,fixtures):
    candidates=[(f,p) for f in fixtures if f.get("status")=="reviewed" and datetime.fromisoformat(f["ko"])>datetime.now(UTC)
                for p in f["players"]]
    # When coverage runs out, start with the strongest foul records.
    candidates.sort(key=lambda row:(-row[1]["perGame"],row[0]["ko"],row[1]["id"]))
    for start in range(0,len(candidates),12):
        batch=candidates[start:start+12]
        try:
            prices=booking_odds(reader,batch)
            missing_price="no fresh booking odds listed"
        except (Missing,KeyError,TypeError,ValueError) as exc:
            prices={}
            missing_price=str(exc) if isinstance(exc,Missing) else "booking odds incomplete"
        for f,p in batch:
            p["cardPrice"]=prices.get((identity(f["id"]),identity(p["id"])))
            p["priceStatus"]="checked" if p["cardPrice"] else missing_price
    for f,p in candidates:
        try:
            p["cards"]=card_record(reader,p,datetime.now(UTC))
        except (Missing,KeyError,TypeError,ValueError) as exc:
            p["cards"]=None
            p["historyStatus"]=str(exc) if isinstance(exc,Missing) else "yellow-card history incomplete"
        p["cardAssessment"]=assess_card(p["cards"],p["cardPrice"])


def shortlist(report,now):
    pairs=[(p,f) for f in report["fixtures"] if f.get("status")=="reviewed" and datetime.fromisoformat(f["ko"])>now
           for p in f.get("players",[])]
    if report.get("screenVersion",1)<2:
        return sorted(pairs,key=lambda x:(-x[0]["perGame"],-x[0]["per90"],-x[0]["minutes"],x[1]["ko"],x[0]["id"]))[:3]
    return sorted((x for x in pairs if x[0].get("cardAssessment")=="possible value"),
                  key=lambda x:(-(x[0]["cards"]["booked"]/x[0]["cards"]["games"]-1/x[0]["cardPrice"]["odds"]),
                                -x[0]["perGame"],x[1]["ko"],x[0]["id"]))[:3]


def digest(report, now):
    leaders = []
    statuses = Counter()
    details = []
    for fixture in report["fixtures"]:
        kickoff = datetime.fromisoformat(fixture["ko"])
        statuses[fixture["status"]] += 1
        details.extend(["", f"{kickoff.astimezone(UK):%a %H:%M UK} · {fixture['league']} · "
                        f"{fixture['home']} v {fixture['away']}", fixture["status"]])
        sample = fixture.get("refSample")
        if sample:
            details.append(f"{fixture['referee']} · {sample['yellows']} yellows in {sample['games']} matches "
                           f"({sample['mean']:.2f}/match), {sample['first']} to {sample['last']}")
        if "eligibleStarters" in fixture:
            details.append(f"{fixture['eligibleStarters']}/22 starters with qualifying foul records")
        if fixture["status"] != "reviewed":
            continue
        for player in fixture["players"]:
            if kickoff > now:
                leaders.append((player, fixture))
            details.append(f"  {player['player']} ({player['team']}, {player['lineup']} XI) · "
                           f"{player['fouls']} fouls committed in {player['apps']} appearances · "
                           f"{player['perGame']:.2f}/appearance · {player['per90']:.2f}/90 · {player['minutes']} min")

    leaders.sort(key=lambda entry: (-entry[0]["perGame"], -entry[0]["per90"], -entry[0]["minutes"],
                                    entry[1]["ko"], entry[0]["id"]))
    current = report.get("screenVersion",1)>=2
    title = f"{'Player booking watch' if current else 'Player foul watch'} · {date.fromisoformat(report['day']):%a %d %b}"
    if report["preview"]:
        title += " · rehearsal"
    reviewed = statuses["reviewed"]
    below = statuses["below referee threshold"]
    missing = len(report["fixtures"]) - reviewed - below
    coverage = f"{reviewed} matches reviewed · {below} below referee cutoff · {missing} incomplete"
    caption = [title, coverage]
    if report["calendarGaps"]:
        caption.append("Calendar coverage incomplete.")
    if current:
        selected = shortlist(report,now)
        checked = sum(bool(p.get("cards") and p.get("cardPrice")) for p,_ in leaders)
        caption.append(f"{checked}/{len(leaders)} foul leaders with yellow-card history and odds.")
        for p,f in selected:
            c,price=p["cards"],p["cardPrice"]
            caption.extend(["",f"{p['player']} to be booked · {price['odds']:.2f} {price['book']}",
                            f"{f['home']} v {f['away']} · {datetime.fromisoformat(f['ko']).astimezone(UK):%H:%M} UK",
                            f"{c['booked']}/{c['games']} booked · {c['perAppearance']:.2f} yellows/app · odds imply {100/price['odds']:.1f}%",
                            f"{p['perGame']:.2f} fouls/app · ref {f['refSample']['mean']:.2f} yellows/game · {p['lineup']} XI"])
        if not selected:
            caption.append("No booking passed the value screen.")
    elif not leaders:
        caption.append("No upcoming player foul leaders with verified data.")
    for player, fixture in ([] if current else leaders[:3]):
        kickoff = datetime.fromisoformat(fixture["ko"]).astimezone(UK)
        sample = fixture["refSample"]
        caption.extend(["", f"{player['player'][:50]} · {player['fouls']} fouls in {player['apps']} appearances "
                        f"({player['perGame']:.2f}/game)",
                        f"{fixture['home'][:28]} v {fixture['away'][:28]} · {kickoff:%H:%M UK} · {player['lineup']} XI",
                        f"Ref {fixture['referee'][:35]} · {sample['mean']:.2f} yellows/game ({sample['games']} games)"])
    caption.append("\nFull match-by-match list attached.")
    if current:
        details.extend(["","Booking prices and player records",
                        "Last 20 club appearances with minutes. A booking is one or more yellows. Odds are the best returned for that player at over 0.5 with stale markets excluded (12-hour provider window).",
                        "Possible value is a historical screen: at least ten appearances, five starts, both booking rates above the odds-implied chance and the one-sided 90% Wilson lower bound for appearances also above it. It is not a calibrated match probability."])
        for p,f in leaders:
            c,price=p.get("cards"),p.get("cardPrice")
            rec=(f"{c['cards']} yellows in {c['games']} appearances ({c['perAppearance']:.2f}/app); "
                 f"booked in {c['booked']}/{c['games']} appearances and {c['bookedStarts']}/{c['starts']} starts"
                 if c else p.get("historyStatus","history unavailable"))
            market=(f"{price['odds']:.2f} {price['book']} ({100/price['odds']:.1f}% implied)" if price else p.get("priceStatus","odds unavailable"))
            details.append(f"{f['home']} v {f['away']} · {p['player']} · {rec} · {market} · {p.get('cardAssessment','unchecked')}")
    body = [title, coverage,
            f"Referee screen: at least {MIN_YELLOWS:.1f} yellow cards per match in {MIN_REF_GAMES}+ dated games "
            "over the past year (up to 50 games, all competitions).",
            f"Up to three likely starters per match, ranked across both teams by season fouls committed per appearance. "
            f"Minimum {MIN_MINUTES} minutes and three appearances. Ties use fouls per 90, then minutes.",
            "Coverage includes the five major domestic leagues and other senior fixtures listed with a referee appointment.",
            "Calendar gaps: " + ("; ".join(report["calendarGaps"]) or "none identified in the checked lists"),
            *details]
    return "\n".join(caption), "\n".join(body)+"\n", len(selected) if current else len(leaders)


def deliver(store, report, now):
    if report["preview"] or date.fromisoformat(report["day"]) != now.astimezone(UK).date():
        raise ValueError("Only today's live edition can be delivered")
    key = f"{PREFIX}/{report['day']}/delivery.json"
    previous = store.get(key)
    if previous and previous.get("state") == "sent":
        original = store.get(f"{PREFIX}/{report['day']}/original.json")
        if not original or original.get("screenVersion",1)==report.get("screenVersion",1):
            return
        selection = lambda rep,at: [[f["id"],p["id"]] for p,f in shortlist(rep,at)]
        before = selection(original,datetime.fromisoformat(previous["at"]))
        after = selection(report,now)
        edit_key=f"{PREFIX}/{report['day']}/booking-amendment.json"
        receipt=store.get(edit_key) or {}
        comparable = any(p.get("cards") and p.get("cardPrice") for f in report["fixtures"] for p in f.get("players",[]))
        displayed=receipt.get("selection",before)
        if (not comparable or displayed==after or
                receipt.get("reportCompleted")==report.get("completed") and receipt.get("state")=="edited"):
            return
        caption,body,_=digest(report,now)
        endpoint,chat=telegram_private()
        mid=previous["message_id"]
        response=http.post(endpoint+"/editMessageMedia",data={"chat_id":chat,"message_id":mid,
            "media":json.dumps({"type":"document","media":"attach://report","caption":caption})},
            files={"report":(f"booking-watch-{report['day']}.txt",body.encode("utf-8"),"text/plain")}, timeout=30)
        msg=payload(response)
        result=msg.get("result") or {}
        if not msg.get("ok") or result.get("message_id")!=mid or str((result.get("chat") or {}).get("id"))!=chat:
            raise RuntimeError("Original digest edit not acknowledged")
        store.put(edit_key,{"state":"edited","selection":after,"at":now.isoformat(),"message_id":mid,
                            "reportCompleted":report.get("completed")})
        return
    caption, body, _ = digest(report, now)
    endpoint, chat = telegram_private()
    if not store.put(key, {"state":"sending", "at":now.isoformat()}, replace=False):
        if store.get(key, {}).get("state") == "sent":
            return
        raise RuntimeError("Uncertain delivery; verify original message before repeating")
    # Keep network retries outside sendDocument: an unacknowledged send may already be visible.
    response = http.post(endpoint+"/sendDocument", data={"chat_id":chat,"caption":caption},
                         files={"document":(f"player-foul-watch-{report['day']}.txt",body.encode("utf-8"),"text/plain")}, timeout=30)
    msg = payload(response)
    if not msg.get("ok") or not msg.get("result",{}).get("message_id"):
        raise RuntimeError("Digest delivery not acknowledged")
    store.put(key, {"state":"sent","at":now.isoformat(),"message_id":msg["result"]["message_id"]})


def save_report(store,key,value,replace=True):
    for attempt in range(3):
        try:
            return store.put(key,value,replace=replace)
        except (requests.Timeout,requests.ConnectionError,RemoteError) as error:
            if isinstance(error,RemoteError) and error.status_code not in (408,429,500,502,503,504):
                raise
            try:
                actual=store.get(key)
            except (requests.Timeout,requests.ConnectionError):
                actual=None
            if actual==value:
                return True
            if actual is not None and not replace:
                return False
            if attempt==2:
                raise
            sleep(1+2*attempt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["scan","deliver","preview"])
    parser.add_argument("--day", type=date.fromisoformat)
    args = parser.parse_args()
    today = datetime.now(UK).date()
    day = args.day or today
    preview = args.mode == "preview"
    if day != today and not preview:
        parser.error("Only a rehearsal accepts a different date")
    folder = f"{PREFIX}/rehearsals/{os.environ.get('GITHUB_RUN_ID','local')}-{os.environ.get('GITHUB_RUN_ATTEMPT','1')}" if preview else PREFIX
    key = f"{folder}/{day}/report.json"
    stage_key=f"{folder}/{day}/booking-v{SCREEN_VERSION}"
    store = Store()
    report = store.get(key)
    final=store.get(stage_key+"-final.json")
    completed=store.get(stage_key+"-complete.json")
    if args.mode == "deliver":
        report=completed or final or report
        if report is None:
            raise RuntimeError("Edition missing from private storage")
        deliver(store, report, datetime.now(UTC))
        print("Private delivery acknowledged")
        return
    upgrade = bool(report and not preview and report.get("screenVersion",1)<SCREEN_VERSION)
    if report is None or upgrade or not report.get("remainingChecked"):
        if upgrade:
            save_report(store,f"{folder}/{day}/original.json",report,replace=False)
        if final is None and completed is None:
            progress=store.get(stage_key+"-players.json") or store.get(stage_key+"-referees.json")
            def checkpoint(name,data):
                save_report(store,stage_key+"-"+name+".json",data,replace=False)
            final=screen(Reads(Provider(store)),day,preview,previous=report,checkpoint=checkpoint,resume=progress)
            if not save_report(store,stage_key+"-final.json",final,replace=False):
                final=store.get(stage_key+"-final.json")
                if not final:
                    raise RuntimeError("Private revision could not be verified")
        if completed is None:
            completed=use_remaining(Reads(Provider(store)),final)
            if not save_report(store,stage_key+"-complete.json",completed,replace=False):
                completed=store.get(stage_key+"-complete.json")
                if not completed:
                    raise RuntimeError("Completed report could not be verified")
        replace=report is not None
        report=completed
        if not save_report(store,key,report,replace=replace):
            report = store.get(key)
    _, _, count = digest(report, datetime.now(UTC))
    statuses = Counter(f["status"] for f in report["fixtures"])
    print(f"Private report saved. Fixtures={len(report['fixtures'])}, reviewed={statuses['reviewed']}, "
          f"below={statuses['below referee threshold']}, upcoming_leaders={count}, calendar gaps={len(report['calendarGaps'])}, reads={report['reads']}")
    if preview and (not report["fixtures"] or not any(f.get("refSample") for f in report["fixtures"])):
        raise RuntimeError("Rehearsal could not verify a dated referee record")


if __name__ == "__main__":
    main()
