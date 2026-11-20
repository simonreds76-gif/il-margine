"""Retire unavailable pre-match observations by editing confirmed private roundups in place."""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from pinnradar_tennis import BUCKET, Store, utc
from price_drop_watch import START, private_chat, roundup_text, telegram

CLOCK_PATH = "presentation/desk-active-messages-v1.json"
MAX_BOARD_AGE = timedelta(minutes=20)


def eligibility(move, latest, now):
    start = utc(move["start"])
    if not start or now >= start or latest.get("guards", {}).get(move["fixture"], {}).get("blocked"):
        return "closed"
    item = latest.get("events",{}).get(move["event_id"])
    if item and (item["fixture"] != move["fixture"] or utc(item["start"]) != start or
                 {item["home"],item["away"]} != {move["player"],move["opponent"]}):
        return "closed"
    if item and move.get("market","winner") != "winner" and move["contract"] not in item.get("contracts",{}):
        return "unavailable"
    seen = utc(latest.get("observed"))
    if not seen or seen > now or now-seen >= MAX_BOARD_AGE or not item:
        return "unavailable"
    return "upcoming"


def edit_message(chat, mid, text, kind):
    def call(method, data, files=None):
        url = "https://api.telegram.org/bot" + os.environ["TELEGRAM_BOT_TOKEN"] + "/" + method
        try:
            response = requests.post(url, data=data if files else None, json=None if files else data,
                                     files=files,timeout=16,allow_redirects=False)
            answer = response.json()
        except (requests.RequestException,ValueError):
            raise RuntimeError("Private message edit could not be confirmed") from None
        if not answer.get("ok"):
            detail = str(answer.get("description","")).lower()
            if "message is not modified" in detail:return "same"
            if "message to edit not found" in detail:return "gone"
            if "there is no text in the message" in detail:return "document"
            raise RuntimeError(f"Private message edit HTTP {response.status_code}")
        result = answer["result"]
        if not isinstance(result,dict) or result.get("message_id") != mid or str(result["chat"]["id"]) != chat:
            raise RuntimeError("Edited roundup identity did not verify")
        return "edited"

    identity={"chat_id":chat,"message_id":mid}
    if kind != "document" and len(text.encode("utf-16-le"))//2 <= 4000:
        status = call("editMessageText",{**identity,"text":text,"link_preview_options":{"is_disabled":True}})
        if status != "document":return status,"text"
    media = {"type":"document","media":"attach://roundup","caption":text.splitlines()[0]+" · Updated pre-match availability"}
    status=call("editMessageMedia",{**identity,"media":json.dumps(media)},{
        "roundup":("tennis-roundup.txt",text.encode(),"text/plain")})
    return status,"document"


def remove_roundup(chat, mid):
    # Telegram skips absent IDs, so a retry after a successful deletion is safe.
    confirmed = telegram("deleteMessages", {"chat_id": chat, "message_ids": [mid]})
    if confirmed is not True:
        raise RuntimeError("Private roundup removal was not confirmed")


def discover(store, state, now):
    day = datetime.fromisoformat(state["day"]).date()
    while day <= now.date():
        suffix=day.strftime("%Y/%m/%d")
        prefix="drop-deliveries-v2/"+suffix
        response=store.request("POST","/object/list/"+BUCKET,json={"prefix":prefix+"/","limit":100})
        store.require(response)
        for f in response.json():
            name=f["name"]
            if not re.fullmatch(r"\d{6}-\d{6}\.json",name) or name in state["read"]:
                continue
            receipt=store.get(prefix+"/"+name)
            if not receipt or receipt.get("state")!="sent":continue
            scan=store.get("drop-scans-v2/"+suffix+"/"+name)
            if not scan or scan["observed"]!=receipt["observed"]:continue
            wanted=set(receipt["move_ids"])
            moves=[m for m in scan["moves"] if m["move_id"] in wanted]
            if not wanted or len(moves)!=len(wanted):raise ValueError("Confirmed roundup contract mismatch")
            mid=str(receipt["message_id"])
            state["messages"].setdefault(mid,{"observed":scan["observed"],"moves":moves,"visible":[m["move_id"] for m in moves],
                "closed":[],"kind":receipt.get("delivery_kind","unknown"),"delivered_at":receipt.get("delivered_at")})
            state["read"][name]=True
        if day < now.date():
            state["day"]=(day+timedelta(days=1)).isoformat()
            state["read"]={}
        day+=timedelta(days=1)


