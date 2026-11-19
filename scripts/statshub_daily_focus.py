"""Private fixture notes. Notes never create a selection or change its price floor."""
from collections import Counter
from datetime import date
from math import isfinite

from statshub_daily_contracts import LEAGUES, exact_quote, identity, norm, utc

FOCUS_LIMIT = 22
WIDE_OPPONENT = {
    "LB": {"RW", "RM"}, "LWB": {"RW", "RM"}, "RB": {"LW", "LM"}, "RWB": {"LW", "LM"},
    "LW": {"RB", "RWB"}, "LM": {"RB", "RWB"}, "RW": {"LB", "LWB"}, "RM": {"LB", "LWB"},
}


def read_data(reader, tool, args):
    obs = reader.read(tool, args, "focus")
    return (obs or {}).get("data") or {}


def number(value):
    return type(value) in (int, float) and isfinite(value) and value >= 0


def select_fixtures(fixtures, picks, prices, now):
    # League-wide screen first; one fixture cannot take three places via alternate lines.
    open_rows = [p for p in prices if utc(p["ko"]) > now and number(p["age"]) and
                 0 <= (now-utc(p["at"])).total_seconds()/60 <= 60-p["age"]]
    coverage = Counter(p["matchId"] for p in open_rows)
    best = {}
    for p in picks:
        best.setdefault(p["matchId"], []).append(p)
    def priority(f):
        pool = best.get(f["id"], [])
        return (not any(p.get("player") for p in pool), not bool(pool),
                -max((p["odds"]/p["minimum"] for p in pool),default=0), -coverage[f["id"]], f["ko"], f["id"])
    return sorted((f for f in fixtures if coverage[f["id"]] and utc(f["ko"]) > now),key=priority)[:3]


def roster(lineups, fid, tid, pid):
    if identity(lineups.get("matchId")) != identity(fid):
        return None
    sides = [lineups.get(s) or {} for s in ("home","away")]
    matches = []
    for i, team in enumerate(sides):
        if not tid or identity(team.get("teamId")) != identity(tid) or team.get("status") not in ("confirmed","predicted"):
            continue
        matches.extend((team, player, sides[1-i]) for player in team.get("players",[])
                       if pid and identity(player.get("id")) == identity(pid))
    return matches[0] if len(matches)==1 else None


def flank(player, other_team):
    positions = WIDE_OPPONENT.get(player.get("position"),set())
    if other_team.get("status") not in ("confirmed","predicted"):
        return None
    matches = [p for p in other_team.get("players",[]) if p.get("position") in positions and p.get("id") and p.get("name")]
    return matches[0] if len(matches)==1 else None


def player_sample(reader, player, stat, f, team):
    hist = read_data(reader,"getPlayerStats",dict(playerId=player,statType=stat,
                     competitionId=LEAGUES[f["league"]][0],limit=10,appearances="starts"))
    req = hist.get("requestedStat") or {}
    span = hist.get("span") or {}
    # Only a verified single current club can use a compact aggregate with no club on each row.
    clubs = span.get("teams") or []
    valid_names = {norm(team.get(k)) for k in ("shortName","name") if team.get(k)}
    count = hist.get("games")
    minutes = (hist.get("totals") or {}).get("minutes")
    if (req.get("statType") != stat or len(clubs)!=1 or norm(clubs[0]) not in valid_names or
            type(count) is not int or not 0<count<=10 or not number(minutes) or not minutes or
            not number(req.get("total")) or not span.get("to") or span["to"]>=f["ko"][:10]):
        return None
    return f'{req["total"]:g} {req.get("label") or stat} in {count} current-club league starts ({minutes:g} min)'


def booking_watch(rows, board, now, at):
    # The screen supplies identities; only the fresh, explicitly named bookmaker contract supplies the price.
    # To be booked and yellow-card counts can have different settlement rules. This is a watch only.
    offers = {}
    for market in board.get("markets",[]):
        if market.get("name")!="Player to be Booked": continue
        for entry in market.get("outcomes",[]):
            quote=exact_quote(entry,60-(now-utc(at)).total_seconds()/60)
            if quote and entry.get("label","").endswith(" Over 0.5"):
                if type(entry.get("books")) is int and entry["books"]>=2 and number(entry.get("average")) and entry["average"]>1:
                    quote.update(books=entry["books"],average=entry["average"])
                offers.setdefault(norm(entry["label"][:-9]),[]).append(quote)
    ids={}
    for row in rows:
        ids.setdefault(norm(row.get("playerName","")),set()).add(identity(row.get("playerId")))
    candidates=[]
    for row in rows:
        who=norm(row.get("playerName",""))
        matches=offers.get(who,[])
        if (len(ids[who])!=1 or len(matches)!=1 or not row.get("inPredictedLineup") or not row.get("playerId") or
                not row.get("teamId") or row.get("statType")!="yellowCards" or row.get("line")!=0.5 or row.get("oddsType")!="over"):
            continue
        candidates.append((row,matches[0]))
    # One research example per focused match. Do not rank by historical yield.
    candidates.sort(key=lambda pair:(-(pair[0].get("hitRateL15") or 0),identity(pair[0]["playerId"])))
    if candidates:
        row,q=candidates[0]
        return dict(player=row["playerId"],playerName=row["playerName"],teamId=row["teamId"],stat="yellowCards",
                    label="to be booked",**q)


