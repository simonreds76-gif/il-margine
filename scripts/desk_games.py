"""Whole-match contract identities and the prospective notification rule."""
import hashlib
import json
import math
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction

PRIOR_ALL_DAY_POLICY = "same-line-over4pp-prematch-limits-shown-v3"
PRIOR_LINE_POLICY = "same-line-over4pp-prematch-min200usd-v4"
PRIOR_MATCH_POLICY = "first-match-over4pp-prematch-min200usd-v5"
PRIOR_PREMATCH_500_POLICY = "first-match-over4pp-prematch-min500usd-v6"
PRIOR_TWO_HOUR_POLICY = "first-match-over4pp-final2h-min500usd-v7"
ALERT_POLICY = "first-match-over4pp-final5h-min500usd-v8"
ALERT_WINDOW = timedelta(hours=5)
ALERT_MINIMUM_USD = 500
PAPER_MINIMUM_USD = 200
FINAL_HOUR = timedelta(hours=1)


def crosses_threshold(earlier, later):
    return 100 * (1 / later - 1 / earlier) >= 4 - 1e-10


def alert_crossing(earlier, later):
    # Strictly over four probability points, without rounding a boundary into a signal.
    a, b = Decimal(str(earlier)), Decimal(str(later))
    return 100 * (a - b) > 4 * a * b


def market_limit(row, contract):
    # Spreads and totals vary by line. Only the match-winner cap applies to both ML sides.
    limit = contract.get("reported_market_max")
    if limit is None and contract["market"] == "winner":
        meta = row.get("match_period_limits", {})
        amount = meta.get("max_money_line", meta.get("max_moneyline"))
        limit = {"amount": amount}
    if not isinstance(limit, dict):
        return None
    amount = limit.get("amount")
    if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
        return None
    currency = limit.get("currency", "USD")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        return None
    return {"amount": amount, "currency": currency}


def meets_usd_floor(limit, minimum):
    if not isinstance(limit, dict) or limit.get("currency") != "USD":
        return False
    amount = limit.get("amount")
    return type(amount) in (int, float) and math.isfinite(amount) and amount >= minimum


def match_rank(move):
    """Same-scan ranking shared by Telegram and the one-unit match record."""
    old, new = (Fraction(str(move[k])) for k in ("old", "new"))
    if not old > new > 1:
        raise ValueError("Invalid odds for a qualifying move")
    return (-(1/new - 1/old), move["contract"], move["side"], move.get("sent", ""))


def strongest_by_match(moves):
    chosen = {}
    for move in moves:
        fixture = move["fixture"]
        if fixture not in chosen or match_rank(move) < match_rank(chosen[fixture]):
            chosen[fixture] = move
    return list(chosen.values())


def seed_match_alerts(last):
    """Carry over earlier per-line reservations, including uncertain deliveries."""
    matches = {}
    for ident,start in last.get("desk_late_issued",last.get("desk_issued",{})).items():
        fixture = ident.rsplit("|", 2)[0]
        if fixture not in matches or datetime.fromisoformat(start)>datetime.fromisoformat(matches[fixture]):
            matches[fixture] = start
    return matches


def alert_moves(batch):
    """A retry can read a batch created before the Telegram policy changed."""
    if batch.get("policy") != ALERT_POLICY:
        return []
    observed = datetime.fromisoformat(batch["observed"])
    wanted = set(batch["alert_ids"])
    moves = []
    for move in batch["moves"]:
        if move["move_id"] in wanted and meets_usd_floor(move.get("alert_detection_limit"), ALERT_MINIMUM_USD):
            start, before, after = (datetime.fromisoformat(move[key]) for key in ("start", "before", "after"))
            if after == observed and start - ALERT_WINDOW <= before < after < start and alert_crossing(move["old"], move["new"]):
                moves.append(move)
    return strongest_by_match(moves)


def dispatch_moves(batch, store):
    """An old fixture can reappear after a reschedule or a cache rebuild."""
    winners = alert_moves(batch)
    if not winners:
        return []
    record = store.get("presentation/drop-paper-v1/first-match-v1/state.json")
    if not record or not isinstance(record.get("locks", {}).get("telegram"), dict):
        raise RuntimeError("Missing confirmed match record for Telegram deduplication")
    confirmed = record["locks"]["telegram"]
    # Let the existing immutable per-scan receipt handle a retry of its own move.
    return [m for m in winners if m["fixture"] not in confirmed
            or confirmed[m["fixture"]]["move_id"] == m["move_id"]]


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
            limit = sample.get("limits", {}).get(market, {}).get(raw)
            if limit is not None:
                lines[code]["reported_market_max"] = limit
    return lines


def pairs(row):
    first, second = sorted((row["home"], row["away"]))
    ml = [row["home_price"], row["away_price"]]
    if first != row["home"]:
        ml.reverse()
    winner = {"market":"winner", "labels":[first, second], "prices":ml}
    if "reported_market_max" in row:
        winner["reported_market_max"] = row["reported_market_max"]
    yield "winner", winner
    yield from row.get("contracts", {}).items()