def recover_closed_notices(store, state, now):
    # The old clock forgot message IDs after replacing them with a closure notice.
    cutoff = now - timedelta(hours=48)
    recent = {"day":cutoff.date().isoformat(), "messages":{}, "read":{}}
    discover(store, recent, now)
    for mid, entry in recent["messages"].items():
        if mid in state["messages"]:
            continue
        sent_at = utc(entry.get("delivered_at")) or utc(entry["observed"])
        starts = [utc(move["start"]) for move in entry["moves"]]
        if cutoff < sent_at <= now and starts and all(t and t <= now for t in starts):
            state["messages"][mid] = entry
    state["silent_expiry"] = True


def reconcile(store,state,latest,now,*,get_chat=private_chat,edit=edit_message,remove=remove_roundup,pause=time.sleep):
    chat=None
    next_starts=set()
    edits=0
    failed=[]
    for mid,entry in list(state["messages"].items()):
        frozen=set(entry["closed"])
        active=[]
        for m in entry["moves"]:
            if m["move_id"] in frozen:continue
            status=eligibility(m,latest,now)
            if status=="closed":
                frozen.add(m["move_id"])
            else:
                next_starts.add(utc(m["start"]))
                if status=="upcoming":active.append(m)
        ids=[m["move_id"] for m in active]
        done=len(frozen)==len(entry["moves"])
        closed_changed = frozen != set(entry["closed"])
        if ids!=entry["visible"] or done or (not active and closed_changed):
            if chat is None:chat=get_chat()
            if edits:pause(1.05)
            try:
                sent_at = utc(entry.get("delivered_at")) or utc(entry["observed"])
                if done and now - sent_at < timedelta(hours=48):
                    remove(chat, int(mid))
                    print(f"Private roundup absent after expiry: {entry['observed']}")
                    status, kind = "gone", entry["kind"]
                else:
                    if active:
                        text=roundup_text(active,entry["observed"])+"\nShowing only matches still verified as upcoming."
                    else:
                        # Retain the actual dated observations if pricing is suspended or
                        # Telegram's deletion window has passed. Never send a replacement.
                        retained = [m for m in entry["moves"] if done or m["move_id"] not in frozen]
                        heading = "Historical prices at detection" if done else "Prices at detection · current quotes unavailable"
                        text = heading + "\n" + roundup_text(retained, entry["observed"])
                    status,kind=edit(chat,int(mid),text,entry["kind"])
            except RuntimeError:
                failed.append(mid)
                continue
            edits+=1
            entry.update(visible=ids,kind=kind)
            if done or status=="gone":
                del state["messages"][mid]
            entry["closed"]=sorted(frozen)
            store.put(CLOCK_PATH,state,replace=True)
        else:
            entry["closed"]=sorted(frozen)
    store.put(CLOCK_PATH,state,replace=True)
    return next_starts,edits,failed


def run():
    store=Store()
    start=datetime.now(timezone.utc)
    stop=start+timedelta(minutes=15,seconds=15)
    state=store.get(CLOCK_PATH) or {"day":START.date().isoformat(),"messages":{},"read":{},"silent_expiry":True}
    discover(store,state,start)
    if not state.get("silent_expiry"):
        recover_closed_notices(store,state,start)
    changes=0
    while True:
        latest=store.get("latest.json") or {}
        now=datetime.now(timezone.utc)
        deadlines,n,failed=reconcile(store,state,latest,now)
        changes+=n
        due=[t for t in deadlines if now<t<=stop]
        if not due:break
        while (delay:=(min(due)-datetime.now(timezone.utc)).total_seconds())>0:
            time.sleep(min(delay,60))
    print(f"Private roundup cutoff checked; {changes} message updates.")
    if failed:
        raise RuntimeError(f"{len(failed)} private roundup edits remain for the next scan")


if __name__ == "__main__":run()
