"""Prepare and deliver one private morning edition from completed fixture reviews."""
import os
import sys
import time
from datetime import datetime, timedelta

from johnny_cards import FLOOR, JohnnyProvider, distinct_opponent, edition_key, offers, private_store
from johnny_cards_calendar import LONDON, senior_fixture
from statshub_daily_board import LINK, REPORT, Reads
from statshub_daily_contracts import identity, norm, utc
from statshub_daily_io import send_digest, timestamp


def candidates(f):
    decisions = {d["index"]: d for d in (f.get("assessment") or {}).get("cases", [])}
    for i, case in enumerate(f.get("cases", [])):
        decision = decisions.get(i, {})
        for kind, verdict, model, bounds in (
            ("booking", "verdict", "booking", "bookingRange"),
            ("fouls", "foulsVerdict", "fouls", "foulsRange"),
        ):
            # Older editions recorded an otherwise qualifying expected starter as WATCH.
            held = case.get(verdict) == "WATCH" and case.get("lineup") == "predicted"
            if case.get(verdict) != "BET" and not (held and decision.get(model) == "BET"):
                continue
            line = "0.5" if kind == "booking" else decision.get("foulLine")
            old = case.get("booking") if kind == "booking" else next(
                (o for o in case["offers"] if o["kind"] == kind and str(o["line"]) == line), None)
            interval = case.get(bounds) or {}
            if old and old.get("rules") and interval.get("low") and interval.get("evLow", 0) > 0:
                yield case, kind, old, interval["low"]


def starting_role(f, case, xi):
    side = case["side"]
    own = xi.get(side) or {}
    if identity(own.get("teamId")) != identity(f["teams"][side]["id"]) or own.get("status") not in ("predicted", "confirmed"):
        return False
    players = [p for p in own.get("players", []) if identity(p.get("id")) == identity(case["player"]["id"])]
    if not case["player"].get("id") or len(players) != 1 or not players[0].get("position") or players[0]["position"] != case["player"].get("position"):
        return False
    if case.get("rival"):
        opp = "away" if side == "home" else "home"
        other = xi.get(opp) or {}
        if other.get("status") not in ("predicted", "confirmed") or identity(other.get("teamId")) != identity(f["teams"][opp]["id"]):
            return False
        rival = distinct_opponent(players[0], other)
        if not rival or identity(rival.get("id")) != identity(case["rival"]["id"]):
            return None
    return (own["status"], (other["status"] if case.get("rival") else None))


def recheck(reader, f, now):
    slot = "edition-" + now.strftime("%H%M")
    def read(tool, **extra):
        return reader.read(tool, dict(matchId=f["id"], **extra), slot) or {}

    result = dict(verdictAt=f["verdictAt"], checkedAt=now.isoformat(), picks=[], notes=[])
    details = ((read("getMatchDetails").get("data") or {}).get("data") or {})
    match = details.get("matches") or {}
    if (match.get("status") != "scheduled" or identity(match.get("id")) != identity(f["id"])
        or match.get("kickoffTimestamp") != int(utc(f["ko"]).timestamp()) or utc(f["ko"]) <= now
        or identity((details.get("competition") or {}).get("competitionId")) != identity(f["competitionId"])
        or any(identity((details.get(s+"Team") or {}).get("id")) != identity(f["teams"][s]["id"]) for s in ("home","away"))):
        result["notes"].append("fixture or scheduled start unverified")
        return result
    packet = read("getLineups")
    if not packet:
        result["notes"].append("lineup lookup failed")
        return result
    xi = (packet.get("data") or {}).get("lineups") or {}
    if xi.get("available") is False:
        result["notes"].append("no expected or confirmed XI published")
        return result
    if identity(xi.get("matchId")) != identity(f["id"]):
        result["notes"].append("lineups unavailable")
        return result
    eligible = []
    for case, kind, old, low in candidates(f):
        role = starting_role(f, case, xi)
        if role:
            eligible.append((case, kind, old, low, role))
        else:
            result["notes"].append("player, role or direct opponent has changed or is missing")
    if eligible:
        board = read("getMatchOdds", markets=["player to be booked","player fouls"])
        if not board.get("at"):
            result["notes"].append("odds unavailable")
            return result
        for case, kind, old, low, role in eligible:
            fresh = [q for q in offers(board["data"], f, case, board["at"], utc(board["at"]))
                     if q["kind"] == kind and q["line"] == old["line"] and norm(q["book"]) == norm(old["book"])]
            if len(fresh) != 1:
                result["notes"].append("exact bookmaker or line unavailable")
                continue
            q = fresh[0]
            if q["age"] > 60 or (kind == "booking" and q["odds"] < FLOOR) or low*q["odds"] <= 1:
                result["notes"].append("odds outside the accepted range or age")
                continue
            result["picks"].append(dict(player=case["name"], playerId=case["player"]["id"], lineup=role[0], opponentLineup=role[1], **q))
    result["notes"] = sorted(set(result["notes"]))
    return result


