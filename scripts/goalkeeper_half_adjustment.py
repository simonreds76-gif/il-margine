"""Forward-only paired comparison, using the GK poll's validated input packets."""
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import math
from statistics import mean

from football_identity import read, write
from goalkeeper_forecast_evidence import timestamp
from goalkeeper_keeper_watch import digest, identity, load_records, retain, targets
from goalkeeper_price_selection import normalized
from goalkeeper_quote_integrity import current_quote_issue, verified_quote
from goalkeeper_saves_live import predict_mean, price_side

ARMS = ("current", "half")
START = datetime(2026, 11, 17, 18, 55, tzinfo=UTC)
PARAM_HASH = "74a1630cb8e82b0e847df1a912101a7a2b9af6b36db7e08618e324d3efd7b189"
STAKE = 0.5


def offer(row, params, now):
    raw = row.get("_research_quote") or {}
    observed = timestamp((row.get("_research_lineup") or {}).get("observed_at"))
    captured = timestamp(raw.get("captured_at"))
    kickoff = timestamp(raw.get("kickoff_at"))
    ids = identity(row)
    if (not ids or not ids["player_id"].isdigit() or not observed or observed > now
            or not captured or not timedelta(0) <= now-captured <= timedelta(minutes=10)
            or captured != timestamp(row.get("captured_at")) or captured < START
            or not kickoff or not now < kickoff or kickoff != timestamp(row.get("kickoff_at"))
            or row.get("contract_scope") != "named_player" or row.get("blockers")
            or row.get("candidate_status") == "blocked" or current_quote_issue(raw)
            or row.get("lineup_status") not in ("confirmed_starter", "predicted_starter")
            or row.get("side") != "over" or raw.get("side") != "over"
            or str(raw.get("event_id")) != str(row.get("event_id"))
            or not row.get("bookmaker") or raw.get("bookmaker") != row["bookmaker"]
            or not row.get("_research_features")):
        return None
    if normalized(raw.get("player")) != normalized(row["goalkeeper"]) and not verified_quote(row):
        return None
    line, odds = float(raw["line"]), float(raw["odds_decimal"])
    if (line != float(row["line"]) or line < .5 or line % 1 != .5
            or not math.isfinite(odds) or odds <= 1 or odds != float(row["odds_decimal"])):
        return None
    venue, league = row["venue"], row["league"]
    current = predict_mean(params, row["_research_features"], league, venue)
    center = params["league_venue_means"][league+"|"+venue]
    models = {}
    for arm, mu in (("current", current), ("half", (current+center)/2)):
        price = price_side("over", line, odds, mu, params["alpha"])
        models[arm] = dict(mu=mu, p=price["model_probability"], edge=price["edge"],
                           p4=price_side("over", 3.5, 2., mu, params["alpha"])["model_probability"])
    if (abs(float(row["model_mean"])-current) > .000051
            or abs(float(row["model_probability"])-models["current"]["p"]) > .00000051):
        raise ValueError("Issued goalkeeper forecast did not reproduce")
    if (1.7<=odds<=3 and models["current"]["edge"]>=.05) != (row["candidate_status"]=="eligible_shadow"):
        raise ValueError("Issued eligibility did not reproduce")
    return dict(**ids, venue=venue, league=league, keeper=row["goalkeeper"], home=row["home_team"],
                away=row["away_team"], kickoff=kickoff.isoformat(), captured=captured.isoformat(),
                bookmaker=row["bookmaker"], line=line, odds=odds, models=models)


