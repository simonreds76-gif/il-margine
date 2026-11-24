"""Discover fixtures in the interval between two London morning editions."""
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from statshub_daily_contracts import LEAGUES, identity, utc

LONDON = ZoneInfo("Europe/London")
SOUTH_AMERICA = {
    "argentina", "bolivia", "brazil", "chile", "colombia", "ecuador", "guyana",
    "paraguay", "peru", "suriname", "uruguay", "venezuela", "french guiana", "south america",
}
DOMESTIC = {identity(comp): name for name, (comp, _) in LEAGUES.items()}
HEADER = re.compile(r"^(.+?) \(([^()]+)\) \[competitionId ([\w.-]+)\]:$")
ROW = re.compile(r"^- (?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) )?(\d\d:\d\d) (.+?) v (.+?) \(id ([\w.-]+)\)")
ID = re.compile(r"\(id ([\w.-]+)\)")
CLOSED = re.compile(r"\b(live|HT|FT|postponed|cancelled|abandoned|finished|suspended|full time)\b", re.I)
OMITTED = re.compile(r"(?:^|; )([^;]+?) \(([^()]+)\) \[competitionId ([\w.-]+)\] (\d+)")


def competition(name, country, comp):
    if identity(comp) in DOMESTIC:
        return DOMESTIC[identity(comp)]
    if country.casefold() in SOUTH_AMERICA or (country == "Europe" and name == "UEFA Champions League"):
        return f"{name} ({country})"
    return None


def only_unrelated_omissions(doc, missing):
    notes = doc.get("notListed") or ""
    groups = OMITTED.findall(notes.partition(": ")[2])
    return (missing > 0 and sum(int(n) for _, _, _, n in groups) == missing
            and all(not competition(name, country, comp) for name, country, comp, _ in groups))


def calendar(reader, day, now):
    first = datetime.combine(datetime.fromisoformat(day).date(), time(11), tzinfo=LONDON)
    start, end = (v.astimezone(timezone.utc) for v in (first, first + timedelta(days=1)))
    # Keep each request within a UTC date so a 00:15 Brazilian fixture cannot acquire yesterday's date.
    midnight = datetime.combine(start.date() + timedelta(days=1), time(), tzinfo=timezone.utc)
    pending = [(start, midnight), (midnight, end)]
    games, coverage = {}, []
    reads = 0
    while pending:
        lo, hi = pending.pop(0)
        label = f"{lo:%d %b %H:%M}–{hi:%d %b %H:%M} UTC"
        packet = None
        if reads < 32:
            args = dict(startOfDay=int(lo.timestamp()), endOfDay=int(hi.timestamp()), timeZone="Europe/London")
            packet = reader.read("getFixturesByDate", args, "morning")
            reads += 1
        doc = (packet or {}).get("data") or {}
        total, listed = doc.get("fixtureCount"), doc.get("listedCount")
        valid = type(total) is int and type(listed) is int and 0 <= listed <= total
        minutes = int((hi-lo).total_seconds() // 60)
        complete_scope = valid and (listed == total or only_unrelated_omissions(doc, total-listed))
        if valid and not complete_scope and minutes > 1 and reads + len(pending) + 2 <= 32:
            mid = lo + timedelta(minutes=minutes//2)
            pending.extend([(lo, mid), (mid, hi)])
            continue
        summary = doc.get("fixturesSummary") or ""
        seen, open_ids = set(), set()
        league = comp = None
        parsed = valid and (total == 0 or "times UTC" in doc.get("context", ""))
        for line in summary.splitlines():
            if not line.startswith("- "):
                head = HEADER.fullmatch(line)
                league, comp = (competition(*head.groups()), head[3]) if head else (None, None)
                continue
            fid = ID.search(line)
            if not fid or not comp:
                parsed = False
                continue
            seen.add(identity(fid[1]))
            if not league or CLOSED.search(line):
                continue
            row = ROW.match(line)
            if not row:
                parsed = False
                continue
            ko = utc(f"{lo.date()}T{row[1]}:00+00:00")
            if not lo <= ko < hi:
                parsed = False
                continue
            if ko <= now:
                continue
            key = identity(row[4])
            games[key] = dict(home=row[2], away=row[3], id=row[4], ko=ko.isoformat(),
                              league=league, competitionId=comp)
            open_ids.add(key)
        gap = "" if parsed and complete_scope and listed == len(seen) else "fixture list incomplete"
        coverage.append(dict(league=label, total=total, open=len(open_ids), gap=gap))
    return sorted(games.values(), key=lambda f: (f["ko"], f["id"])), sorted(coverage, key=lambda r: r["league"])
