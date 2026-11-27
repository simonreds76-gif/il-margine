"""Daily private referee screen. The ranking is a shortlist, not a fitted price model."""
import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import math
import os
import re
from time import monotonic
from zoneinfo import ZoneInfo

import requests
from johnny_cards_calendar import CLOSED, ROW, senior_fixture
from statshub_daily_contracts import LEAGUES, exact_quote, identity, norm, price_floor
from statshub_daily_io import Provider, RemoteError, Store, http, payload, telegram_private

UK = ZoneInfo("Europe/London")
UTC = timezone.utc
MIN_REF_GAMES = 10
MIN_YELLOWS = 4.5
MIN_MINUTES = 270
MAX_AGE = 60
PREFIX = "referee-bookings/v1"


class Missing(Exception):
    """One fixture or data source could not be verified."""


class Reads:
    def __init__(self, api, max_reads=320, seconds=1200):
        self.api = api
        self.calls = 0
        self.max_reads = max_reads
        self.deadline = monotonic() + seconds
        self.stopped = None

    def read(self, name, **args):
        if self.stopped or self.calls >= self.max_reads or monotonic() >= self.deadline:
            raise Missing(self.stopped or "scan budget reached")
        self.calls += 1
        try:
            doc = self.api.read(name, args)
        except RemoteError as exc:
            if exc.status_code in (401, 403, 429):
                self.stopped = f"provider HTTP {exc.status_code}"
            raise Missing(self.stopped or f"{name} unavailable") from None
        except (RuntimeError, ValueError, requests.RequestException, StopIteration):
            raise Missing(f"{name} unavailable") from None
        if not isinstance(doc, dict) or doc.get("error"):
            raise Missing(f"{name} unavailable")
        return doc


def edition_window(day):
    start = datetime.combine(day, time(9), UK)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def discover(reader, start, end):
    games, gaps = {}, []
    for league, (cid, _) in LEAGUES.items():
        for day in dict.fromkeys([start.date(), end.date()]):
            try:
                board = reader.read("getFixturesByDate", date=str(day), competitionId=cid, timeZone="UTC")
                seen = 0
                for line in board.get("fixturesSummary", "").splitlines():
                    m = ROW.match(line)
                    if not m:
                        continue
                    seen += 1
                    ko = datetime.fromisoformat(f"{day}T{m[1]}:00+00:00")
                    if start <= ko < end and not CLOSED.search(line):
                        games[identity(m[4])] = dict(id=m[4], home=m[2], away=m[3], ko=ko.isoformat(),
                                                     league=league, competitionId=cid, core=True)
                if seen != board.get("fixtureCount"):
                    gaps.append(f"{league} {day}: calendar incomplete")
            except Missing as exc:
                gaps.append(f"{league} {day}: {exc}")

    # The worldwide index covers each assigned referee's next advertised game.
    # An absent competition or a missing appointment is never a negative screen.
    page = 1
    while True:
        try:
            doc = reader.read("getRefereesList", upcomingFixturesOnly=True, last20GamesOnly=True,
                              sortField="next_game_timestamp", sortDirection="asc", minGames=0, limit=20, page=page)
            pagination = doc.get("pagination", {})
            if pagination.get("page") != page or not isinstance(doc.get("data"), list):
                raise Missing("assignment index incomplete")
            for ref in doc["data"]:
                m = re.fullmatch(r"(.+?) v (.+) \((.+)\), (\w{3} \d{1,2} \w{3} \d{4}, \d\d:\d\d) UTC", ref.get("nextGame") or "")
                if not m or not ref.get("nextMatchId"):
                    gaps.append("worldwide assignment without a usable fixture or start")
                    continue
                ko = datetime.strptime(m[4], "%a %d %b %Y, %H:%M").replace(tzinfo=UTC)
                if start <= ko < end:
                    f = dict(id=ref["nextMatchId"], home=m[1], away=m[2], league=m[3],
                             ko=ko.isoformat(), core=False, indexYellows=ref.get("yellowsPerGame"))
                    if senior_fixture(f):
                        games.setdefault(identity(f["id"]), f)
            if not pagination.get("hasNextPage"):
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
        if first >= cutoff:
            best = dict(games=games, yellows=yellows, mean=yellows/games, first=str(first), last=str(last), capped=games==50)
            low = n
            if n == 50:
                break
        else:
            high = min(n, games)
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


