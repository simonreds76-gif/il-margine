"""Whole-match contract identities and the prospective notification rule."""
import hashlib
import json
import math
from datetime import datetime, timedelta


def contracts(sample):
    """Canonical player order makes home/away reordering harmless. Lines are signed."""
    named = [sample["home"], sample["away"]]
    first, second = sorted(named)
    lines = {}
    for market in ("spreads", "totals"):
        for raw, odds in sample[market].items():
            line = float(raw)
            if not (line * 4).is_integer():
                continue
            prices = list(odds)
            if market == "spreads" and first != named[0]:
                line = -line
                prices.reverse()
            line = line or 0.0
            labels = ([f"{first} {line:+g} games", f"{second} {-line:+g} games"]
                      if market == "spreads" else [f"Over {line:g} games", f"Under {line:g} games"])
            code = f"{market}:{line:g}"
            lines[code] = {"market":market, "line":line, "labels":labels, "prices":prices}
    return lines


def pairs(row):
    first, second = sorted((row["home"], row["away"]))
    ml = [row["home_price"], row["away_price"]]
    if first != row["home"]:
        ml.reverse()
    yield "winner", {"market":"winner", "labels":[first, second], "prices":ml}
    yield from row.get("contracts", {}).items()


def compare(last, current, state, blocked):
    """Small moves stay on the board. Alert once per exact contract side at +4pp."""
    from price_drop_watch import observe
    batch = observe(None, current)
    batch.update(before=last.get("observed"), policy="same-line-4pp-prematch-v1", alert_ids=[])
    now = datetime.fromisoformat(current["observed"])
    history = {k:v for k,v in last.get("desk_windows",{}).items() if datetime.fromisoformat(v["start"]) > now}
    # Retain issued identities across gaps, temporary withdrawals and pre-start reschedules.
    issued = {k:t for k,t in last.get("desk_issued",{}).items() if datetime.fromisoformat(t) + timedelta(days=7) > now}
    for eid,row in state["events"].items():
        if row["fixture"] in blocked:
            continue
        first, second = sorted((row["home"], row["away"]))
        for code, pair in pairs(row):
            k = "|".join((eid, row["fixture"], row["start"], code))
            old = history.get(k)
            prices = pair["prices"]
            point = [current["observed"], *prices]
            peaks = list(old["peaks"]) if old else [point, point]
            for side in (0,1):
                if prices[side] > peaks[side][side+1]:
                    peaks[side] = point
            history[k] = {"start":row["start"], "last":point, "peaks":peaks}
            if not old:
                continue
            if code == "winner":
                batch["compared_pairs"] += 1
            for i, price in enumerate(prices):
                if price >= old["last"][1+i]:
                    continue
                contract = "|".join((row["fixture"], code, str(i)))
                peak = old["peaks"][i]
                qualifies = contract not in issued and 100*(1/price - 1/peak[1+i]) >= 4-1e-10
                reference = peak if qualifies else old["last"]
                before, old_price, old_other = reference[0], reference[1+i], reference[2-i]
                p, old_p = prices[1-i]/sum(prices), old_other/(old_price+old_other)
                mid = hashlib.sha256(json.dumps([k,i,current["observed"]]).encode()).hexdigest()[:32]
                # Real players are always preserved for exact result binding, including totals.
                player, opponent = (second,first) if i and pair["market"] != "totals" else (first,second)
                move = dict(move_id=mid,fixture=row["fixture"],event_id=eid,tour=row["tour"],league=row["league"],
                            player=player,opponent=opponent,start=row["start"],before=before,after=current["observed"],
                            old=old_price,new=price,old_opponent=old_other,new_opponent=prices[1-i],old_p=old_p,
                            new_p=p,move_pp=round(100*(p-old_p),6),both_shortened=prices[1-i]<old_other,
                            result="Pending",profit=None,score=None,market=pair["market"],contract=code,side=i,
                            selection=pair["labels"][i],opposite=pair["labels"][1-i])
                if code != "winner":
                    move["line"] = -pair["line"] if i and pair["market"]=="spreads" else pair["line"]
                batch["moves"].append(move)
                if qualifies:
                    batch["alert_ids"].append(mid)
                    issued[contract] = row["start"]
    state.update(desk_windows=history, desk_issued=issued)
    return batch


def grade(ticket, sets, selected_won):
    """Sets contain only completed winner-first game scores. A breaker counts as one game."""
    winner_games = sum(x for x,y in sets)
    loser_games = sum(y for x,y in sets)
    margin = (winner_games-loser_games) * (1 if selected_won else -1)
    line = ticket["line"]
    legs = [line] if (float(line)*2).is_integer() else [math.floor(line*2)/2, math.ceil(line*2)/2]
    def leg_value(h):
        if ticket["market"] == "spreads":
            return margin+h
        return (winner_games+loser_games-h) * (1 if ticket["side"]==0 else -1)
    grades = [leg_value(h) for h in legs]
    wins = sum(x>0 for x in grades)/len(grades)
    losses = sum(x<0 for x in grades)/len(grades)
    result = ("Won" if wins==1 else "Lost" if losses==1 else "Half won" if wins else
              "Half lost" if losses else "Push")
    return {"result":result, "profit":round(wins*(ticket["new"]-1)-losses,8),"settled_stake":1}
