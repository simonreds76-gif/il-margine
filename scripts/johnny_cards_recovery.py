"""Manual same-day repair of the already delivered edition. Only edit its original message."""
import os
import sys
from datetime import datetime, time

from johnny_cards import JohnnyProvider, edition_key, private_store, scan
from johnny_cards_calendar import LONDON
from johnny_cards_edition import candidates, make_digest, recheck
from johnny_cards_review import Analyst
from statshub_daily_board import REPORT, Reads
from statshub_daily_contracts import utc
from statshub_daily_io import http, telegram_private, timestamp

GAPS = {"starting elevens unavailable", "lineup lookup failed", "no expected or confirmed XI published",
        "no expected or confirmed starters identified for these teams"}


def require_edition(store, day):
    now = datetime.now(LONDON)
    if now.date().isoformat() != day or now.time() < time(11,31):
        raise ValueError("Manual lineup repair needs today's delivered edition after the morning window")
    receipt = store.get(f"receipts/johnny-{day}-0.json", {})
    original = store.get(edition_key(day, "digest"), {})
    if (receipt.get("state") != "sent" or not receipt.get("message_id")
            or original.get("day") != day or original.get("attach")):
        raise ValueError("No confirmed original text digest to amend")
    return receipt


def retryable(fixture, now):
    return (fixture.get("reviewState") == "unavailable" and fixture.get("priority")
            and fixture.get("gap") in GAPS and utc(fixture["ko"]) > now)


def prepare(store, day):
    require_edition(store, day)
    original = store.get(edition_key(day,"research"), {})
    if original.get("stage") != "finished" or original.get("guideSHA256") != Analyst.digest:
        raise ValueError("Completed original research required")
    path = edition_key(day,"lineup-repair-research")
    saved = store.get(path)
    snapshot = saved or original
    if not saved:
        for f in snapshot["slate"]:
            if retryable(f, utc(timestamp())):
                f.pop("gap")
                f["reviewState"] = "selected"
    if not saved or saved.get("stage") != "finished":
        original_calls = store.get(f"evidence/{day}/johnny/calls.json", [])
        reader = Reads(store, JohnnyProvider(store), day, "johnny-lineup-repair", max(0,212-len(original_calls)))
        with Analyst(store) as analyst:
            snapshot = scan(reader,day,analyst,previous=snapshot,save=lambda doc: store.put(path,doc))
    print("Completed fixture reviews:",sum(f.get("reviewState")=="complete" for f in snapshot["slate"]))


def verify_repair(store, day):
    require_edition(store, day)
    snapshot = store.get(edition_key(day,"lineup-repair-research"), {})
    if snapshot.get("day") != day or snapshot.get("stage") != "finished":
        raise ValueError("Lineup repair has not finished")
    reader = Reads(store,JohnnyProvider(store),day,"johnny-edition-verify",28)
    checks = {}
    for f in snapshot["slate"]:
        now = utc(timestamp())
        if f.get("reviewState") == "complete" and utc(f["ko"]) > now and any(candidates(f)):
            checks[f["id"]] = recheck(reader, f, now)
    store.put(edition_key(day,"lineup-repair-checks"),checks)


def amend(store,day):
    receipt = require_edition(store,day)
    snapshot = store.get(edition_key(day,"lineup-repair-research"), {})
    checks = store.get(edition_key(day,"lineup-repair-checks"))
    if checks is None or snapshot.get("day") != day or snapshot.get("stage") != "finished":
        raise ValueError("Missing repaired evidence")
    edition = make_digest(day,snapshot,checks,utc(timestamp()))
    if edition["attach"]:
        raise ValueError("Repaired text exceeds Telegram message limit")
    report = store.get(REPORT)
    if report["days"][day].get("policy") != "johnny-bookings":
        raise ValueError("Another policy owns the Admin report")
    endpoint, chat = telegram_private()
    response = http.post(endpoint+"/editMessageText",json=dict(chat_id=chat,message_id=receipt["message_id"],
                         text=edition["message"],link_preview_options={"is_disabled":True}),timeout=20)
    if response.ok:
        ack=response.json()
        if not ack.get("ok") or (ack.get("result") or {}).get("message_id") != receipt["message_id"]:
            raise RuntimeError("Edit acknowledgement missing")
    elif response.status_code != 400 or "message is not modified" not in response.text.lower():
        raise RuntimeError("Private Telegram edit failed: HTTP "+str(response.status_code))
    store.put(edition_key(day,"lineup-repair-digest"),edition)
    report["days"][day].update(at=edition["at"],coverage=edition["coverage"],final=edition["complete"])
    report["updated"]=edition["at"]
    store.put(REPORT,report)
    if store.get(REPORT)["days"][day]["coverage"] != edition["coverage"]:
        raise RuntimeError("Admin readback did not match")
    print("Existing private message and Admin verified. Qualified selections:",len(edition["picks"]))


if __name__=="__main__":
    day=os.environ["EDITION_DAY"]
    actions={"research":prepare,"verify":verify_repair,"amend":amend}
    actions[sys.argv[1]](private_store(),day)
