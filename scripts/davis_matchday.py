"""Import named men's Davis Cup singles independently of prices and check both public views."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from pinnradar_tennis import Store

UK = ZoneInfo("Europe/London")
ROOT = "matchday/davis/"
SITE = "https://ilmargine.bet"
# Published session starts, not individual match times. Other editions use the
# date of their published order and no claimed venue or scheduled player time.
BOLOGNA = {"2026-11-24": ["15:00"], "2026-11-25": ["15:00"], "2026-11-26": ["09:00", "16:00"],
           "2026-11-27": ["15:00"], "2026-11-28": ["11:00"], "2026-11-29": ["14:00"]}
SESSIONS = {("2026-11-26", "Germany"): "09:00", ("2026-11-26", "Spain"): "16:00"}
EXPECTED = {"2026-11-24": 1, "2026-11-25": 1, "2026-11-26": 2, "2026-11-27": 1, "2026-11-28": 1, "2026-11-29": 1}
QUARTERS = {"2026-11-24": [{"Czechia","Canada"}], "2026-11-25":[{"Italy","Korea, Rep."}],
            "2026-11-26":[{"Great Britain","Germany"},{"Austria","Spain"}]}


def words(name):
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return tuple(re.findall(r"[a-z]+", text))


def name_matches(label, full):
    """Exact full name or explicitly initialled surname. Never a bare surname."""
    a, b = words(label), words(full)
    if len(a) < 2 or len(b) < 2:
        return False
    if a == b:
        return True
    # Some players' Asian given names appear hyphenated in only one source.
    if "".join(a) == "".join(b):
        return True
    for split in range(1, len(b)):
        given, surname = b[:split], b[split:]
        initials = tuple(part[0] for part in given)
        if a in (surname + initials, initials + surname, surname + given):
            return True
    return False


def fetch(url, allow_missing=False):
    r = requests.get(url, timeout=(4, 8))
    if r.status_code == 404 and allow_missing:
        return None
    r.raise_for_status()
    if len(r.content) > 2_800_000:
        raise ValueError("Schedule exceeds expected size")
    return BeautifulSoup(r.content, "html.parser")


def nominations(page, year, day):
    """Official participants used only to resolve identities in dated match rows."""
    stream = []
    for tag in page.select("script"):
        text = tag.string or ""
        if text.startswith("self.__next_f.push("):
            payload = json.JSONDecoder().raw_decode(text[text.index("(")+1:])[0]
            if payload[0] == 1:
                stream.append(payload[1])
    result = set()
    def walk(node):
        if isinstance(node, dict):
            if node.get("season") == year and isinstance(node.get("eventTeamNominations"), list):
                for group in node["eventTeamNominations"]:
                    for team in group.get("nominations", []):
                        if day in BOLOGNA and team.get("eventName") != "Finals":
                            continue
                        for player in team.get("players", []):
                            if player.get("isCaptain") is False and player.get("name") and team.get("teamName"):
                                result.add((player["name"], team["teamName"]))
                return
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for val in node:
                walk(val)
    for line in "".join(stream).splitlines():
        try:
            value = json.loads(line.split(":", 1)[1])
        except (IndexError, ValueError):
            continue
        walk(value)
    if not result:
        raise ValueError("Official player identities unavailable")
    return result


def corroborating_pairs(page, day):
    output = []
    for header in page.select("tr.head.flags"):
        if not header.select_one(f'a[href="/davis-cup/{day[:4]}/atp-men/"]'):
            continue
        for row in header.find_next_siblings("tr"):
            if "head" in row.get("class", []):
                break
            rid = row.get("id", "")
            other = row.find_next_sibling("tr")
            if not re.fullmatch(r"r\d+", rid) or not other or other.get("id") != rid+"b":
                continue
            cells = [r.select_one('td.t-name a[href^="/player/"]') for r in [row, other]]
            if all(cells):
                output.append(tuple(c.get_text(" ", strip=True) for c in cells))
    return output


def order_rows(page, day):
    section = page.select_one('section[aria-labelledby="oop-h"]')
    if not section or "davis cup" not in page.title.get_text(" ", strip=True).lower():
        raise ValueError("Davis Cup order unavailable")
    group = section.find(id="u-"+day)
    rows = []
    for row in group.select("ol.ml > li.mr") if group else []:
        names = []
        for side in row.select(".mr-p > .pl"):
            a = side.select_one("a.pn")
            if a:
                names.append((a.select_one(".fn") or a).get_text(" ", strip=True))
        link = row.select_one('.mr-a[href^="/partita/"]')
        if len(names) != 2 or not link or "-"+day+"-" not in link["href"]:
            continue
        if any("/" in n or "&" in n for n in names):
            continue
        rows.append((names, row.get("class", [])))
    return rows


def make_programme(rows, roster, reference, day, now):
    ties, blocked, orientations = defaultdict(list), set(), {}
    for labels, statuses in rows:
        persons = [set(entry for entry in roster if name_matches(label, entry[0])) for label in labels]
        if any(len(p) != 1 for p in persons):
            for p in persons:
                if len(p) == 1:
                    blocked.add(next(iter(p))[1])
            continue
        people = [next(iter(p)) for p in persons]
        teams = tuple(sorted(p[1] for p in people))
        if teams[0] == teams[1]:
            continue
        order = orientations.setdefault(teams, [p[1] for p in people])
        pair = tuple(next(name for name, country in people if country == team) for team in order)
        def confirms(labels):
            return all({name for name, team in roster if team == country and name_matches(label, name)} == {person}
                       for label, country, person in zip(labels, order, pair))
        matches = [r for r in reference if confirms(r) or confirms(r[::-1])]
        if len(matches) != 1 or not {"st-live", "st-scheduled", "st-finished", "st-completed", "st-final", "st-done"} & set(statuses):
            blocked.add(teams)
        ties[teams].append(pair)
    accepted = []
    for teams, pairs in ties.items():
        if day in QUARTERS and set(teams) not in QUARTERS[day]:
            continue
        if teams in blocked or any(t in blocked for t in teams) or len(pairs) != 2 or len({n for p in pairs for n in p}) != 4:
            blocked.add(teams)
            continue
        clock = "00:00"
        if day in BOLOGNA:
            clocks = BOLOGNA[day]
            clock = clocks[0] if len(clocks) == 1 else next((SESSIONS[(day,t)] for t in teams if (day,t) in SESSIONS), None)
            if not clock:
                continue
        session = day+"T"+clock+":00Z"
        if now < datetime.fromisoformat(session)-timedelta(hours=1):
            continue
        accepted.append({"teams":orientations[teams], "singles":[list(p) for p in pairs], "session":session,
                         "event":"Davis Cup · Bologna" if day in BOLOGNA else "Davis Cup",
                         "venue": "Bologna" if day in BOLOGNA else None})
    return accepted, {t for item in blocked for t in (item if isinstance(item, tuple) else (item,))}


def collect(now):
    day = now.astimezone(UK).date().isoformat()
    url = f"https://www.tennis-oggi.com/tornei/davis-cup-world-group-{day[:4]}"
    page = fetch(url, allow_missing=True)
    rows = order_rows(page, day) if page else []
    if not rows:
        return [], "awaiting_order", set()
    draw = fetch(f"https://www.daviscup.com/en/draws-results/{day[:4]}/finals")
    year, month, date = day.split("-")
    listings = fetch(f"https://www.tennisexplorer.com/matches/?year={year}&month={month}&day={date}")
    ties, disputed = make_programme(rows, nominations(draw, day[:4], day), corroborating_pairs(listings,day), day, now)
    return ties, "checked" if ties else "awaiting_agreement", disputed


def homepage_cards():
    chrome = next((which for name in ("google-chrome", "chromium", "chrome") if (which := shutil.which(name))), None)
    if not chrome and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
        chrome = str(candidate) if candidate.is_file() else None
    if not chrome:
        raise RuntimeError("Headless browser unavailable")
    with tempfile.TemporaryDirectory() as profile:
        env = {k:v for k,v in os.environ.items() if k in ("HOME","PATH","TMPDIR","TEMP","TMP","LANG","SystemRoot","LOCALAPPDATA")}
        cmd = [chrome, "--headless", "--disable-gpu", "--disable-dev-shm-usage", "--disable-extensions",
               "--no-first-run", "--user-data-dir="+profile, "--virtual-time-budget=15000", "--dump-dom", SITE+"/#home-tennis"]
        result = subprocess.run(cmd, capture_output=True, env=env, timeout=35, check=True)
    soup = BeautifulSoup(result.stdout, "html.parser")
    return {(int(card["data-singles-order"]), tuple(sorted("".join(words(n.get_text(strip=True))) for n in card.select("h4"))))
            for card in soup.select("#home-tennis article[data-singles-order]")}


def public_check(ties, browser=True):
    expected = {(i,tuple(sorted("".join(words(n)) for n in pair))) for t in ties for i,pair in enumerate(t["singles"],1)}
    page = fetch(SITE+"/tennis-matchday")
    seen = set()
    for row in page.select('section[aria-label^="Davis Cup"] [data-singles-order]'):
        names = [n.get_text(" ", strip=True) for n in row.select("button span[class*='_name']")]
        if len(names) == 2:
            seen.add((int(row["data-singles-order"]),tuple(sorted("".join(words(n)) for n in names))))
    r = requests.get(SITE+"/api/home-fixtures",timeout=(4,8))
    r.raise_for_status()
    home = {(f["programme"]["order"], tuple(sorted("".join(words(p["name"])) for p in f["sides"]))) for f in r.json()["tennis"]["fixtures"] if f.get("programme")}
    both = bool(expected) and expected <= seen and expected <= home
    cards = homepage_cards() if both and browser else set()
    return {"expected":len(expected), "matchday":len(expected & seen), "homeFeed":len(expected & home),
            "homeCards":len(expected & cards), "verified":bool(both and expected <= cards)}


def run(now, dry=False):
    day = now.astimezone(UK).date().isoformat()
    path = ROOT+day+"/"
    store = None if dry else Store()
    previous = store.get(path+"programme.json") if store else None
    # Outside a known session window, discover other published ties hourly.
    if not dry and day not in BOLOGNA and not previous and now.minute >= 15:
        return {"state":"outside_discovery_slot"}
    ties, state, disputed = collect(now)
    if dry:
        return {"day":day,"state":state,"ties":ties}
    fresh = {tuple(sorted(t["teams"])):t for t in ties}
    for tie in (previous or {}).get("ties",[]):
        if not disputed.intersection(tie["teams"]):
            fresh.setdefault(tuple(sorted(tie["teams"])), tie)
    ties = [fresh[key] for key in sorted(fresh)]
    stamp = now.isoformat()
    # A disagreement withdraws unsupported selections. Transport errors above
    # preserve the last accepted document; each document is specific to one day.
    doc = {"version":1, "day":day, "verifiedAt":stamp, "ties":ties}
    changed = (previous or {}).get("ties",[]) != ties
    if changed:
        store.put(path+"programme.json",doc,replace=True)
        if store.get(path+"programme.json") != doc:
            raise RuntimeError("Programme read-back mismatch")
    receipt = {"day":day, "checkedAt":stamp, "state":state, "ties":len(ties)}
    digest = hashlib.sha256(json.dumps(ties,sort_keys=True).encode()).hexdigest()
    last = store.get(path+"last-check.json") if previous and ties else None
    if ties:
        if last and last.get("digest") == digest and last.get("public",{}).get("verified") and not changed:
            receipt["public"] = last["public"]
        else:
            try:
                receipt["public"] = public_check(ties)
            except (OSError, ValueError, RuntimeError, requests.RequestException, subprocess.SubprocessError) as error:
                receipt["public"] = {"verified":False, "problem":type(error).__name__}
                print("::warning::Could not verify both public Davis Cup views")
            receipt["public"]["checkedAt"] = stamp
        receipt["digest"] = digest
    if ties or day in EXPECTED or previous:
        store.put(path+"last-check.json",receipt,replace=True)
    if ties and receipt["public"]["verified"] and (not last or last.get("digest") != digest or not last.get("public",{}).get("verified")):
        for tie in ties:
            key = "-".join("-".join(words(t)) for t in tie["teams"])
            store.put(path+"verified-"+key+".json",{"programme":tie,**receipt},replace=True)
    if day in EXPECTED:
        due = sum(now >= datetime.fromisoformat(day+"T"+s+":00Z")+timedelta(minutes=15) for s in BOLOGNA[day])
        if len(ties) < due or (due and ties and not receipt.get("public",{}).get("verified")):
            print("::warning::Davis Cup public lineup verification is outstanding")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    args = parser.parse_args()
    result = run(datetime.now(timezone.utc), args.dry_run)
    print(json.dumps(result,ensure_ascii=True))

