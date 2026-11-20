"""Evidence and exact full-time contracts for the private matchweek pilot."""
import csv
import hashlib
import io
import math
import re
import unicodedata
from datetime import datetime, timezone

import requests

LEAGUES = {"Premier League": ("premier-league.0z9xjh1", "E0"), "Serie A": ("serie-a.17atem7", "I1"),
           "La Liga": ("laliga.1ddpw68", "SP1"), "Bundesliga": ("bundesliga.19a8rva", "D1"),
           "Ligue 1": ("ligue-1.13zyav8", "F1")}
TEAM_MARKETS = {"Total Corners": ("corners","match"), "Match Shots": ("shots","match"),
    "Match Shots on Target": ("shotsOnTarget","match"), "Total Goals": ("goals","match"),
    "Both Teams To Score": ("btts","match"), "To Win": ("result","match"),
    "Home Team Goals": ("goals","home"), "Away Team Goals": ("goals","away"),
    "Team Shots Home": ("shots","home"), "Team Shots Away": ("shots","away"),
    "Team Shots on Target Home": ("shotsOnTarget","home"), "Team Shots on Target Away": ("shotsOnTarget","away"),
    "Home Team Shots": ("shots","home"), "Away Team Shots": ("shots","away"),
    "Home Team Shots on Target": ("shotsOnTarget","home"), "Away Team Shots on Target": ("shotsOnTarget","away"),
    "Home Team Corners": ("corners","home"), "Away Team Corners": ("corners","away"),
    "Double Chance": ("doubleChance","match"), "Asian Handicap": ("handicap","match"),
    "Total Fouls": ("fouls","match"), "Match Fouls": ("fouls","match"),
    "Home Team Fouls": ("fouls","home"), "Away Team Fouls": ("fouls","away")}
PLAYER_MARKETS = {"Player Shots":"shots", "Player Shots On Target":"shotsOnTarget", "Player Assists":"assists",
    "Player Fouls Committed":"fouls","Player Fouls":"fouls","Player Fouls Won":"foulsWon","Player Tackles":"tackles",
    "Player Saves":"saves","Player Passes":"passes","Player Offsides":"offsides",
    "Player Interceptions":"interceptions","Player Goals":"goals",
    "Player Crosses":"crosses","Player Key Passes":"keyPasses","Player Aerials Won":"aerialsWon",
    "Player Duels Won":"duelsWon","Player Passes Completed":"passesCompleted",
    "Player Dispossessions":"timesDispossessed","Player Possession Lost":"possessionLost"}
MARKETS = list(TEAM_MARKETS) + list(PLAYER_MARKETS)
PLAYER_STATS = {"shots":"shots", "shotsOnTarget":"shots on target", "tackles":"tackles",
                "fouls":"fouls committed", "foulsWon":"fouls drawn"}
PLAYER_PRICE_MIN = 1.70
PLAYER_POLICY = "player-counts-v1"
ALIASES = {
    "Manchester United":"Man United","Manchester City":"Man City","Nottingham Forest":"Nott'm Forest",
    "Leeds United":"Leeds","Coventry City":"Coventry","Tottenham Hotspur":"Tottenham","Ipswich Town":"Ipswich",
    "Newcastle United":"Newcastle","Hull City":"Hull","Brighton & Hove Albion":"Brighton",
    "Athletic Club":"Ath Bilbao","Deportivo Alavés":"Alaves","Deportivo La Coruña":"La Coruna",
    "Rayo Vallecano":"Vallecano","Real Betis":"Betis","Celta Vigo":"Celta","Real Sociedad":"Sociedad",
    "Atlético Madrid":"Ath Madrid","Racing de Santander":"Santander","Levante UD":"Levante","Espanyol":"Espanol",
    "FC Bayern München":"Bayern Munich","1. FC Köln":"FC Koln","Bayer 04 Leverkusen":"Leverkusen",
    "SC Paderborn 07":"Paderborn","Eintracht Frankfurt":"Ein Frankfurt","TSG Hoffenheim":"Hoffenheim",
    "Borussia M'gladbach":"M'gladbach","Borussia Dortmund":"Dortmund","1. FC Union Berlin":"Union Berlin",
    "RB Leipzig":"RB Leipzig","SV 07 Elversberg":"Elversberg","SC Freiburg":"Freiburg","FC Schalke 04":"Schalke 04",
    "VfB Stuttgart":"Stuttgart","FC Augsburg":"Augsburg","1. FSV Mainz 05":"Mainz","SV Werder Bremen":"Werder Bremen",
    "Hamburger SV":"Hamburg","Paris Saint-Germain":"Paris SG","RC Lens":"Lens","Olympique Lyonnais":"Lyon",
    "AS Monaco":"Monaco","RC Strasbourg":"Strasbourg","Stade Brestois":"Brest","Stade Rennais":"Rennes",
    "Olympique de Marseille":"Marseille"}

