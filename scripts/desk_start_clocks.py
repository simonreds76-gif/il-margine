"""Bounded, private match-clock discovery. Scheduled times are identity checks only."""
import hashlib
import json
import re
from datetime import timedelta
from functools import lru_cache
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from drop_desk_history import normal, wta_result, wta_scoreboard
from pinnradar_tennis import utc

ROUNDS={"sf":"semifinal","qf":"quarterfinal","final":"final","groups":"round robin",
        "q1":"qualifying first round","q2":"qualifying second round","q3":"qualifying final"}


def link_candidates(ticket, directory):
    rnd=ticket["league"].rpartition(" - ")[2].lower()
    expected=ROUNDS.get(rnd) or ("round of "+rnd[1:] if re.fullmatch(r"r(16|32|64|128)",rnd) else None)
    if not expected:return []
    names=[normal(ticket[k]).split() for k in ("player","opponent")]
    hits=[]
    for path,text in directory:
        line=normal(text)
        if not (line.startswith(expected+" ") or rnd=="groups" and "finals" in line):continue
        if all(re.search(r"\b"+re.escape(p[0][0])+r" (?:[a-z]+ )*?"+re.escape(p[-1])+r"\b",line) for p in names):
            hits.append(path)
    return list(dict.fromkeys(hits))


def opening_point(page, ident):
    chunks=[]
    for tag in page.find_all("script"):
        js=tag.string or ""
        if js.startswith("self.__next_f.push([1,"):
            chunks.append(json.loads(js[js.index("(")+1:js.rindex(")")])[1])
    text="".join(chunks)
    needle='{"id":"'+ident+'-01-01-001"'
    valid=set()
    for match in re.finditer(re.escape(needle),text):
        point,_=json.JSONDecoder().raw_decode(text[match.start():])
        if not all(k in point for k in ("time","completedDateUtc")):continue
        if point.get("complete") is not True or any(point.get(k)!=1 for k in ("setNumber","gameNumber","pointNumber","pointSequence")):
            continue
        begin,end=utc(point["time"]),utc(point["completedDateUtc"])
        if begin and end and begin<=end<=begin+timedelta(minutes=5):
            valid.add(begin)
    return valid.pop() if len(valid)==1 else None


def match_clock(ticket, page, ident):
    title=page.title.get_text(" ",strip=True) if page.title else ""
    meta=page.find("meta",attrs={"name":"description"})
    detail=normal(meta["content"]) if meta and meta.has_attr("content") else ""
    womens=ticket["tour"] in ("WTA","WTA 125")
    if ("women s singles" if womens else "men s singles") not in detail:return None
    place=normal(ticket["league"].rpartition(" - ")[0])
    place=re.sub(r"^(?:atp|wta)(?: challenger| 125k?)? ","",place)
    if not place or ((" "+place+" ") not in " "+detail+" " and not (place=="finals" and " turin " in " "+detail+" ")):
        return None
    names={normal(image["alt"]) for image in page.select("img[alt]")}
    for tag in page.find_all("script"):
        js=tag.string or ""
        if js.startswith("self.__next_f.push([1,"):
            block=json.loads(js[js.index("(")+1:js.rindex(")")])[1]
            names.update(normal(json.loads(v)) for v in re.findall(r'"alt":("(?:[^"\\]|\\.)*")',block))
    if any(normal(ticket[k]) not in names for k in ("player","opponent")):return None
    if not re.search(r"#(?:MS|QS|WS|LS)\d+\b",title):return None
    return opening_point(page,ident)


def fetch_page(url):
    response=requests.get(url,timeout=(4,8),allow_redirects=False)
    if response.status_code!=200:raise ValueError("Clock page unavailable")
    return BeautifulSoup(response.content,"html.parser")


def refresh_clocks(tickets, config, saved, now):
    @lru_cache(maxsize=2)
    def board(url):
        if urlsplit(url).scheme!="https":raise ValueError("Invalid directory")
        doc=fetch_page(url)
        return [(a["href"],a.get_text(" ",strip=True)) for a in doc.select("a[href]")
                if re.fullmatch(r"/en/results/[a-f0-9-]{36}",a["href"])]
    @lru_cache(maxsize=3)
    def women(day):
        return wta_scoreboard(day)
    due={}
    for t in tickets:
        key=t["fixture"]
        scheduled=utc(t["start"])
        if key in saved["clocks"] or key in config["clocks"] or not scheduled<=now<scheduled+timedelta(days=14):
            continue
        last=utc(saved["checked"].get(key))
        if not last or now-last>=timedelta(hours=1):due[key]=t
    for key,t in sorted(due.items(),key=lambda kv:saved["checked"].get(kv[0],""))[:3]:
        saved["checked"][key]=now.isoformat()
        begin=None
        evidence=None
        precision=0
        try:
            womens=t["tour"] in ("WTA","WTA 125")
            url=config["directory"].get("WTA" if womens else "ATP")
            if url:
                paths=link_candidates(t,board(url))
                if len(paths)==1:
                    path=paths[0]
                    page=fetch_page(urljoin(url,path))
                    begin=match_clock(t,page,path.rsplit("/",1)[1])
                    if begin:evidence=hashlib.sha256(page.encode()).hexdigest()
            if womens and not begin:
                events=women(t["start"][:10])
                bound=wta_result(t,events)
                if bound and bound[1].get("score")!="W/O":
                    edition,game_id=bound[0][1:3]
                    for event in events:
                        if event["id"]!=edition:continue
                        for grouping in event.get("groupings",[]):
                            for game in grouping.get("competitions",[]):
                                if game["id"]==game_id:
                                    begin=utc(game.get("actualStartDate"))
                                    if begin:
                                        evidence=str(game_id)
                                        precision=60 if begin.second==begin.microsecond==0 else 0
        except (requests.RequestException,KeyError,TypeError,ValueError):
            continue
        if begin and begin<=now and abs(begin-utc(t["start"]))<=timedelta(hours=36):
            saved["clocks"][key]=dict(start_report=begin.isoformat(),precision_seconds=precision,league=t["league"],evidence=evidence,
                                      players=[t["player"],t["opponent"]])
