"""List the leading foul committers in upcoming matches assigned to high-booking referees."""
import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import os
import re
from time import monotonic
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


class Missing(Exception):
    """One fixture or data source could not be verified."""


class Reads:
    def __init__(self, api, max_reads=220, seconds=1200):
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
                              sortField="next_game_timestamp", sortDirection="asc", minGames=0, limit=30, page=page)
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
                        existing = games.setdefault(identity(f["id"]), f)
                        if existing["ko"] == f["ko"] and all(norm(existing[s]) == norm(f[s]) for s in ("home","away")):
                            existing["indexYellows"] = ref.get("yellowsPerGame")
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
    title = f"Player foul watch · {date.fromisoformat(report['day']):%a %d %b}"
    if report["preview"]:
        title += " · rehearsal"
    reviewed = statuses["reviewed"]
    below = statuses["below referee threshold"]
    missing = len(report["fixtures"]) - reviewed - below
    coverage = f"{reviewed} matches reviewed · {below} below referee cutoff · {missing} incomplete"
    caption = [title, coverage]
    if report["calendarGaps"]:
        caption.append("Calendar coverage incomplete.")
    if not leaders:
        caption.append("No upcoming player foul leaders with verified data.")
    for player, fixture in leaders[:3]:
        kickoff = datetime.fromisoformat(fixture["ko"]).astimezone(UK)
        sample = fixture["refSample"]
        caption.extend(["", f"{player['player'][:50]} · {player['fouls']} fouls in {player['apps']} appearances "
                        f"({player['perGame']:.2f}/game)",
                        f"{fixture['home'][:28]} v {fixture['away'][:28]} · {kickoff:%H:%M UK} · {player['lineup']} XI",
                        f"Ref {fixture['referee'][:35]} · {sample['mean']:.2f} yellows/game ({sample['games']} games)"])
    caption.append("\nFull match-by-match list attached.")
    body = [title, coverage,
            f"Referee screen: at least {MIN_YELLOWS:.1f} yellow cards per match in {MIN_REF_GAMES}+ dated games "
            "over the past year (up to 50 games, all competitions).",
            f"Up to three likely starters per match, ranked across both teams by season fouls committed per appearance. "
            f"Minimum {MIN_MINUTES} minutes and three appearances. Ties use fouls per 90, then minutes.",
            "Coverage includes the five major domestic leagues and other senior fixtures listed with a referee appointment.",
            "Calendar gaps: " + ("; ".join(report["calendarGaps"]) or "none identified in the checked lists"),
            *details]
    return "\n".join(caption), "\n".join(body)+"\n", len(leaders)


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
                         files={"document":(f"player-foul-watch-{report['day']}.txt",body.encode("utf-8"),"text/plain")}, timeout=30)
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
          f"below={statuses['below referee threshold']}, upcoming_leaders={count}, calendar gaps={len(report['calendarGaps'])}, reads={report['reads']}")
    if preview and (not report["fixtures"] or not any(f.get("refSample") for f in report["fixtures"])):
        raise RuntimeError("Rehearsal could not verify a dated referee record")


if __name__ == "__main__":
    main()