def norm(text):
    ascii_text=unicodedata.normalize("NFKD",str(text)).encode("ascii","ignore").decode()
    return re.sub(r"[^a-z0-9]","",ascii_text.lower())

def identity(value):
    return str(value or "").rsplit(".",1)[-1]

def utc(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)

def fixtures(board,day,league):
    matches=[]
    for line in board.get("fixturesSummary","").splitlines():
        m=re.match(r"^- (?:(Mon|Tue|Wed|Thu|Fri|Sat|Sun) )?(\d\d:\d\d) (.+?) v (.+?) \(id ([\w.-]+)\)",line)
        if not m or (m[1] and m[1]!=datetime.fromisoformat(day).strftime("%a")):
            continue
        matches.append(dict(home=m[3],away=m[4],id=m[5],ko=day+"T"+m[2]+":00+00:00",league=league))
    return matches

def load_history(league,day):
    code=LEAGUES[league][1]
    rows={}
    for season in ("2526","2627"):
        url=f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
        try:
            response=requests.get(url,timeout=12)
            response.raise_for_status()
            data=csv.DictReader(io.StringIO(response.content.decode("utf-8-sig",errors="replace")))
            for r in data:
                if not r.get("Date") or not (r.get("FTHG") or "").isdigit() or not (r.get("FTAG") or "").isdigit():
                    continue
                when=datetime.strptime(r["Date"],"%d/%m/%Y" if len(r["Date"])==10 else "%d/%m/%y").date().isoformat()
                if when<day:
                    rows[(when,r["HomeTeam"],r["AwayTeam"])]=(when,r)
        except (requests.RequestException,ValueError,KeyError):
            continue
    return sorted(rows.values(),key=lambda item:item[0],reverse=True)

def exact_quote(outcome,max_age):
    best=outcome.get("best") or {}
    price=best.get("odds")
    age=best.get("ageMinutes")
    book=best.get("bookmaker")
    if (type(price) not in (int,float) or not math.isfinite(price) or price<=1 or
        type(age) not in (int,float) or not 0<=age<=max_age or not book or
        re.search(r"exchange|boost|super.?sub|promo",book,re.I)):
        return None
    return dict(odds=price,book=book,age=age)

def number_contract(label):
    m=re.fullmatch(r"(Over|Under) (\d+\.5)",label,re.I)
    return (m[1].lower(),float(m[2])) if m else None

def screen_age(row):
    age=row.get("bestOddsAgeMinutes")
    if type(age) in (int,float): return age
    shown=str(row.get("bestOddsAge","")).casefold()
    if shown in ("just now","less than a minute old"): return 1
    match=re.fullmatch(r"(\d+) minutes? old",shown)
    return int(match[1])+1 if match else None

