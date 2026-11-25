"""Manual same-day repair of the already delivered edition. Only edit its original message."""
import os
import sys
from time import sleep
from datetime import datetime, time

from johnny_cards import JohnnyProvider, edition_key, private_store, scan
from johnny_cards_calendar import LONDON
from johnny_cards_edition import make_digest, verify
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
    if not fixture.get("priority") or utc(fixture["ko"]) <= now:
        return False
    return (fixture.get("reviewState") == "unfinished" or
            (fixture.get("reviewState") == "unavailable" and fixture.get("gap") in GAPS))


def prepare(store, day):
    require_edition(store, day)
    original = store.get(edition_key(day,"research"), {})
    if (original.get("day") != day or original.get("stage") not in {"ranked","finished"}
            or original.get("guideSHA256") != Analyst.digest):
        raise ValueError("Original ranked research required")
    path = edition_key(day,"lineup-repair-research")
    saved = store.get(path)
    snapshot = saved_repair(store, day) if saved else original
    for f in snapshot["slate"]:
        if retryable(f, utc(timestamp())):
            for key in ("gap", "reviewError", "reviewStep"):
                f.pop(key, None)
            f["reviewState"] = "selected"
    if not saved or snapshot.get("stage") != "finished" or any(f.get("reviewState")=="selected" for f in snapshot["slate"]):
        original_calls = store.get(f"evidence/{day}/johnny/calls.json", [])
        reader = Reads(store, JohnnyProvider(store), day, "johnny-lineup-repair", max(0,212-len(original_calls)))
        with Analyst(store) as analyst:
            snapshot = scan(reader,day,analyst,previous=snapshot,save=lambda doc: store.put(path,doc))
    print("Completed fixture reviews:",sum(f.get("reviewState")=="complete" for f in snapshot["slate"]))


def saved_repair(store, day):
    snapshot = store.get(edition_key(day,"lineup-repair-research"), {})
    if (snapshot.get("day") != day or snapshot.get("guideSHA256") != Analyst.digest
            or snapshot.get("stage") not in {"ranked", "finished"} or not snapshot.get("calendar")):
        raise ValueError("No verified repair checkpoint for this edition")
    return snapshot


def verify_repair(store, day):
    require_edition(store, day)
    saved_repair(store, day)
    reader = Reads(store,JohnnyProvider(store),day,"johnny-edition-verify",28)
    verify(store, day, reader, research_part="lineup-repair-research", checks_part="lineup-repair-checks")


def amend(store,day):
    receipt = require_edition(store,day)
    snapshot = saved_repair(store, day)
    checks = store.get(edition_key(day,"lineup-repair-checks"), {})
    edition = make_digest(day,snapshot,checks,utc(timestamp()))
    if edition["attach"]:
        raise ValueError("Repaired text exceeds Telegram message limit")
    report = store.get(REPORT)
    if report["days"][day].get("policy") != "johnny-bookings":
        raise ValueError("Another policy owns the Admin report")
    path = edition_key(day,"lineup-repair-digest")
    previous = store.get(path, {})
    if previous.get("messageId") != receipt["message_id"] or previous.get("message") != edition["message"]:
        endpoint, chat = telegram_private()
        response = http.post(endpoint+"/editMessageText",json=dict(chat_id=chat,message_id=receipt["message_id"],
                             text=edition["message"],link_preview_options={"is_disabled":True}),timeout=20)
        if response.ok:
            ack=response.json()
            if not ack.get("ok") or (ack.get("result") or {}).get("message_id") != receipt["message_id"]:
                raise RuntimeError("Edit acknowledgement missing")
        elif response.status_code != 400 or "message is not modified" not in response.text.lower():
            raise RuntimeError("Private Telegram edit failed: HTTP "+str(response.status_code))
        edition["messageId"] = receipt["message_id"]
        store.put(path,edition)
    entry = report["days"][day]
    if entry.get("coverage") != edition["coverage"] or entry.get("final") != edition["complete"]:
        entry.update(at=edition["at"],coverage=edition["coverage"],final=edition["complete"])
        report["updated"]=edition["at"]
        store.put(REPORT,report)
    verify_published_coverage(store, day, edition)
    print("Existing private message and Admin verified. Qualified selections:",len(edition["picks"]))


def verify_published_coverage(store, day, edition):
    # A successful write on 25 Nov still served the previous report after 15 seconds.
    # Await visibility on the same read path Admin uses. Polling must never edit or upload again.
    for delay in (0, 2, 4, 8, 16, 30, 30, 30):
        if delay:
            sleep(delay)
        observed = store.get(REPORT)["days"][day]
        if observed.get("coverage") == edition["coverage"] and observed.get("final") == edition["complete"]:
            return
    raise RuntimeError("Telegram edit acknowledged; private Admin readback still differs after two minutes")


if __name__=="__main__":
    day=os.environ["EDITION_DAY"]
    actions={"research":prepare,"verify":verify_repair,"amend":amend}
    actions[sys.argv[1]](private_store(),day)
