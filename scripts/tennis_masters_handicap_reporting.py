"""Read the registered paper ledger for the private Monitor and existing weekly review."""
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3

PATH=Path("data/tennis-ml-research/match-shape-v1/hard-masters-handicap-v1")
LABEL={"current":"Current handicap pricing","candidate":"Neutral serving centre","anchor":"Winner-anchored venue control"}


def load(path):
    return json.loads(path.read_bytes()) if path.is_file() else {}


def summarize_arm(name,rows,clock):
    wins=losses=pushes=pending=no_bets=void_bets=overdue=0
    expected=observed=brier=ll=push_expected=profit=0.
    bins=defaultdict(lambda:[0,0.,0])
    daily=defaultdict(lambda:[0,0.])
    per_edition=defaultdict(lambda:[0,0.])
    n=complete=observed_push=0
    for r,out in rows:
        a=r["arms"][name]
        if not a["selected"]:
            no_bets+=1
        if not out:
            if a["selected"]:
                pending+=1
                overdue+=datetime.fromisoformat(r["quote"]["scheduled_start"].replace("Z","+00:00"))<clock-timedelta(days=2)
            continue
        if out["status"]=="void":
            void_bets+=int(a["selected"])
            continue
        win,draw,lose=a["probabilities"]
        complete+=1
        push_expected+=draw
        result=out["cover"]
        observed_push+=(result=="push")
        if result!="push":
            probability=win/(1-draw)
            actual=int(result=="p1")
            expected+=probability
            observed+=actual
            brier+=(probability-actual)**2
            safe=max(1e-15,min(1-1e-15,probability))
            ll-=math.log(safe if actual else 1-safe)
            bucket=bins[min(4,int(probability*5))]
            bucket[0]+=1; bucket[1]+=probability; bucket[2]+=actual
            n+=1
        if not a["selected"]:
            continue
        if result=="push":
            pnl=0.; pushes+=1
        elif result=="p"+str(a["side"]):
            pnl=a["odds"]-1; wins+=1
        else:
            pnl=-1.; losses+=1
        profit+=pnl
        for entry in (daily[out["result_date"][:10]],per_edition[r["edition"]+" ("+r["tour_id"]+")"]):
            entry[0]+=1; entry[1]+=pnl
    stake=wins+losses+pushes
    return {"wins":wins,"losses":losses,"pushes":pushes,"no_bets":no_bets,"pending":pending,"overdue":overdue,
            "void_bets":void_bets,"settled":stake,"stake_units":stake,"pnl_units":profit,"roi_pct":100*profit/stake if stake else None,
            "brier":brier/n if n else None,"log_loss":ll/n if n else None,"nonpush":n,"expected":expected/n if n else None,
            "observed":observed/n if n else None,"expected_pushes":push_expected,"observed_pushes":observed_push,
            "bins":{i:{"n":v[0],"mean_p":v[1]/v[0],"observed":v[2]/v[0]} for i,v in bins.items()},
            "days":[[d,*v] for d,v in sorted(daily.items())],"per_edition":dict(per_edition)}


def section(root):
    folder=Path(root)/PATH
    registration=load(folder/"registration.json")
    if not registration:
        return {}
    database=folder/"paper.sqlite3"
    rows=[]
    if database.is_file():
        with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)) as db:
            rows=[(json.loads(f),json.loads(o) if o else None) for f,o in db.execute(
                "select f.record,r.record from forecast f left join result r on r.id=f.id order by f.rowid")]
    capture=load(folder/"capture-health.json")
    settlement=load(folder/"settlement-health.json")
    clock=datetime.now(timezone.utc)
    return {"registered_at":registration["registered_at"],"generated_at":max(registration["registered_at"],capture.get("checked_at",""),settlement.get("checked_at","")),
            "status":capture.get("state","AWAITING_CHECK"),"capture":capture,"settlement":settlement,
            "priced":len(rows),"editions":len({r["tour_id"] for r,_ in rows}),"settled_fixtures":sum(bool(o and o["status"]=="settled") for r,o in rows),
            "pending_fixtures":sum(o is None for r,o in rows),"void":sum(bool(o and o["status"]=="void") for r,o in rows),
            "arms":{a:summarize_arm(a,rows,clock) for a in LABEL},
            "latest":[{"names":r["names"],"edition":r["edition"],"lines":r["lines"],"odds":r["odds"],"book":r["quote"]["bookmaker"],
                       "quoted_at":r["quote"]["captured_at"],"result":o.get("cover",o["status"]) if o else "pending",
                       "selections":{a:r["arms"][a]["side"] if r["arms"][a]["selected"] else None for a in LABEL}} for r,o in rows[-3:][::-1]]}