def verify(store, day, reader, clock=timestamp, *, research_part="research", checks_part="checks"):
    snapshot = store.get(edition_key(day,research_part), {})
    checks_path = edition_key(day,checks_part)
    checks = store.get(checks_path, {})
    for f in snapshot.get("slate", []):
        if not senior_fixture(f) or f.get("reviewState") != "complete" or not any(candidates(f)):
            continue
        now = utc(clock())
        prior = checks.get(f["id"], {})
        if prior.get("verdictAt") == f["verdictAt"] and now - utc(prior["checkedAt"]) < timedelta(minutes=20):
            continue
        try:
            checks[f["id"]] = recheck(reader, f, now)
        except (ValueError, TypeError, KeyError, IndexError, TimeoutError):
            checks[f["id"]] = dict(verdictAt=f["verdictAt"], checkedAt=now.isoformat(),
                                   picks=[], notes=["final verification incomplete"])
        store.put(checks_path, checks)


def make_digest(day, snapshot, checks, now):
    picks, pending, reserve, unavailable, detail = [], [], [], [], []
    complete = 0
    slate = [f for f in snapshot.get("slate", []) if senior_fixture(f)]
    for f in slate:
        name = f["home"] + " v " + f["away"]
        state = f.get("reviewState")
        if state == "reserve":
            reserve.append(name)
        elif state == "unfinished" or (state == "unavailable" and
                str(f.get("gap", "")).startswith("Player assessment incomplete (")):
            step = f.get("reviewStep") or "player assessment"
            pending.append(f"{name} ({step} incomplete)")
        elif state == "unavailable":
            unavailable.append(name + " (" + f.get("gap", "evidence unavailable") + ")")
        elif state != "complete":
            pending.append(name + (" (player screen saved)" if "playerScreen" in f else ""))
        else:
            complete += 1
            if utc(f["ko"]) <= now:
                detail.append(name + " · scheduled kickoff passed")
                continue
            if not any(candidates(f)):
                detail.append(name + " · no qualifying booking or foul")
                continue
            check = checks.get(f["id"], {})
            if (check.get("verdictAt") != f.get("verdictAt") or not check.get("checkedAt") or
                not timedelta(0) <= now - utc(check["checkedAt"]) <= timedelta(minutes=30)):
                pending.append(name + " (final check outstanding)")
                continue
            for q in check["picks"]:
                age = (now-utc(q["at"])).total_seconds()/60
                if not 0 <= age <= 30 or age+q["age"] > 60:
                    unavailable.append(name + " (odds expired before delivery)")
                    continue
                picks.append(dict(fixture=name,matchId=f["id"],kickoff=f["ko"],**q))
            if check["notes"]:
                unavailable.append(name + " (" + ", ".join(check["notes"]) + ")")
    gaps = [w["league"] for w in snapshot.get("calendar", []) if w["gap"]]
    summary = [f"Johnny · Bookings and fouls · {day}",
               f"{len(picks)} verified selections · {complete} fixture review{'s' if complete != 1 else ''} completed."]
    if not snapshot or not snapshot.get("calendar"):
        summary.append("Fixture list unavailable. The scope of the unfinished scan is unknown.")
    elif gaps:
        summary.append("Fixture calendar incomplete for " + ", ".join(gaps))
    if not picks:
        summary.append("No verified selections available for this edition.")
    grouped = {}
    for p in picks:
        market = "to be booked" if p["kind"]=="booking" else f"over {p['line']:g} fouls"
        status = {"predicted":"expected starter", "confirmed":"confirmed starter"}.get(p.get("lineup"), "starter status unrecorded")
        if p.get("opponentLineup") == "predicted" and p.get("lineup") == "confirmed":
            status += ", expected opponent"
        grouped.setdefault(p["fixture"], []).append(f"{p['player']} {market} @ {p['odds']:g} {p['book']} · {status}")
    for name, contracts in grouped.items():
        summary += [name, *contracts]
    if pending:
        summary.append(f"Unfinished ({len(pending)}) · " + ", ".join(pending))
    if unavailable:
        summary.append(f"Evidence unavailable ({len(unavailable)}) · " + ", ".join(unavailable))
    if reserve:
        summary.append(f"{len(reserve)} fixtures screened and left outside the detailed review.")
    full = summary + detail + (["Outside detailed review · " + ", ".join(reserve)] if reserve else [])
    text = "\n".join(summary)
    footer = "\nFull private report " + LINK
    budget = 4096 - len(footer.encode("utf-16-le"))//2
    if len(text.encode("utf-16-le"))//2 > budget:
        # Preserve the contracts ahead of long lists of outstanding fixture names.
        text = "\n".join(s for s in summary if not s.startswith(("Unfinished (","Evidence unavailable (")))
        text += f"\nUnfinished {len(pending)} · evidence unavailable {len(unavailable)}. Names in Admin."
    message = text+footer
    return dict(day=day,at=now.isoformat(),fixtures=len(slate),picks=picks,
                complete=bool(snapshot.get("calendar")) and not (gaps or pending or unavailable),
                coverage="\n".join(full),message=message,attach=len(text.encode("utf-16-le"))//2 > budget)



def deliver(store, day, clock=timestamp):
    path = edition_key(day,"digest")
    edition = store.get(path)
    if edition is None:
        candidate = make_digest(day, store.get(edition_key(day,"research"), {}),
                                store.get(edition_key(day,"checks"), {}), utc(clock()))
        store.put(path, candidate, replace=False)
        edition = store.get(path)
    receipt = store.get("receipts/johnny-"+day+"-0.json", {})
    if receipt and receipt.get("state") != "sent":
        raise RuntimeError("Delivery uncertain; inspect the original receipt")
    if not receipt:
        # The delivery lane is serialized. An unclaimed edition can be refreshed
        # if its previous attempt stopped before calling Telegram.
        if utc(clock())-utc(edition["at"]) > timedelta(minutes=2):
            edition = make_digest(day, store.get(edition_key(day,"research"), {}),
                                  store.get(edition_key(day,"checks"), {}), utc(clock()))
            store.put(path, edition)
        if edition.get("attach"):
            send_digest(store, "johnny-"+day, [edition["coverage"]+"\n"+LINK],
                        document_name=f"Johnny-{day}.txt")
        else:
            send_digest(store,"johnny-"+day,[edition["message"]])
    index = store.get(REPORT)
    if not isinstance(index,dict) or not isinstance(index.get("days"),dict):
        raise RuntimeError("Private Admin report unavailable")
    old = index["days"].get(day)
    if old and old.get("policy") != "johnny-bookings":
        raise RuntimeError("Another policy owns this day's report")
    index["days"][day] = dict(at=edition["at"], policy="johnny-bookings", fixtures=edition["fixtures"],
                              picks=[], coverage=edition["coverage"], final=edition["complete"])
    index.update(updated=edition["at"],status="Johnny's daily booking and fouls scan · 11am London")
    store.put(REPORT,index)
    store.put(edition_key(day,"published"), {"at":edition["at"]})


if __name__ == "__main__":
    store = private_store()
    now = datetime.now(LONDON)
    day = os.environ["EDITION_DAY"]
    if day != now.date().isoformat():
        sys.exit("Expired edition date")
    if sys.argv[1] == "already-sent":
        receipt = store.get("receipts/johnny-"+day+"-0.json", {})
        if receipt.get("state") == "sent" and receipt.get("message_id"):
            if not store.get(edition_key(day,"digest")) or store.get(edition_key(day,"published")):
                sys.exit(0)
            sys.exit(4)  # Only the Admin index needs recovery.
        if receipt:
            sys.exit("Previous delivery is uncertain; inspect existing receipt")
        sys.exit(3)
    elif sys.argv[1] == "verify":
        # Discover additional completed fixtures while time permits. The workflow
        # independently enforces the cutoff even if a provider request hangs.
        reader = Reads(store, JohnnyProvider(store), day, "johnny-edition-verify", 28)
        while True:
            verify(store, day, reader)
            state = store.get(edition_key(day,"research"), {})
            if state.get("stage") == "finished":
                verify(store, day, reader)
                break
            time.sleep(35)
    elif sys.argv[1] == "send":
        deliver(store, day)
    else:
        sys.exit("Unknown edition action")
