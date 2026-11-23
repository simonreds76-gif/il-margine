"""Prospective double-fault comparison. The writer only owns its private paper directory."""
import argparse
import ast
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import inspect
import json
import re
import runpy
import subprocess
import sys
import tempfile

from df_surface_reporting import REL, summarize, pair_proof
from oncourt_nonplayed import settlement_games
from tennis_ace_compass import atomic, lock, native_round
from tennis_paper_walkover import consistent_walkover, csv_rows

ROOT=Path(__file__).resolve().parents[1]
TREND=runpy.run_path(str(ROOT/"scripts/tennis-props-rate-trend-prospective.py"))
MODEL=TREND["MODEL"]
digest, stamp, norm = (TREND[k] for k in ("digest","stamp","norm"))
POLICY=dict(version="df-surface-forward-v1",age_minutes=10,real_stake=0,paper_stake=1,min_ev=.03,
            baseline_config_hash="28f35b5a1c2b16cdd8c3ad1cbafe83787ddfdd193f4cc453491f6466d5d81912",
            replay_registration_sha="b8bcdc710319308635e350826e07ac50eb837b09469de2906da4515844d0185b",
            scope="first fresh two-sided full-match player DF line per native fixture, player and book",
            review="200 settled fixtures, 4 tournaments and 56 days; no automatic promotion")


def utcnow():
    return datetime.now(timezone.utc)


def model_signature():
    functions=(TREND["paired_predictions"],TREND["policy"],MODEL["prediction"],MODEL["rate_trend"],
               MODEL["surface"],MODEL["aggregate"],MODEL["negative_binomial_line_probabilities"])
    return digest([ast.dump(ast.parse(inspect.getsource(fn))) for fn in functions])


def weighted_multiplier(history, cutoff, target_surface, edition, courts, features, astra, cfg):
    base, recent = features["player_baseline"], features["player_recent"]
    totals=[[0,0] for _ in range(3)]
    for game in history:
        played=game["played"]
        if not (game["double_faults_valid"] and cutoff-timedelta(days=365)<=played<cutoff):
            continue
        tid=game["fixture_id"].split("|")[3]
        native=courts.get(tid)
        if not native or MODEL["surface"](native)!=game["surface"]:
            return astra, "court_identity_fallback", totals
        i=2 if tid==edition else 1 if native==target_surface else 0
        totals[i][0]+=game["df"]
        totals[i][1]+=game["second"]
    (od,on),(sd,sn),(ed,en)=totals
    if not on or not base["second"] or not base["df"]:
        return astra,"missing_prior_fallback",totals
    prior=cfg["second_serve_prior"]
    surface_rate=(sd+prior*od/on)/(sn+prior)
    edition_rate=(ed+prior*surface_rate)/(en+prior)
    share=base["second"]/base["sp"]
    share_ratio=(recent["second"]+cfg["point_prior"]*share)/(recent["sp"]+cfg["point_prior"])/share
    factor=edition_rate/(base["df"]/base["second"])*share_ratio
    blend=cfg["trend_blend"]
    return max(cfg["multiplier_min"], min(cfg["multiplier_max"],1-blend+blend*factor)), "weighted", totals


def price_reason(q, now, inception):
    observed,start=stamp(q.get("capture_ts")),stamp(q.get("match_start_utc"))
    if not observed or not start or not inception<=observed<=now<start:
        return "outside_forward_prematch_window"
    if now-observed>timedelta(minutes=POLICY["age_minutes"]):
        return "stale_odds"
    if not all(q.get(k) for k in ("event_id","bookmaker","player","opponent","tour","tournament")):
        return "missing_market_identity"
    if any(MODEL["numeric"](q.get(k)) is None or MODEL["numeric"](q[k])<=1 for k in ("over_odds","under_odds")):
        return "no_valid_two_sided_odds"
    if q.get("market")!="double_faults" or q.get("tour") not in ("ATP","WTA"):
        return "outside_market"
    line=MODEL["numeric"](q.get("line"))
    if line is None or line<0 or not (2*line).is_integer():
        return "invalid_line"
    return None


def source_key(q):
    return (q["tour"],q["event_id"],norm(q["bookmaker"]),norm(q["player"]),norm(q["opponent"]),
            q["market"],float(q["line"]),stamp(q["capture_ts"]),stamp(q["match_start_utc"]))


