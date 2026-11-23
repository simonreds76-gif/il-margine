"""Private reporting for the forward, two-sided double-fault comparison."""
from collections import Counter, defaultdict
from datetime import datetime
from math import log
from statistics import mean
import json
import hashlib

from pathlib import Path

REL = Path("data/tennis-props/shadow/df-surface-forward-v1")
ARMS = {"weighted": "Surface-weighted DF", "astra": "Astra DF", "control": "DF control"}


def pair_proof(row):
    """Bind the original two sides before the general feed combines its rows."""
    if row.get("market")!="double_faults" or not row.get("over_odds") or not row.get("under_odds"):
        return ""
    fields=("event_id","tour","tournament","bookmaker","player","opponent","market","line",
            "capture_ts","match_start_utc","raw_market_name","over_odds","under_odds")
    return hashlib.sha256(json.dumps([row.get(k) for k in fields],ensure_ascii=False).encode()).hexdigest()


def observe(root, **kwargs):
    # This observer has its own receipt and never gates the existing pricing or alert stages.
    try:
        from tennis_df_surface_paper import run
        result=run(root,**kwargs)
        print("DF surface paper:",result["offers"],"registered,",result["capture"]["state"])
    except Exception as error:
        print("WARNING: DF surface paper observer failed:",type(error).__name__)


def report(root):
    path = root / REL / "report.json"
    return json.loads(path.read_bytes()) if path.exists() else {}


def summarize(records, outcomes, coverage, now):
    arms = {}
    graded = {r["fixture"] for r in records if outcomes.get(r["id"], {}).get("status") == "settled"}
    for arm in (*ARMS, "market"):
        by_match = defaultdict(list)
        bins = defaultdict(list)
        counts = Counter()
        entries = []
        player_counts = {}
        for r in records:
            key = r["id"]
            prediction = r["arms"][arm]
            side = prediction.get("side")
            grade = outcomes.get(key, {})
            status = grade.get("status", "pending")
            if side:
                counts["selected"] += 1
                counts[status] += 1
                if status == "pending" and (now - datetime.fromisoformat(r["start"])).total_seconds() > 48*3600:
                    counts["overdue"] += 1
            if status != "settled":
                continue
            actual = grade["actual"]
            delta = actual - r["line"]
            if side:
                diff = delta if side == "OVER" else -delta
                pnl = r["odds"][side]-1 if diff > 0 else -1 if diff < 0 else 0
                counts["wins" if diff > 0 else "losses" if diff < 0 else "pushes"] += 1
                entries.append((key, r["start"], pnl))
            if "mean" in prediction:
                player_counts.setdefault((r["fixture"],r["player_id"]), (prediction["mean"], actual))
            if delta == 0:
                continue
            p = prediction["p_over"]
            y = int(delta > 0)
            loss = -log(max(1e-15, p if y else 1-p))
            by_match[r["fixture"]].append(loss)
            bins[min(4,int(5*p))].append((p,y))
        pairs = [v for values in bins.values() for v in values]
        net = sum(e[2] for e in entries)
        count = len(entries)
        arm_report = dict(scored=len(pairs), brier=mean((p-y)**2 for p,y in pairs) if pairs else None,
                          log_loss=mean(mean(scores) for scores in by_match.values()) if by_match else None,
                          expected_hit_rate=mean(p for p,y in pairs) if pairs else None,
                          observed_hit_rate=mean(y for p,y in pairs) if pairs else None,
                          reliability=[dict(bin=b,n=len(v),forecast=mean(p for p,y in v),
                                            observed=mean(y for p,y in v)) for b,v in sorted(bins.items())])
        if arm != "market":
            arm_report.update(selected=counts["selected"],passes=len(records)-counts["selected"],stake_units=count,
                              settled=count,pnl_units=net,roi_pct=100*net/count if count else None,
                              **{k:counts[k] for k in ("wins","losses","pushes","void","pending","overdue")})
            arm_report["count_mae"]=mean(abs(mu-y) for mu,y in player_counts.values()) if player_counts else None
            arm_report["count_bias"]=mean(mu-y for mu,y in player_counts.values()) if player_counts else None
        arms[arm]=arm_report
    return dict(generated_at=now.isoformat(),capture=coverage,offers=len(records),
                fixtures=len({r["fixture"] for r in records}),settled_fixtures=len(graded),
                pending_offers=len(records)-len(outcomes),void_offers=sum(g["status"]=="void" for g in outcomes.values()),
                arms=arms)


def add_cards(root, add):
    r = report(root)
    if not r:
        return
    folder=root/REL
    path=folder/"observations.jsonl"
    records=[json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []
    grades=json.loads((folder/"outcomes.json").read_bytes())
    for arm,label in ARMS.items():
        raw=r["arms"][arm]
        entries=[]
        for row in records:
            side=row["arms"][arm].get("side")
            grade=grades.get(row["id"],{})
            if side and grade.get("status")=="settled":
                diff=(grade["actual"]-row["line"])*(1 if side=="OVER" else -1)
                entries.append((row["id"],row["start"],row["odds"][side]-1 if diff>0 else -1 if diff<0 else 0))
        add("df-surface-"+arm,label+" · fresh paired odds",raw,r,
            f'{r["offers"]} two-sided offers across {r["fixtures"]} matches. {raw["passes"]} passes, '
            f'{raw["void"]} void. Calibration includes passes and grades {raw["scored"]} non-push odds lines. '
            '1u per qualifying line. Multiple lines may belong to one match.',
            group="Double faults · fresh paired odds",calibration={k:raw[k] for k in
                ("brier","log_loss","expected_hit_rate","observed_hit_rate","count_mae","count_bias")},entries=entries)


def weekly(r):
    if not r:
        return "Double faults · fresh paired odds — no forward report received."
    def fmt(value, digits=3):
        return f"{value:.{digits}f}" if value is not None else "—"
    lines=[f'Double faults · fresh paired odds | {r["offers"]} offers, {r["settled_fixtures"]} settled matches, '
           f'{r["pending_offers"]} pending offers. Last odds check {(r.get("capture") or {}).get("checked_at","—")}.']
    for arm,label in ARMS.items():
        a=r["arms"][arm]
        roi=f'{a["roi_pct"]:+.1f}%' if a["roi_pct"] is not None else "—"
        lines.append(f'{label} | {a["wins"]}W/{a["losses"]}L, {a["pushes"]} pushes, {a["void"]} void, '
                     f'{a["pending"]} pending, {a["passes"]} passes | {a["pnl_units"]:+.2f}u / {a["stake_units"]}u, '
                     f'ROI {roi} | Brier {fmt(a["brier"])}, fixture log loss {fmt(a["log_loss"])}.')
    return "\n".join(lines)