def assess_players(reader, f, players):
    lookup = dict(matchId=f["id"], markets=["player to be booked"], line=0.5)
    odds = reader.read("getMatchOdds", **lookup)
    observed = datetime.now(UTC)
    ko = datetime.fromisoformat(f["ko"])
    header = odds.get("context","")
    board_ok = (norm(header.split(" · ",1)[0]) == norm(f["home"]+" v "+f["away"])
                and ko.strftime("%d %b %Y, %H:%M UTC").lstrip("0") in header and not CLOSED.search(header.split(" · markets")[0]))
    outcomes = [o for m in odds.get("markets",[]) if m.get("name","").casefold()=="player to be booked" for o in m.get("outcomes",[])] if board_ok else []
    try:
        history = reader.read("checkBet", bets=[dict(matchId=f["id"],playerId=p["id"],statType="yellowCards",line=.5) for p in players])
    except Missing:
        history = {}
    for p in players:
        p["decision"] = "watch"
        rows = [o for o in outcomes if norm(o.get("label","")) == norm(p["player"]+" Over 0.5")
                and re.search(r" over 0\.5$",o.get("label",""),re.I)]
        quote = exact_quote(rows[0], MAX_AGE) if len(rows)==1 else None
        if quote:
            p.update(quote, observed=observed.isoformat(), breakEven=1/quote["odds"])
        evidence = []
        for row in history.get("bets") or ([history["report"]] if isinstance(history.get("report"), dict) else []):
            fixture = row.get("fixture") or {}
            bet = row.get("bet") or {}
            if (norm(row.get("player")) == norm(p["player"]) and fixture.get("kickoffTimestamp")==int(ko.timestamp())
                    and all(norm(fixture.get(s))==norm(f[s]) for s in ("home","away"))
                    and fixture.get("isHome") is (p["side"]=="home")
                    and bet.get("statType")=="yellowCards" and bet.get("line")==.5):
                evidence.append(row)
        samples = [v for row in evidence for v in row.get("samples",[]) if v.get("label")=="Last 20 starts"]
        if len(evidence) != 1 or len(samples)!=1 or len([r for r in players if norm(r["player"])==norm(p["player"])])!=1:
            p["reason"] = "booking history or player identity unverified"
            continue
        sample = samples[0]
        games,hits = sample.get("starts"),sample.get("hits")
        if type(games) is not int or type(hits) is not int or not 0 <= hits <= games or not 10 <= games <= 20:
            p["reason"] = "insufficient booking history"
            continue
        floor = price_floor(hits,games)
        p.update(starts=games,booked=hits,minimum=floor if math.isfinite(floor) else None)
        if not quote:
            p["reason"]="no fresh exact booking odds"
        elif (evidence[0].get("availability") or {}).get("warning"):
            p["reason"]="availability or role warning"
        elif quote["odds"] >= floor:
            p.update(decision="candidate",ratio=quote["odds"]/floor)
        else:
            p["reason"]="odds below screen minimum"


def analyse(reader, f, now, cache):
    if datetime.fromisoformat(f["ko"]) <= now:
        raise Missing("kickoff passed")
    data = reader.read("getMatchDetails", matchId=f["id"]).get("data") or {}
    if not exact_fixture(f,data):
        raise Missing("fixture identity, kickoff or pre-match status unverified")
    ref = data.get("referees") or {}
    if not ref.get("id"):
        raise Missing("no assigned referee")
    f["referee"] = ref["name"]
    if ref["id"] not in cache:
        cache[ref["id"]] = referee_sample(reader,ref,now.date())
    sample = f["refSample"] = cache[ref["id"]]
    if not sample or sample["games"] < MIN_REF_GAMES:
        raise Missing("insufficient dated referee history")
    if sample["mean"] < MIN_YELLOWS:
        return "below referee threshold"
    teams = {s:data[s+"Team"] for s in ("home","away")}
    players, count = rank_players(reader, f, data, teams)
    f.update(players=players, eligibleStarters=count)
    assess_players(reader,f,players)
    return "reviewed"