def original_pair(q):
    if q.get("df_pair_evidence"):
        return q["df_pair_evidence"]==pair_proof(q)
    if norm(q["bookmaker"])!="betsbk":
        return False
    # This collector records both original button labels in the same market read.
    sides=re.findall(r"\b(OVER|UNDER)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\b",
                     q.get("raw_label_sample","").upper())
    return (len(sides)==2 and {(s,float(l),float(o)) for s,l,o in sides}
            =={(s,float(q["line"]),float(q[s.lower()+"_odds"])) for s in ("OVER","UNDER")})


def map_forecast(q, raw, board, today, now):
    if (q.get("matched_board")!="yes" or q.get("scope")!="player"
            or q.get("match_source") not in {"exact","exact_any_date","undated_pair_market_schedule"}):
        return None,"no_exact_board_pair"
    if MODEL["tournament_identity"](q["tournament"])!=MODEL["tournament_identity"](raw["tournament"]):
        return None,"different_tournament"
    candidates=[b for b in board if b["tour"]==q["tour"] and b["date"]==q["date"]
                and norm(b["player"])==norm(q["player"]) and norm(b["opponent"])==norm(q["opponent"])
                and b["tournament"]==q["tournament"]]
    if len(candidates)!=1:
        return None,"board_identity_unresolved"
    b=candidates[0]
    if (b.get("generation_date")!=now.date().isoformat() or b.get("history_as_of")!=b["generation_date"]
            or not q.get("history_fingerprint") or b.get("history_fingerprint")!=q["history_fingerprint"]
            or b["surface"]!=q["surface"] or float(b["projected_dfs"])!=float(q["projection_mean"])):
        return None,"board_inputs_changed_or_stale"
    rid,reason=native_round(b,today[q["tour"]])
    if reason:
        return None,reason
    return (b,rid),None