def freeze(rows, at):
    # Only compare identical player/line contracts from each book's latest poll.
    latest = {book:max(r["captured"] for r in rows if r["bookmaker"]==book)
              for book in {r["bookmaker"] for r in rows}}
    best = {}
    for r in rows:
        if r["captured"] != latest[r["bookmaker"]]:
            continue
        key = (r["venue"], r["player_id"], r["line"])
        prev = best.get(key)
        if prev is None or (r["odds"], r["bookmaker"]=="Bet365") > (prev["odds"], prev["bookmaker"]=="Bet365"):
            best[key] = r
    sides = {}
    for venue in ("home","away"):
        people = [r for r in rows if r["venue"]==venue]
        if len({(r["player_id"],r["team_id"],r["models"]["current"]["mu"]) for r in people}) != 1:
            return None
        sides[venue] = people[0]
    if (len({r["kickoff"] for r in rows}) != 1 or len({r["league"] for r in rows}) != 1
            or len({r["team_id"] for r in sides.values()}) != 2
            or len({r["player_id"] for r in sides.values()}) != 2):
        return None
    picks = {}
    for arm in ARMS:
        eligible = [r for r in best.values() if 1.7<=r["odds"]<=3. and r["models"][arm]["edge"]>=.05]
        picks[arm] = min(eligible, key=lambda r:(abs(r["odds"]-2), -r["models"][arm]["p"],
                        -r["models"][arm]["edge"], r["player_id"], r["line"])) if eligible else None
    return dict(match_id=rows[0]["match_id"], kickoff=rows[0]["kickoff"], registered_at=at.isoformat(),
                sides=sides, picks=picks, offers=list(best.values()), parameter_hash=PARAM_HASH, actual_stake=0)


def verified_counts(board, result):
    if not result:
        return None, "awaiting_result"
    if result.get("conflict") or not result.get("full_match_agreement"):
        return None, "incomplete_or_conflicting_result"
    if timestamp(result["kickoff"]) != timestamp(board["kickoff"]) or result["league"] != board["sides"]["home"]["league"]:
        return None, "fixture_mismatch"
    saves = {}
    for side, row in board["sides"].items():
        people = [k for k in result["keepers"] if str(k["player_id"])==row["player_id"] and str(k["team_id"])==row["team_id"]]
        if len(people)!=1 or not people[0]["started"] or people[0]["minutes"]!=90:
            return None, "starting_keeper_mismatch"
        actual = people[0]["saves"]
        if type(actual) is not int or actual < 0 or actual != people[0].get("event_saves"):
            return None, "unverified_save_total"
        saves[side] = actual
    return saves, None


def summarize(boards, results, at, folder):
    scores = defaultdict(list)
    picks = defaultdict(list)
    holds = Counter()
    settled = 0
    for b in sorted(boards,key=lambda x:(x["kickoff"],x["match_id"])):
        mid = b["match_id"]
        actual, reason = verified_counts(b, results.get(mid))
        if actual is None:
            holds[reason] += 1
            continue
        path = folder/"outcomes"/(sha256(mid.encode()).hexdigest()+".json")
        prior = read(path)
        if prior and prior["saves"] != actual:
            holds["changed_verified_result"] += 1
            continue
        retain(folder/"outcomes", mid, dict(match_id=mid, saves=actual, observed_at=at.isoformat(),
                                           source_hash=results[mid]["source_hash"]))
        settled += 1
        for arm in ARMS:
            for venue, side in b["sides"].items():
                scores[arm].append((side["models"][arm]["p4"],int(actual[venue]>=4)))
            pick = b["picks"][arm]
            if pick:
                won = actual[pick["venue"]]>pick["line"]
                pnl = STAKE*(pick["odds"]-1) if won else -STAKE
                picks[arm].append(dict(id=mid,date=b["kickoff"][:10],won=won,pnl=pnl))
    arms = {}
    for arm in ARMS:
        bets = picks[arm]
        stake = STAKE*len(bets)
        pnl = sum(r["pnl"] for r in bets)
        pairs = scores[arm]
        selected = sum(b["picks"][arm] is not None for b in boards)
        arms[arm] = dict(settled=len(bets), pending=selected-len(bets), no_bets=len(boards)-selected,
                         wins=sum(r["won"] for r in bets), losses=sum(not r["won"] for r in bets),
                         stake_units=stake, pnl_units=pnl, roi_pct=100*pnl/stake if stake else None,
                         brier=mean((p-y)**2 for p,y in pairs) if pairs else None,
                         log_loss=mean(-math.log(max(1e-15,p if y else 1-p)) for p,y in pairs) if pairs else None,
                         predicted=mean(p for p,y in pairs) if pairs else None,
                         observed=mean(y for p,y in pairs) if pairs else None, n=len(pairs), bets=bets)
    return dict(arms=arms, fixtures=len(boards), paired_settled_fixtures=settled, holds=dict(holds),
                generated_at=at.isoformat(), start_at=START.isoformat(), actual_stake=0,
                status="TRACKING" if boards else "AWAITING_FIRST_VERIFIED_BOARD")


