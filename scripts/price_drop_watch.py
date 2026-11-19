"""Private forward observations. All genuine decimal shortenings, neither stakes nor tips."""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

import requests


START = datetime(2026, 11, 19, 12, 31, tzinfo=timezone.utc)
MAX_GAP = timedelta(minutes=40)


def instant(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)


def observe(previous, current, blocked=()):
    """Compare only consecutive saved complete markets, preserving named sides across swaps."""
    after = instant(current["observed"])
    before = instant(previous["observed"]) if previous else None
    result = {"pilot_start": START.isoformat(), "observed": current["observed"],
              "before": previous["observed"] if previous else None,
              "compared_pairs": 0, "too_far_apart": False, "moves": []}
    if before is None or before < START or after <= before:
        return result
    if after - before > MAX_GAP:
        result["too_far_apart"] = True
        return result
    for eid, new in current["events"].items():
        old = previous["events"].get(eid)
        if not old or new["fixture"] in blocked or old["fixture"] != new["fixture"]:
            continue
        if old["start"] != new["start"] or instant(new["start"]) <= after:
            continue
        names = (new["home"], new["away"])
        old_pair = {old["home"]: old["home_price"], old["away"]: old["away_price"]}
        if len(old_pair) != 2 or set(names) != old_pair.keys():
            continue
        earlier = [old_pair[p] for p in names]
        now = [new["home_price"], new["away_price"]]
        result["compared_pairs"] += 1
        for i, player in enumerate(names):
            other = 1-i
            if now[i] >= earlier[i]:
                continue
            prior_p = earlier[other]/sum(earlier)
            current_p = now[other]/sum(now)
            identity = [new["fixture"], eid, player, previous["observed"], current["observed"]]
            move_id = hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode()).hexdigest()[:32]
            result["moves"].append({
                "move_id": move_id, "fixture": new["fixture"], "event_id": eid, "tour": new["tour"],
                "league": new["league"], "player": player, "opponent": names[other], "start": new["start"],
                "before": previous["observed"], "after": current["observed"],
                "old": earlier[i], "new": now[i], "old_opponent": earlier[other], "new_opponent": now[other],
                "old_p": prior_p, "new_p": current_p, "move_pp": round(100*(current_p-prior_p), 6),
                "both_shortened": now[other] < earlier[other], "result":"Pending","profit":None,"score":None
            })
    return result


def blocked_fixtures(guards, current):
    """Carry the same post-start reschedule quarantine across temporarily absent events."""
    after = instant(current["observed"])
    guards = {key:val for key,val in guards.items() if instant(val["start"])+timedelta(days=7)>after}
    for row in current["events"].values():
        previous=guards.get(row["fixture"],{})
        changed=previous.get("start") and previous["start"]!=row["start"]
        blocked=bool(previous.get("blocked") or (changed and after>=instant(previous["start"])))
        guards[row["fixture"]]={"start":row["start"],"blocked":blocked}
    return guards


def object_key(observed):
    return instant(observed).strftime("%Y/%m/%d/%H%M%S-%f.json")


def telegram(method, values, files=None):
    url = "https://api.telegram.org/bot" + os.environ["TELEGRAM_BOT_TOKEN"] + "/" + method
    try:
        payload = {"data": values, "files": files} if files else {"json":values}
        response=requests.post(url,timeout=18,allow_redirects=False,**payload)
        if response.status_code != 200:
            raise RuntimeError(f"Telegram {method} HTTP {response.status_code}")
        data=response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError(f"Telegram {method} response unavailable") from None
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} was not acknowledged")
    return data["result"]


def private_chat():
    chat=os.environ["TELEGRAM_CHAT_ID"].strip()
    result=telegram("getChat",{"chat_id":chat})
    if result.get("type")!="private" or str(result.get("id"))!=chat:
        raise RuntimeError("Telegram destination did not verify as the configured private chat")
    return chat


def roundup_text(moves, observed):
    stamp=instant(observed).strftime("%d %b %H:%M UTC")
    ordered=sorted(moves,key=lambda m:(m["start"],m["league"],m["event_id"],m["player"]))
    lines=[f"Tennis Price Moves | {stamp}",f"{len(ordered)} observed price drops · PinnRadar / Pinnacle",""]
    for m in ordered:
        late=instant(m["start"]).strftime("%d %b %H:%M UTC")
        lines.extend([f"{m['player']} vs {m['opponent']}",f"{m['league']} · {late}",
                      f"{m['player']}: {m['old']:g} → {m['new']:g}"+(" · both prices shortened" if m["both_shortened"] else ""),""])
    lines.append("Price observations only. The second number was seen at detection. No stake or betting recommendation.")
    return "\n".join(lines)


def deliver(batch, store, *, now, get_chat=private_chat, send=telegram):
    stamp=batch["observed"]
    seen=instant(stamp)
    rows=[m for m in batch["moves"] if instant(m["start"])>now]
    if not rows or now<seen or now-seen>timedelta(minutes=2):
        return "quiet"
    key="drop-deliveries-v2/"+object_key(stamp)
    received=store.get(key)
    if received:
        if received.get("state")!="sent":
            raise RuntimeError("Uncertain Telegram receipt. Automatic resend suppressed.")
        return "already delivered"
    chat=get_chat()
    text=roundup_text(rows,stamp)
    intent={"state":"sending","observed":stamp,"attempted_at":now.isoformat(),
            "move_ids":[m["move_id"] for m in rows]}
    if not store.put(key,intent):
        return "reserved"
    if len(text.encode("utf-16-le"))//2 <= 3900:
        message=send("sendMessage",{"chat_id":chat,"text":text,"link_preview_options":{"is_disabled":True}})
    else:
        message=send("sendDocument",{"chat_id":chat,"caption":f"Tennis Price Moves · {len(rows)} price drops. All observations in the attached roundup."},
                     files={"document":("tennis-price-moves.txt",text.encode(),"text/plain")})
    if str(message.get("chat",{}).get("id"))!=chat or not isinstance(message.get("message_id"),int):
        raise RuntimeError("Unable to verify Telegram delivery receipt")
    store.put(key,{**intent,"state":"sent","message_id":message["message_id"],
                   "delivered_at":datetime.fromtimestamp(message["date"],timezone.utc).isoformat()},replace=True)
    return "delivered"