def contracts(f,board,player_rows,max_age):
    people={}
    for r in player_rows:
        if identity(r.get("matchId"))!=identity(f["id"]): continue
        people.setdefault((norm(r.get("playerName","")),r.get("statType")),set()).add(r["playerId"])
    offers={}
    for market in board.get("markets",[]):
        name=market.get("name","")
        for out in market.get("outcomes",[]):
            quote=exact_quote(out,max_age)
            if not quote: continue
            label=out.get("label","")
            side=""; player=""; player_name=""; line=None
            if name in TEAM_MARKETS:
                stat,side=TEAM_MARKETS[name]
                if stat=="btts" and label.lower() in ("yes","no"):
                    direction=label.lower()
                elif stat=="result" and norm(label) in {norm(f["home"]),norm(f["away"]),"draw"}:
                    direction="draw" if label.lower()=="draw" else "home" if norm(label)==norm(f["home"]) else "away"
                elif stat=="doubleChance":
                    labels={norm(f["home"]+" or Draw"):"home/draw",norm("Draw or "+f["away"]):"draw/away",
                            norm(f["home"]+" or "+f["away"]):"home/away"}
                    direction=labels.get(norm(label))
                    if direction is None: continue
                elif stat=="handicap":
                    m=re.fullmatch(r"(.+) \(([+-]\d+\.5)\)",label)
                    if not m or norm(m[1]) not in (norm(f["home"]),norm(f["away"])): continue
                    direction="home" if norm(m[1])==norm(f["home"]) else "away"
                    line=float(m[2])
                else:
                    parsed=number_contract(label)
                    if not parsed or stat in ("btts","result"): continue
                    direction,line=parsed
            elif name in PLAYER_MARKETS:
                stat=PLAYER_MARKETS[name]
                m=re.fullmatch(r"(.+) (Over|Under) (\d+\.5)",label,re.I)
                if not m: continue
                ids=people.get((norm(m[1]),stat),set())
                if len(ids)!=1: continue
                player=next(iter(ids));player_name=m[1];side="player";direction=m[2].lower();line=float(m[3])
            else: continue
            key="|".join(map(str,(identity(f["id"]),side,identity(player),stat,direction,line)))
            pick=dict(id=hashlib.sha256(key.encode()).hexdigest()[:24],matchId=f["id"],
                fixture=f['home']+" v "+f['away'],home=f["home"],away=f["away"],league=f["league"],ko=f["ko"],
                market=name,label=(f[side]+" · " if side in ("home","away") else "")+name+" · "+label,
                side=side,stat=stat,line=line,direction=direction,player=player,playerName=player_name,**quote)
            if key not in offers or quote["odds"]>offers[key]["odds"]: offers[key]=pick
    # The dedicated player screen also carries markets absent from the match price board.
    # Never assume that an omitted age means fresh.
    for r in player_rows:
        if identity(r.get("matchId"))!=identity(f["id"]) or not r.get("playerId") or not r.get("playerName"): continue
        side=r.get("oddsType")
        line=r.get("line")
        if side not in ("under","over") or type(line) not in (int,float) or line%1!=0.5: continue
        stat=r.get("statType")
        age=screen_age(r)
        if not stat or age is None: continue
        quote=exact_quote({"best":{"bookmaker":r.get("bestBookmakerName"),"odds":r.get("bestOdds"),"ageMinutes":age}},max_age)
        if not quote: continue
        key="|".join(map(str,(identity(f["id"]),"player",identity(r["playerId"]),stat,side,float(line))))
        if key in offers and offers[key]["odds"]>=quote["odds"]: continue
        market=next((k for k,v in PLAYER_MARKETS.items() if v==stat),"Player "+stat)
        offers[key]=dict(id=hashlib.sha256(key.encode()).hexdigest()[:24],matchId=f["id"],fixture=f["home"]+" v "+f["away"],
            home=f["home"],away=f["away"],ko=f["ko"],league=f["league"],market=market,side="player",player=r["playerId"],
            playerName=r["playerName"],stat=stat,line=float(line),direction=side,label=f"{r['playerName']} · {side} {line} {stat}",**quote)
    return list(offers.values())

def won(p,home,away):
    if p["stat"]=="btts": return (home>0 and away>0)==(p["direction"]=="yes")
    if p["stat"] in ("result","doubleChance"):
        result="home" if home>away else "away" if away>home else "draw"
        return result in p["direction"].split("/")
    if p["stat"]=="handicap":
        difference=home-away if p["direction"]=="home" else away-home
        return difference+p["line"]>0
    value=home+away if p["side"]=="match" else away if p["side"]=="away" else home
    return value>p["line"] if p["direction"]=="over" else value<p["line"]