def compare(last, current, state, blocked):
    """Keep every board move; reserve the strongest eligible line on a match's first scan."""
    from price_drop_watch import observe
    batch = observe(None, current)
    batch.update(before=last.get("observed"), policy=ALERT_POLICY, alert_ids=[], compared_by_circuit={"ATP": 0, "WTA": 0})
    now = datetime.fromisoformat(current["observed"])
    history = {k:v for k,v in last.get("desk_windows",{}).items() if datetime.fromisoformat(v["start"]) > now}
    # Retain issued identities across gaps, temporary withdrawals and pre-start reschedules.
    issued = {k:t for k,t in last.get("desk_issued",{}).items() if datetime.fromisoformat(t) + timedelta(days=7) > now}
    # Grandfather existing signals on migration. New early board moves never consume a late alert.
    alerted = {k:t for k,t in last.get("desk_late_issued", issued).items()
                   if datetime.fromisoformat(t) + timedelta(days=7) > now}
    # Old per-line reservations also cover deliveries with an uncertain response.
    # Keep a postponed fixture locked while it is still present on the board.
    previous_matches = last.get("desk_match_issued")
    if previous_matches is None:
        previous_matches = seed_match_alerts(last)
    match_issued = dict(previous_matches)
    for row in state["events"].values():
        fixture = row["fixture"]
        if fixture in match_issued and datetime.fromisoformat(match_issued[fixture]) + timedelta(days=7) > now:
            if datetime.fromisoformat(row["start"])>datetime.fromisoformat(match_issued[fixture]):
                match_issued[fixture] = row["start"]
    match_issued = {f:s for f,s in match_issued.items() if datetime.fromisoformat(s)+timedelta(days=7)>now}
    eligible = []
    for eid,row in state["events"].items():
        if row["fixture"] in blocked:
            continue
        start = datetime.fromisoformat(row["start"])
        window_start = start - ALERT_WINDOW
        first, second = sorted((row["home"], row["away"]))
        for code, pair in pairs(row):
            k = "|".join((eid, row["fixture"], row["start"], code))
            old = history.get(k)
            prices = pair["prices"]
            limit = market_limit(row, pair)
            point = [current["observed"], *prices, limit]
            peaks = list(old["peaks"]) if old else [point, point]
            for side in (0,1):
                if prices[side] > peaks[side][side+1]:
                    peaks[side] = point
            history[k] = {"start":row["start"], "last":point, "peaks":peaks}
            alert_refs = None
            if window_start <= now < start:
                if old and old["last"][0] == last.get("observed"):
                    previous_time = datetime.fromisoformat(old["last"][0])
                    adjacent = int(now.timestamp()) // 900 - int(previous_time.timestamp()) // 900 == 1
                    if adjacent and window_start <= previous_time < now and now - previous_time <= timedelta(minutes=20):
                        # At cutover the narrower saved peaks are valid inside five hours.
                        # Otherwise seed from the adjacent scan, never the all-day peak.
                        alert_refs = old.get("final_five_hour_peaks") or old.get("final_two_hour_peaks") or [old["last"], old["last"]]
                history[k]["final_five_hour_peaks"] = [
                    alert_refs[i] if alert_refs and alert_refs[i][i+1] > prices[i] else point for i in (0, 1)
                ]
            if not old:
                continue
            if code == "winner":
                batch["compared_pairs"] += 1
                circuit = "WTA" if row["tour"] in ("WTA", "WTA 125") else "ATP"
                batch["compared_by_circuit"][circuit] += 1
            for i, price in enumerate(prices):
                if price >= old["last"][1+i]:
                    continue
                contract = "|".join((row["fixture"], code, str(i)))
                peak = old["peaks"][i]
                board_crossing = contract not in issued and crosses_threshold(peak[1+i], price)
                if board_crossing:
                    issued[contract] = row["start"]
                qualifies = (alert_refs is not None and contract not in alerted
                             and meets_usd_floor(limit, ALERT_MINIMUM_USD)
                             and alert_crossing(alert_refs[i][1+i], price))
                reference = peak if board_crossing else old["last"]
                if qualifies:
                    reference = alert_refs[i]
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
                if "reported_market_max" in pair:
                    move["reported_market_max_at_detection"] = pair["reported_market_max"]
                batch["moves"].append(move)
                if qualifies:
                    move["alert_reference_limit"] = reference[3]
                    move["alert_detection_limit"] = limit
                    move["detected_in_final_hour"] = start - FINAL_HOUR <= now
                    move["wholly_in_final_hour"] = start - FINAL_HOUR <= datetime.fromisoformat(before)
                    move["alert_policy"] = ALERT_POLICY
                    if row["fixture"] not in match_issued:
                        eligible.append(move)
                    alerted[contract] = row["start"]
    for winner in strongest_by_match(eligible):
        batch["alert_ids"].append(winner["move_id"])
        match_issued[winner["fixture"]] = winner["start"]
    state.update(desk_windows=history, desk_issued=issued, desk_late_issued=alerted, desk_match_issued=match_issued)
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