def run(root, packets, now=None):
    at = now or datetime.now(UTC)
    folder = root/"data/goalkeeper-saves/half-adjustment-v1"
    groups = defaultdict(list)
    issued = defaultdict(list)
    reasons = Counter()
    for path in sorted(set(packets)):
        d = read(path)
        reg = timestamp(d["registered_at"])
        if not reg or not START<=reg<=at or at-reg>timedelta(minutes=10) or timestamp(d["kickoff_at"])<=at:
            continue
        expected = {k:v for k,v in d.items() if k not in ("registered_at","payload_sha256")}
        if path.stem!=digest(expected) or path.stem!=d["payload_sha256"] or digest(d["model_params"])!=PARAM_HASH:
            raise ValueError("Frozen keeper parameters or packet integrity changed")
        newest = {}
        for row in d["offers"]:
            observed = timestamp(row.get("captured_at"))
            book = row.get("bookmaker")
            if observed and observed<=at:
                newest[book] = max(observed,newest.get(book,observed))
        for row in d["offers"]:
            if str(row.get("event_id"))!=str(d["event_id"]) or timestamp(row.get("kickoff_at"))!=timestamp(d["kickoff_at"]):
                raise ValueError("Keeper packet fixture mismatch")
            mid = str((row.get("_research_lineup") or {}).get("fotmob_match_id") or "")
            if row.get("strongest_for_fixture") == "yes":
                issued[mid].append((row["bookmaker"],row["goalkeeper"],float(row["line"]),float(row["odds_decimal"])))
            if timestamp(row.get("captured_at")) != newest.get(row.get("bookmaker")):
                reasons["superseded_book_board"] += 1
                continue
            try:
                r = offer(row,d["model_params"],at)
            except (ValueError,TypeError,KeyError,ArithmeticError):
                # An unreproduced offer invalidates this fixture's board.
                # Other verified fixtures in the same poll can still register.
                issued[mid].append(("input_parity_hold",))
                reasons["offer_integrity_failure"] += 1
                continue
            if r:
                r["input_packet"] = path.stem
                groups[r["match_id"]].append(r)
            else:
                reasons["ineligible_contract_or_input"] += 1
    for mid, rows in groups.items():
        board = freeze(rows,at)
        if board:
            pick = board["picks"]["current"]
            control = [(pick["bookmaker"],pick["keeper"],pick["line"],pick["odds"])] if pick else []
            if issued[mid] == control:
                retain(folder/"forecasts",mid,board)
            else:
                reasons["issued_selection_did_not_reproduce"] += 1
        else:
            reasons["unverified_two_keeper_board"] += 1
    boards = load_records(folder/"forecasts")
    results = targets(root,at)[0] if boards else {}
    report = summarize(boards,results,at,folder)
    report["scan_exclusions"] = dict(reasons)
    write(folder/"report.json",report)
    return report


def weekly_text(report):
    report = report or {}
    parts = []
    for key,label in (("current","Current"),("half","Half adjustment")):
        arm = (report.get("arms") or {}).get(key,{})
        def metric(field, fmt):
            value = arm.get(field)
            return format(value,fmt) if value is not None else "—"
        roi = f"{arm['roi_pct']:+.1f}%" if arm.get("roi_pct") is not None else "pending"
        parts.append(f"{label} {arm.get('wins',0)}W/{arm.get('losses',0)}L, {metric('pnl_units','+.2f')}u"
                     f" on {metric('stake_units','.1f')}u, ROI {roi},"
                     f" Brier {metric('brier','.4f')}, log loss {metric('log_loss','.4f')}")
    return f"GK half adjustment · {report.get('status','AWAITING_REPORT')} · {report.get('paired_settled_fixtures',0)}/{report.get('fixtures',0)} paired fixtures settled · " + " | ".join(parts)