def form(p,history,day):
    names=[norm(ALIASES.get(p[k],p[k])) for k in ("home","away")]
    columns={"shots":("HS","AS"),"shotsOnTarget":("HST","AST"),"corners":("HC","AC"),"fouls":("HF","AF")}.get(p["stat"],("FTHG","FTAG"))
    groups=[[],[]]
    for date,row in history:
        if date>=day: continue
        sides=[norm(row["HomeTeam"]),norm(row["AwayTeam"])]
        indices=[i for i in range(2) if names[i]==sides[i] and len(groups[i])<15]
        if len(indices)!=1 or not all((row.get(k) or "").isdigit() for k in columns): continue
        groups[indices[0]].append(won(p,*(int(row[k]) for k in columns)))
    if min(map(len,groups))<8: return None
    return groups

def price_floor(wins,total):
    # One-sided Wilson lower bound, z=1.28. A screening rule, not a fitted probability.
    z=1.28; frequency=wins/total
    lower=(frequency+z*z/(2*total)-z*math.sqrt(frequency*(1-frequency)/total+z*z/(4*total*total)))/(1+z*z/total)
    return math.ceil(100*1.03/lower)/100 if lower>0 else math.inf

def team_case(p,rows,day):
    groups=form(p,rows,day)
    if not groups: return False
    a,b=groups
    minimum=price_floor(sum(a)+sum(b),len(a)+len(b))
    if min(sum(a)/len(a),sum(b)/len(b))<=1/p["odds"] or p["odds"]<minimum: return False
    p.update(minimum=minimum,why=f"The same outcome hit in {sum(a)}/{len(a)} previous {p['home']} home games and {sum(b)}/{len(b)} {p['away']} away games in this league. Break-even at this price is {100/p['odds']:.1f}%.",
             risk="Venue samples span different opponents and squads. The price floor is a historical screen.")
    return True

def player_case(p,r,history):
    stat=history.get("requestedStat") or {}
    if stat.get("statType")!=p["stat"] or not stat.get("column"): return False
    rows=[dict(zip(history["matchColumns"],v)) for v in history.get("matchRows",[])] if "matchColumns" in history else history.get("matches",[])
    teams=(history.get("span") or {}).get("teams") or []
    sole_team=teams[0] if len(teams)==1 else None
    samples={}
    for row in rows:
        date=row.get("date") or ""
        count=row.get(stat["column"])
        minutes=row.get("minutes")
        key=identity(row.get("matchId"))
        if (not key or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date) or date>=p["ko"][:10]
            or norm(row.get("team") or sole_team or "")!=norm(r["teamName"])
            or type(count) not in (float,int) or not math.isfinite(count) or count<0
            or type(minutes) not in (float,int) or not 0<minutes<=130): continue
        sample=(count,minutes,date)
        if key in samples and samples[key]!=sample: return False
        samples[key]=sample
    n=len(samples)
    if n<10: return False
    hits=sum(won(p,count,0) for count,_,_ in samples.values())
    floor=max(PLAYER_PRICE_MIN,price_floor(hits,n))
    if p["odds"]<floor: return False
    avg=sum(count for count,_,_ in samples.values())/n
    minutes=sum(mins for _,mins,_ in samples.values())/n
    p.update(minimum=floor,teamId=r["teamId"],hits=hits,starts=n,meanCount=avg,meanMinutes=minutes,
             why=f"{hits} of {n} previous league starts for {r['teamName']} cleared this selection. Averaged {avg:.1f} {PLAYER_STATS[p['stat']]} and {minutes:.0f} minutes. Break-even at these odds is {100/p['odds']:.1f}%. Opponent: {r['matchup']}.",
             risk="Expected starter. Check the official XI, role and substitution terms before posting.")
    return True