def summary_line(a):
    roi="pending" if a["roi_pct"] is None else f"{a['roi_pct']:+.2f}%"
    scores="awaiting non-push results" if a["brier"] is None else (
        f"Brier {a['brier']:.4f}, log loss {a['log_loss']:.4f}, player-one cover expected {a['expected']:.1%}, observed {a['observed']:.1%} (n={a['nonpush']})")
    return (f"{a['wins']}W/{a['losses']}L/{a['pushes']} pushes, {a['settled']}u settled, {a['pnl_units']:+.2f}u, ROI {roi}. "
            f"{a['pending']} pending bets, {a['no_bets']} no-bets. Calibration {scores}.")


def health_text(r):
    capture=r.get("capture") or {}
    if r.get("settlement",{}).get("state")=="CHECK_REQUIRED":
        return "Settlement needs review."
    if capture.get("state")=="CHECK_REQUIRED":
        return "Capture needs review: "+capture.get("reason","source check failed")+"."
    if capture.get("state")=="NO_ELIGIBLE_FIXTURES":
        return "Latest forecast contains no outdoor hard Masters singles."
    if capture.get("eligible_rows") and capture.get("counts"):
        return "Latest capture check: "+", ".join(f"{v} {k}" for k,v in sorted(capture["counts"].items()))+"."
    return "Awaiting the first eligible refresh."


def weekly_text(r):
    if not r:
        return "Outdoor hard Masters handicaps · paper evidence unavailable."
    lines=[f"Outdoor hard Masters handicaps · {r['priced']} priced, {r['settled_fixtures']} completed, {r['pending_fixtures']} pending, {r['void']} void. {health_text(r)}"]
    lines.extend(f"{label} · {summary_line(r['arms'][a])}" for a,label in LABEL.items())
    return "\n".join(lines)


def add_cards(add,r):
    if not r:
        return
    from admin_profit_history import daily
    for name in ("current","candidate"):
        a=r["arms"][name]
        text=(f"{r['priced']} paired Pinnacle fixtures, including qualifiers and no-bets. {health_text(r)} "
              +summary_line(a))
        if name=="candidate":
            text+=" Winner-anchored venue control: "+summary_line(r["arms"]["anchor"])
        for q in r["latest"]:
            side=q["selections"][name]
            choice="no bet" if side is None else q["names"][side-1]
            text+=(" "+q["edition"]+" · "+", ".join(f"{n} {l:+g} @ {p:g}" for n,l,p in zip(q["names"],q["lines"],q["odds"],strict=True))
                   +f" ({q['book']}, {q['quoted_at']}) · {choice}, {q['result']}.")
        card=add("masters-handicap-"+name,"Hard Masters · "+LABEL[name],a,r,text,group="Tennis match markets",cohort="Prospective paper · 1u per selection",
                 calibration={"brier":a["brier"],"log_loss":a["log_loss"]})
        if a["days"]:
            history=daily([(d,p) for d,n,p in a["days"]],"Cumulative paper profit at the first recorded Pinnacle spread by result date.")
            for v,(_,n,_) in zip(history["days"],a["days"],strict=True):
                v["settled"]=n
            history["settled"]=a["settled"]
            card["history"]=history
        else:
            card["history"]={"message":"The profit graph starts at the first settled paper selection."}