def screen(reader, day, preview=False):
    now = datetime.now(UTC)
    start, end = edition_window(day)
    fixtures, gaps = discover(reader, start, end)
    if preview:
        # Exercise both calendar routes without consuming a weekend's full allowance.
        fixtures = [f for core in (True, False) for f in [g for g in fixtures if g["core"] == core][:2]]
    cache = {}
    for f in fixtures:
        try:
            f["status"] = analyse(reader, f, datetime.now(UTC), cache)
        except Missing as exc:
            f["status"] = str(exc)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError):
            f["status"] = "unexpected fixture data format"
    return dict(day=str(day), preview=preview, started=now.isoformat(), completed=datetime.now(UTC).isoformat(),
                fixtures=fixtures, calendarGaps=gaps, reads=reader.calls)


def digest(report, now):
    candidates = []
    statuses = Counter()
    player_coverage = Counter()
    detail = []
    for f in report["fixtures"]:
        ko = datetime.fromisoformat(f["ko"])
        title = f"{f['home']} v {f['away']}"
        header = f"{ko.astimezone(UK):%a %H:%M UK} | {f['league']} | {title}"
        statuses[f["status"]] += 1
        detail.extend(["", header, f["status"]])
        sample = f.get("refSample")
        if sample:
            suffix = " (latest 50 only)" if sample["capped"] else ""
            detail.append(f"{f['referee']}: {sample['yellows']} yellows in {sample['games']} matches"
                          f" ({sample['mean']:.2f}/match), {sample['first']} to {sample['last']}{suffix}")
        if "eligibleStarters" in f:
            detail.append(f"{f['eligibleStarters']}/22 starters with eligible foul history")
        for p in f.get("players", []):
            reason = p.get("reason", "incomplete player evidence")
            odds = "odds unavailable"
            if "odds" in p:
                elapsed = max(0, (now-datetime.fromisoformat(p["observed"])).total_seconds()/60)
                age = p["age"] + elapsed
                odds = f"{p['odds']:.2f} {p['book']} ({math.ceil(age)} min old at digest)"
                if p["decision"] == "candidate":
                    if ko <= now:
                        reason = "kickoff passed before delivery"
                    elif age > MAX_AGE:
                        reason = "odds expired before delivery"
                    else:
                        reason = "shortlisted"
                        candidates.append((p, f))
            player_coverage[reason] += 1
            history = f"{p['booked']}/{p['starts']} booked" if "starts" in p else "booking sample unavailable"
            floor = f" | screening minimum {p['minimum']:.2f}" if p.get("minimum") else ""
            detail.append(f"  {p['player']} ({p['lineup']}): {p['fouls']} fouls in {p['apps']} appearances,"
                          f" {p['perGame']:.2f}/game, {p['per90']:.2f}/90 | {history} | {odds}{floor} | {reason}")
    candidates.sort(key=lambda pair:(-pair[0]["ratio"], -pair[0]["starts"], pair[1]["ko"], pair[0]["id"]))
    headline = f"Booking watch · {date.fromisoformat(report['day']):%a %d %b}"
    if report["preview"]:
        headline += " · rehearsal"
    reviewed = statuses["reviewed"]
    below = statuses["below referee threshold"]
    missing = len(report["fixtures"])-reviewed-below
    count = len(candidates)
    coverage = f"{len(report['fixtures'])} fixtures · {reviewed} passed referee screen and reviewed · {missing} incomplete"
    caption = [headline, f"{count} priced candidate{'s' if count != 1 else ''}" if count else "No qualifying booking odds.", coverage]
    if report["calendarGaps"]:
        caption.append("Calendar coverage incomplete. Details attached.")
    missing_odds = player_coverage["no fresh exact booking odds"] + player_coverage["odds expired before delivery"]
    if missing_odds:
        caption.append(f"{missing_odds} player checks lacked fresh booking odds.")
    for p, f in candidates[:3]:
        ko = datetime.fromisoformat(f["ko"]).astimezone(UK)
        caption.extend(["", f"{p['player'][:75]} to be booked @ {p['odds']:.2f} · {p['book'][:45]}",
                        f"{f['home'][:40]} v {f['away'][:40]} · {ko:%H:%M UK} · {p['lineup']} XI",
                        f"{p['perGame']:.1f} fouls/game · booked {p['booked']}/{p['starts']} starts · ref {f['refSample']['mean']:.2f} yellows/game"])
    caption.append("\nFull fixture and odds checks attached.")
    body = [headline, coverage, f"Below referee threshold: {below}. Priced candidates: {count}.",
            "The five major domestic leagues are checked by fixture calendar. Other senior fixtures come from the worldwide next-appointment list.",
            "A referee qualifies at 4.5 yellows per match over 10 or more dated matches in the past year (up to 50).",
            "For each qualifying match the top three expected or confirmed starters across both teams are ranked by season fouls committed per appearance (minimum 270 minutes).",
            "The screening minimum uses a one-sided Wilson lower bound (z=1.28) on recent booked starts, plus a 3% odds cushion. This shortlist has no verified profit record.",
            "Decimal odds for an ordinary booking must be at most 60 minutes old. Check starting status, odds and bookmaker rules before use.",
            "Calendar gaps: " + ("; ".join(report["calendarGaps"]) or "none reported for the checked lists"),
            *detail]
    return "\n".join(caption), "\n".join(body)+"\n", count