def capture(root, folder, records, raw_path, comparison, now, reg, cfg, clock=utcnow):
    health=Counter()
    source=root/"data/oncourt"
    inception=stamp(reg["start"])
    raw_groups=defaultdict(list)
    for q in csv_rows(raw_path) if raw_path and raw_path.is_file() else ():
        if q.get("market")!="double_faults":
            continue
        health["df_offers_seen"]+=1
        reason=price_reason(q,now,inception)
        if reason:
            health[reason]+=1
        elif not original_pair(q):
            health["unverified_two_sided_snapshot"]+=1
        else:
            raw_groups[source_key(q)].append(q)
    def receipt():
        return dict(state="CAPTURED" if health["added"] else "NO_NEW_ELIGIBLE_PAIRS",
                    checked_at=now.isoformat(),reasons=dict(health),added=health["added"])
    if not raw_groups:
        return receipt()
    if not comparison:
        # Price immediately from today's normal board, without rewriting the live comparison.
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            out=Path(tmp)/"comparison.csv"
            subprocess.run([sys.executable,str(root/"scripts/tennis-props-compare-bet365.py"),
                            "--date",now.date().isoformat(),"--lines",str(raw_path),"--market-filter","double_faults",
                            "--out",str(out),"--unmatched-out",str(Path(tmp)/"unmatched.csv")],
                           check=True,timeout=45)
            if not out.exists():
                health["no_current_comparison"]+=1
                return receipt()
            return capture(root,folder,records,raw_path,out,clock(),reg,cfg,clock)
    board=list(csv_rows(root/"data/tennis-props/player-props-board.csv"))
    today={t:list(csv_rows(source/f"today_{t.lower()}.csv")) for t in {k[0] for k in raw_groups}}
    work=[]
    seen={r["id"] for r in records}
    for q in csv_rows(comparison):
        if q.get("market")!="double_faults" or price_reason(q,now,inception):
            continue
        offers=raw_groups.get(source_key(q),[])
        if not offers:
            health["raw_pair_missing"]+=1
            continue
        prices={(float(o["over_odds"]),float(o["under_odds"])) for o in offers}
        if prices!={(float(q["over_odds"]),float(q["under_odds"]))}:
            health["conflicting_pair"]+=1
            continue
        raw=offers[0]
        reason=TREND["eligibility"](q,now)
        if not reason:
            mapped,reason=map_forecast(q,raw,board,today,now)
        if reason:
            health[reason]+=1
            continue
        b,rid=mapped
        fixture=digest([q["tour"],b["tour_id"],rid,sorted([b["player_id"],b["opponent_id"]])])
        key=digest([fixture,b["player_id"],norm(q["bookmaker"]),float(q["line"])])
        if key in seen:
            health["duplicate"]+=1
            continue
        q=dict(q,logged_at_utc=now.isoformat())
        work.append((q,raw,b,rid,fixture,key))
    if not work:
        if not health["duplicate"]: health["no_usable_comparison"]+=1
        return receipt()
    tours=sorted({q["tour"] for q,*_ in work})
    before,reason=TREND["source_manifest"](source,tours,now,cfg["max_source_age_hours"])
    if reason:
        health[reason]+=len(work)
        return receipt()
    histories,_,ids,_=MODEL["load_source"](source,[w[0] for w in work],cfg)
    courts={c["id"]:c["name"] for c in csv_rows(source/"courts.csv")}
    editions={t:{e["id"]:e for e in csv_rows(source/f"tours_{t.lower()}.csv")} for t in tours}
    native={t:{tid:courts.get(e["court_id"]) for tid,e in values.items()} for t,values in editions.items()}
    if before!=TREND["source_manifest"](source,tours,clock(),cfg["max_source_age_hours"])[0]:
        raise ValueError("DF paper inputs changed during forecast")
    for q,raw,b,rid,fixture,key in sorted(work,key=lambda w:stamp(w[0]["capture_ts"])):
        if key in seen:
            health["duplicate"]+=1
            continue
        t=q["tour"]; pid=b["player_id"]; opp=b["opponent_id"]; tid=b["tour_id"]
        e=editions[t].get(tid,{})
        if (ids[t].get(norm(q["player"]))!=pid or ids[t].get(norm(q["opponent"]))!=opp or not e
                or not MODEL["BOARD"]["is_supported_main_tour"](e) or not native[t].get(tid)
                or MODEL["surface"](native[t][tid])!=q["surface"]):
            health["unverified_fixture_or_surface"]+=1
            continue
        history=histories[t][pid]
        cutoff=stamp(q["capture_ts"]).date()
        factor,features,reason=MODEL["rate_trend"](history,histories[t][opp],q["surface"],cutoff,"double_faults",cfg)
        if factor is None:
            health[reason]+=1
            continue
        weighted,support,groups=weighted_multiplier(history,cutoff,native[t][tid],tid,native[t],features,factor,cfg)
        pair=TREND["paired_predictions"](q,factor,cfg)
        arms={}
        for arm,p in (("weighted",TREND["paired_predictions"](q,weighted,cfg)["candidate"]),
                      ("astra",pair["candidate"]),("control",pair["control"])):
            arms[arm]=dict(p_over=p["OVER"]["p_conditional"],mean=p["OVER"]["mean"],
                           side=TREND["policy"](p,cfg["min_ev"]),predictions=p)
        odds={s:float(q[s.lower()+"_odds"]) for s in ("OVER","UNDER")}
        arms["market"]={"p_over":(1/odds["OVER"])/sum(1/o for o in odds.values())}
        frozen=clock()
        reason=price_reason(q,frozen,inception)
        if reason:
            health[reason]+=1
            continue
        record=dict(id=key,fixture=fixture,tour=t,edition=tid,round=rid,player_id=pid,opponent_id=opp,
                    player=q["player"],opponent=q["opponent"],tournament=q["tournament"],book=q["bookmaker"],
                    start=stamp(q["match_start_utc"]).isoformat(),registered_at=frozen.isoformat(),
                    odds=odds,line=float(q["line"]),captured_at=q["capture_ts"],event_id=q["event_id"],
                    odds_age_seconds=(frozen-stamp(q["capture_ts"])).total_seconds(),raw_hash=digest(raw),
                    forecast_hash=digest(q),history_fingerprint=q["history_fingerprint"],source_manifest=before,
                    features=features,surface=native[t][tid],support=support,group_df_and_second=groups,
                    multipliers=dict(astra=factor,weighted=weighted),arms=arms,policy_hash=digest(POLICY))
        TREND["append"](folder/"observations.jsonl",records,record)
        health["added"]+=1
        seen.add(key)
    return receipt()