def recent_other_team(reader, player, name, club, f):
    hist=read_data(reader,"getPlayerStats",dict(playerId=player,statType="fouls",appearances="played",limit=5))
    rows=hist.get("matches") or [dict(zip(hist.get("matchColumns",[]),r)) for r in hist.get("matchRows",[])]
    clubs=(hist.get("span") or {}).get("teams") or []
    same={norm(club[key]) for key in ("name","shortName") if club.get(key)}
    for row in rows:
        team=row.get("team") or (clubs[0] if len(clubs)==1 else None)
        if not team or norm(team) in same or not number(row.get("minutes")) or not row["minutes"]: continue
        try: gap=(date.fromisoformat(f["ko"][:10])-date.fromisoformat(row["date"][:10])).days
        except (ValueError,KeyError,TypeError): continue
        if 0<gap<=3:
            return f'{name}: {row["minutes"]:g} min for {team} on {row["date"][:10]}. Recheck availability.'
    return ""


def context(reader, f, pick):
    fid=f["id"]
    detail=read_data(reader,"getMatchDetails",dict(matchId=fid)).get("data") or {}
    match=detail.get("matches") or {}
    if (identity(match.get("id"))!=identity(fid) or match.get("status")!="scheduled" or
            match.get("kickoffTimestamp")!=int(utc(f["ko"]).timestamp())):
        return "Fixture details unverified."
    xi=read_data(reader,"getLineups",dict(matchId=fid)).get("lineups") or {}
    role=roster(xi,fid,pick["teamId"],pick["player"])
    if not role: return "Starting role unverified. Recheck the official XI."
    team,player,other=role
    clubs={identity(d["id"]):d for k in ("homeTeam","awayTeam") if (d:=detail.get(k)) and d.get("id")}
    if identity(team.get("teamId")) not in clubs or identity(other.get("teamId")) not in clubs: return "Team identity unverified."
    note=[f'{team["status"].capitalize()} {player.get("position") or "starter"}.']
    own=player_sample(reader,pick["player"],pick["stat"],f,clubs[identity(team["teamId"])])
    if own: note.append(own+".")
    else: note.append("Comparable current-club sample unavailable.")
    opp=flank(player,other)
    if opp:
        note.append(f'{other["status"].capitalize()} opposite flank: {opp["name"]} ({opp["position"]}).')
        stat={"yellowCards":"foulsWon","fouls":"foulsWon","foulsWon":"fouls","tackles":"timesDispossessed"}.get(pick["stat"])
        if stat:
            sample=player_sample(reader,opp["id"],stat,f,clubs[identity(other["teamId"])])
            if sample: note.append("Opponent: "+sample+".")
        pick["focusOpponent"]={"id":opp["id"],"teamId":other["teamId"],"position":opp["position"],
                               "playerPosition":player.get("position")}
    else: note.append("Individual opponent unresolved.")
    focus_player=opp or player
    focus_club=clubs[identity((other if opp else team)["teamId"])]
    workload=recent_other_team(reader,focus_player["id"],focus_player["name"],focus_club,f)
    if workload: note.append(workload)
    if pick["stat"]=="yellowCards":
        ref=detail.get("referees") or {}
        if ref.get("id") and match.get("seasonId"):
            refdoc=read_data(reader,"getReferee",dict(refereeId=ref["id"],competitionId=LEAGUES[f["league"]][0],
                                                     seasonId=match["seasonId"],recentGames=10))
            recent=(refdoc.get("record") or {}).get("recentGames") or {}
            figures=recent.get("totals") or {}
            if figures.get("games") and number(figures.get("yellowCardsPerGame")):
                note.append(f'Ref {ref["name"]}: {figures["yellowCardsPerGame"]:g} yellows/game in {figures["games"]} league games this season.')
        elif not ref: note.append("Referee unconfirmed.")
    return " ".join(note)


