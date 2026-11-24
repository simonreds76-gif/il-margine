"""Exact opening-round results from registered official Challenger singles draws."""
import calendar
import hashlib
import os
import re
from datetime import date
from functools import lru_cache
import requests

EVENTS = {"playford": 7586, "san salvador": 3199, "yokohama": 6626}


@lru_cache(maxsize=1)
def event_ids():
    from pinnradar_tennis import Store
    if not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        return EVENTS
    try:
        registry = Store().get("research/desk-draws/tournament-ids-v1.json")
    except (requests.RequestException, RuntimeError) as exc:
        print("Draw directory unavailable:",type(exc).__name__)
        return EVENTS
    if not registry:
        return EVENTS
    if (registry.get("schema")!=1 or not isinstance(registry.get("events"),dict)
            or not all(isinstance(k,str) and type(v) is int and 0<v<100000 for k,v in registry["events"].items())):
        print("Invalid draw directory; using the verified built-in venues.")
        return EVENTS
    return {**registry["events"],**EVENTS}


def draw_results(blocks, city, day):
    from drop_desk_history import completed_score, normal
    header = " ".join(b[4].strip() for b in blocks if b[1] < 75)
    if "Main Draw Singles" not in header or not re.search(r"\bChallenger\s+\d+", header):
        return {}
    if not any(normal(line.split(",")[0]) == city for b in blocks if b[1] < 75 for line in b[4].splitlines() if "," in line):
        return {}
    period = re.search(r"(\d{1,2}) ([A-Za-z]+)\s*[-–—]\s*(\d{1,2}) ([A-Za-z]+) (\d{4})",header)
    if not period:
        return {}
    a, m, b, n, y = period.groups()
    months = list(calendar.month_name)
    if m not in months or n not in months:
        return {}
    try:
        start, end = date(int(y),months.index(m),int(a)), date(int(y),months.index(n),int(b))
    except ValueError:
        return {}
    if not start <= day <= end or (end-start).days > 8:
        return {}
    seeds = {}
    for block in blocks:
        if block[4].startswith("Player\nRank\n"):
            for rank,full in re.findall(r"^(\d+) ([^\n]+,[^\n]+)$",block[4],re.M):
                seeds.setdefault(rank,[]).append(full)
    slots = {}
    for block in blocks:
        lines = [line.strip() for line in block[4].strip().splitlines()]
        joined = re.fullmatch(r"(.+,.+) ([A-Z]{3})",lines[-1]) if lines else None
        if joined:
            lines[-1:] = joined.groups()
        if len(lines) < 3 or not re.fullmatch(r"\d{1,2}", lines[0]) or not re.fullmatch(r"[A-Z]{3}",lines[-1]):
            continue
        slot = int(lines[0])
        if not 1 <= slot <= 32 or slot in slots:
            return {}
        name = lines[-2]
        if name.endswith(("…","...")) and len(lines)>=4:
            rank=lines[-3].split()[-1]
            choices=seeds.get(rank,[])
            prefix=normal(name.rstrip("…."))
            if len(choices)==1 and prefix and normal(choices[0]).startswith(prefix):
                name=choices[0]
        slots[slot] = block,name
    if set(slots) != set(range(1,33)):
        return {}
    # Read only the first advancement column. Winner and score must independently
    # align with the two numbered entrants in the bracket.
    right = max(v[0][2] for v in slots.values())
    inner = [b for b in blocks if b[0] > right and slots[1][0][1]-4 <= b[1] <= slots[32][0][1]+4 and b[4].strip()]
    if not inner:
        return {}
    first_col = min(b[0] for b in inner)
    column = [b for b in inner if abs(b[0]-first_col)<1]
    results = {}
    for slot in range(1,32,2):
        entrants = [slots[slot],slots[slot+1]]
        if any(name.count(",") != 1 or "…" in name or "..." in name for _,name in entrants):
            continue
        parts = [name.split(",") for _,name in entrants]
        names = [normal(first+" "+last) for last,first in parts]
        short = [normal(first.strip()[0]+" "+last) for last,first in parts if first.strip()]
        cells = [[c[4].strip() for c in column if abs(c[1]-b[1]) <= 4] for b,_ in entrants]
        if len(set(names))!=2 or len(set(short))!=2 or any(len(c)!=1 for c in cells):
            continue
        winner = normal(re.sub(r"\s+\d+\s*$","",cells[0][0]))
        sets = cells[1][0].split()
        if winner not in short or not all(re.fullmatch(r"(?:[0-7][0-7]|(?:67|76)\d{1,2})",s) for s in sets):
            continue
        score = " ".join(s[0]+"-"+s[1]+("("+s[2:]+")" if len(s)>2 else "") for s in sets)
        if completed_score(score,2):
            key = tuple(sorted(names))
            results[key] = (names[short.index(winner)],score) if key not in results else None
    return results


@lru_cache(maxsize=8)
def draw_document(code, year):
    if draw_document.cache_info().misses>6:
        return [], None
    url = f"https://www.protennislive.com/posting/{year}/{code}/mds.pdf"
    try:
        import pymupdf
        with requests.get(url, stream=True, timeout=(3,6), allow_redirects=False) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body)>1500000:
                    raise ValueError("Oversized draw")
        if not body.startswith(b"%PDF"):
            raise ValueError("Invalid draw")
        with pymupdf.open(stream=bytes(body),filetype="pdf") as doc:
            if len(doc)!=1:
                return [], None
            blocks = doc[0].get_text("blocks")
        return blocks, hashlib.sha256(body).hexdigest()
    except (ImportError, requests.RequestException, ValueError, RuntimeError) as exc:
        print("Official draw unavailable:",code,type(exc).__name__)
        return [], None


@lru_cache(maxsize=24)
def load_draw(city, day):
    blocks,digest = draw_document(event_ids()[city],day.year)
    return draw_results(blocks,city,day), digest