def settle(source,records,outcomes,now):
    pending=[r for r in records if r["id"] not in outcomes and stamp(r["start"])<=now]
    def ident(tid,rid,p,o):
        return (tid,rid,tuple(sorted((p,o))))
    for t in sorted({r["tour"] for r in pending}):
        group=[r for r in pending if r["tour"]==t]
        wanted={ident(r["edition"],r["round"],r["player_id"],r["opponent_id"]) for r in group}
        games=defaultdict(dict); stats=defaultdict(dict)
        for g in settlement_games(source,t.lower(),csv_rows):
            w,l,tid,rid=MODEL["match_key"](g)
            fk=ident(tid,rid,w,l)
            if fk in wanted:
                games[fk][digest(g)]=g
        for s in csv_rows(source/f"stat_{t.lower()}.csv"):
            w,l,tid,rid=MODEL["match_key"](s)
            if ident(tid,rid,w,l) in wanted:
                stats[(w,l,tid,rid)][digest(s)]=s
        for r in group:
            fk=ident(r["edition"],r["round"],r["player_id"],r["opponent_id"])
            if len(games[fk])!=1:
                continue
            g=next(iter(games[fk].values()))
            if not r["registered_at"][:10]<=g["date"]<=now.date().isoformat():
                continue
            w,l,tid,rid=MODEL["match_key"](g)
            matches=stats[(w,l,tid,rid)]
            reverse=stats[(l,w,tid,rid)]
            actual=None
            if g.get("status")=="walkover":
                if not consistent_walkover(g,stamp(r["start"]),stamp(r["registered_at"]),now,bool(matches or reverse)):
                    continue
            elif TREND["SETTLE"]["is_void_score"](g["result"]):
                pass
            else:
                from ace_compass_engine import score
                sets=score(g["result"])
                if not sets or len(matches)!=1 or reverse:
                    continue
                stat=next(iter(matches.values()))
                prefix="w_" if w==r["player_id"] else "l_"
                actual,second,first,sp=[MODEL["count"](stat.get(prefix+k)) for k in ("df","w2sof","fs","svpt")]
                if None in (actual,second,first,sp) or sp==0 or actual>second or second+first!=sp:
                    continue
            outcomes[r["id"]]=dict(status="void" if actual is None else "settled",actual=actual,
                                    date=g["date"],settled_at=now.isoformat(),source_hash=digest([g,matches]))


def run(root=ROOT,lines=None,comparison=None,settlement=False,initialize=False):
    folder=root/REL
    with lock(folder):
        now=utcnow()
        registration=folder/"registration.json"
        implementation=hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n",b"\n")).hexdigest()
        cfg=TREND["read_json"](root/"config/tennis-props-rate-trend-prospective-v1.json",{})
        if digest(cfg)!=POLICY["baseline_config_hash"]:
            raise ValueError("Frozen Astra configuration changed")
        signature=model_signature()
        if initialize and not registration.exists():
            atomic(registration,dict(start=now.isoformat(),policy=POLICY,implementation=implementation,
                                     model_signature=signature))
        reg=TREND["read_json"](registration,{})
        if reg.get("policy")!=POLICY or reg.get("implementation")!=implementation or reg.get("model_signature")!=signature:
            raise ValueError("Unregistered DF surface implementation")
        records=TREND["ledger"](folder/"observations.jsonl")
        outcomes=TREND["read_json"](folder/"outcomes.json",{})
        previous=TREND["read_json"](folder/"report.json",{})
        health=previous.get("capture",{"state":"AWAITING_FIRST_CHECK","checked_at":None})
        if lines:
            try:
                health=capture(root,folder,records,lines,comparison,now,reg,cfg)
            except Exception as exc:
                health=dict(state="CAPTURE_CHECK_FAILED",checked_at=now.isoformat(),error=type(exc).__name__)
                atomic(folder/"report.json",summarize(records,outcomes,health,utcnow()))
                raise
        if settlement:
            settle(root/"data/oncourt",records,outcomes,now)
        atomic(folder/"outcomes.json",outcomes)
        result=summarize(records,outcomes,health,utcnow())
        atomic(folder/"report.json",result)
        return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--lines",type=Path)
    parser.add_argument("--comparison",type=Path)
    parser.add_argument("--settle",action="store_true")
    parser.add_argument("--initialize",action="store_true")
    args=parser.parse_args()
    result=run(lines=args.lines,comparison=args.comparison,settlement=args.settle,initialize=args.initialize)
    print(json.dumps({k:result[k] for k in ("offers","fixtures","capture","settled_fixtures")}))