def add_focus(board, reader, fixtures, prices, clock, board_matches):
    now=utc(clock())
    chosen=select_fixtures(fixtures,board["picks"],prices,now)
    if not chosen: return
    focused = []
    fallback=[f for f in chosen if not any(p.get("player") and p["matchId"]==f["id"] for p in board["picks"])]
    rows=read_data(reader,"getPropScreener",dict(games=[f["id"] for f in fallback],statTypes=["yellowCards"],
                   oddsFrom=1.01,oddsTo=100,hitRateFrom=0,hitRateScope="competition",lineupFilterType="predicted",
                   useSupersub=False,pageSize=40)).get("data",[]) if fallback else []
    for f in chosen:
        picks=[p for p in board["picks"] if p.get("player") and p["matchId"]==f["id"]]
        p=picks[0] if picks else None
        if p is None:
            quote=reader.read("getMatchOdds",dict(matchId=f["id"],markets=["player to be booked"]),"focus")
            if quote and board_matches(f,quote["data"]):
                p=booking_watch([r for r in rows if identity(r.get("matchId"))==identity(f["id"])],quote["data"],utc(clock()),quote["at"])
        match_name=f['home']+" v "+f['away']
        if p is None:
            focused.append(match_name+" — no identifiable, freshly priced player matchup to review.")
            continue
        detail=context(reader,f,p)
        if picks:
            p["risk"]+=" Matchup review: "+detail
            focused.append(match_name+" — see "+p["playerName"]+" in the shortlist.")
        else:
            comparison=(f' Same-line board average {p["average"]:.2f} across {p["books"]} books.' if "average" in p else "")
            focused.append(f'{match_name} — watch only: {p["playerName"]} {p["label"]} at {p["odds"]:.2f} {p["book"]} ({p["age"]:g} min old when checked).{comparison} {detail}')
            board.setdefault("focusWatch",[]).append({**p,"matchId":f["id"],"fixture":f,"observedAt":quote["at"]})
    board["focus"]=focused
    board["coverage"]+="\nMatchup review · formation-based, no measured heatmap.\n"+"\n".join(focused)
    board["coverage"]+=f"\n{len(reader.log)}/{reader.limit} matchup reads."


def opponent_recheck(p, doc):
    expected=p.get("focusOpponent")
    if not expected: return ""
    role=roster(doc.get("lineups") or {},p["matchId"],p["teamId"],p["player"])
    if not role or any(s.get("status")!="confirmed" or len({identity(a.get("id")) for a in s.get("players",[]) if a.get("id")})!=11 for s in (role[0],role[2])):
        return " Opponent matchup still provisional."
    other=flank(role[1],role[2])
    valid=(other and identity(other["id"])==identity(expected["id"]) and
           role[1].get("position")==expected["playerPosition"] and other.get("position")==expected["position"] and
           identity(role[2].get("teamId"))==identity(expected["teamId"]))
    return " Both named flank roles confirmed." if valid else " Morning flank matchup changed or is unresolved. Disregard that matchup note."


def recheck_watches(board, reader, now, clock, board_matches):
    for p in board.get("focusWatch",[]):
        mins=(utc(p["fixture"]["ko"])-now).total_seconds()/60
        tries=p.get("checks",0)
        if not 0<mins<=57 or tries>=2 or p.get("closed") or (tries==1 and (mins>30 or (now-utc(p["checkedAt"])).total_seconds()<300)):
            continue
        fid=p["matchId"]
        slot=now.strftime("%H:%M")
        snap=reader.read("getMatchOdds",dict(matchId=fid,markets=["player to be booked"]),slot)
        xi=reader.read("getLineups",dict(matchId=fid),slot)
        quote=None
        if snap and board_matches(p["fixture"],snap["data"]):
            identical=[o for m in snap["data"].get("markets",[]) if m.get("name")=="Player to be Booked"
                       for o in m.get("outcomes",[]) if o.get("label","").endswith(" Over 0.5") and norm(o["label"][:-9])==norm(p["playerName"])]
            if len(identical)==1: quote=exact_quote(identical[0],30-(utc(clock())-utc(snap["at"])).total_seconds()/60)
        doc=(xi or {}).get("data",{})
        lineups=doc.get("lineups") or {}
        sides=[s for k in ("home","away") if (s:=lineups.get(k)) and identity(s.get("teamId"))==identity(p["teamId"])]
        named=None
        if identity(lineups.get("matchId"))==identity(fid) and len(sides)==1 and sides[0].get("status")=="confirmed":
            ids={identity(a.get("id")) for a in sides[0].get("players",[]) if a.get("id")}
            if len(ids)==11: named=identity(p["player"]) in ids
        p.update(checks=tries+1,checkedAt=clock())
        if utc(p["checkedAt"])>=utc(p["fixture"]["ko"]): detail="Verification finished after kickoff."
        elif named is False:
            detail="Outside official XI."; p["closed"]=True
        else:
            role_note=opponent_recheck(p,doc)
            detail=("Official starter." if named else "Official XI pending.")+role_note
            detail+=f' Same line {quote["odds"]:.2f} {quote["book"]}.' if quote else " Fresh same-line quote unavailable."
            p["closed"]=bool(named and quote and "provisional" not in role_note)
        p["checkNote"]=detail
    summaries=[f'{p["playerName"]} at {p["checkedAt"][11:16]} UK: {p["checkNote"]}' for p in board.get("focusWatch",[]) if p.get("checkNote")]
    if summaries:
        marker="\nWatch rechecks (still research only)\n"
        board["coverage"]=board["coverage"].partition(marker)[0]+marker+"\n".join(summaries)