def deliver(store, report, now):
    if report["preview"] or date.fromisoformat(report["day"]) != now.astimezone(UK).date():
        raise ValueError("Only today's live edition can be delivered")
    key = f"{PREFIX}/{report['day']}/delivery.json"
    previous = store.get(key)
    if previous and previous.get("state") == "sent":
        return
    caption, body, _ = digest(report, now)
    endpoint, chat = telegram_private()
    if not store.put(key, {"state":"sending", "at":now.isoformat()}, replace=False):
        if store.get(key, {}).get("state") == "sent":
            return
        raise RuntimeError("Uncertain delivery; verify original message before repeating")
    # Keep network retries outside sendDocument: an unacknowledged send may already be visible.
    response = http.post(endpoint+"/sendDocument", data={"chat_id":chat,"caption":caption},
                         files={"document":(f"booking-watch-{report['day']}.txt",body.encode("utf-8"),"text/plain")}, timeout=30)
    msg = payload(response)
    if not msg.get("ok") or not msg.get("result",{}).get("message_id"):
        raise RuntimeError("Digest delivery not acknowledged")
    store.put(key, {"state":"sent","at":now.isoformat(),"message_id":msg["result"]["message_id"]})


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
    store = Store()
    report = store.get(key)
    if args.mode == "deliver":
        if report is None:
            raise RuntimeError("Edition missing from private storage")
        deliver(store, report, datetime.now(UTC))
        print("Private delivery acknowledged")
        return
    if report is None:
        report = screen(Reads(Provider(store)), day, preview)
        if not store.put(key, report, replace=False):
            report = store.get(key)
    _, _, count = digest(report, datetime.now(UTC))
    statuses = Counter(f["status"] for f in report["fixtures"])
    print(f"Private report saved. Fixtures={len(report['fixtures'])}, reviewed={statuses['reviewed']}, "
          f"below={statuses['below referee threshold']}, candidates={count}, calendar gaps={len(report['calendarGaps'])}, reads={report['reads']}")
    if preview and (not report["fixtures"] or not any(f.get("refSample") for f in report["fixtures"])):
        raise RuntimeError("Rehearsal could not verify a dated referee record")


if __name__ == "__main__":
    main()
