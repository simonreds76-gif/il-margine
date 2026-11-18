"""Presentation of one sealed ATP comparison for the private Monitor and weekly digest."""
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import sqlite3

SECTION = "tennis_opponent_return"
NAMES = {"before": "Before adjustment", "after": "With opponent adjustment"}
TURIN = ("21364|8|22807|68074", "21364|8|29939|67546")


def section(root):
    root = Path(root)
    folder = root / "data/tennis-ml-research/opponent-return-paired-v1"
    path = folder / "research.sqlite3"
    if not path.is_file():
        return {}
    import tennis_opponent_return_forward as forward
    from contextlib import closing
    endpoint = forward.utc(forward.read(folder / "registration.json")["last_kickoff_exclusive"])
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.execute("begin")
        forecasts, results, stats = (forward.records(db, name) for name in ("forecast", "result", "service"))
        # Use the last actual writer receipt to date the comparison. Rendering the
        # page must never make yesterday's research look freshly collected.
        observed = [r["captured_at"] for r in forecasts.values()]
        observed.extend(r["observed_at"] for table in (results, stats) for r in table.values())
        report_stamp = forward.read(folder/"report.json").get("as_of")
        if report_stamp:
            observed.append(report_stamp)
        if not observed:
            return {}
        stamp = max(map(forward.utc, observed))
        summary = forward.summarize(db, stamp, endpoint)
    days = {arm: defaultdict(lambda: [0, 0.0]) for arm in NAMES}
    pending = dict.fromkeys(NAMES, 0)
    for key, r in forecasts.items():
        result = results.get(key, {})
        for name in NAMES:
            side = r["arms"][name]["selection"]
            if side is None:
                continue
            if not result:
                pending[name] += 1
            elif result["status"] == "settled":
                slot = days[name][result["result_date"][:10]]
                slot[0] += 1
                slot[1] += r["odds"][side] - 1 if r["players"][side] == result["winner_id"] else -1
    for name, daily in days.items():
        summary[name]["pending_selections"] = pending[name]
        summary[name]["daily"] = [[d,n,p] for d,(n,p) in sorted(daily.items())]
        if sum(n for n,p in daily.values()) != summary[name]["settled_units"] or abs(sum(p for n,p in daily.values())-summary[name]["profit_units"]) > 1e-8:
            raise ValueError("opponent-return daily settlements do not reconcile")
    summary["turin"] = []
    for key in TURIN:
        if key not in forecasts:
            continue
        r = forecasts[key]
        result = results.get(key, {})
        evidence = stats.get(key, {})
        summary["turin"].append({
            "fixture": key, "players": r["names"], "scheduled": r["quote"]["scheduled_start"],
            "result": result.get("status","pending"), "score": result.get("score"),
            "winner": r["names"][r["players"].index(result["winner_id"])] if result.get("winner_id") else None,
            "serve": {a:r["arms"][a]["serve"] for a in NAMES}, "actual": evidence.get("actual"),
            "verified_at": evidence.get("observed_at") or result.get("observed_at"),
        })
    return summary


def fmt(value, digits=4, suffix=""):
    return "pending" if value is None else f"{value:.{digits}f}{suffix}"


def reliability(arm):
    bins=arm["favourite_reliability"].values()
    n=sum(b["n"] for b in bins)
    if not n:
        return "favourite calibration pending"
    forecast=sum(b["mean_forecast"]*b["n"] for b in bins)/n
    actual=sum(b["won_rate"]*b["n"] for b in bins)/n
    return f"model favourites expected {forecast:.1%}, won {actual:.1%} ({n} matches)"


def box(row):
    values = row["actual"]
    if values:
        return ", ".join(f"{name} {s['won']}/{s['total']} ({s['won']/s['total']:.1%})" for name,s in zip(row["players"], values))
    suffix = {"pending":"awaiting result", "settled":"result verified, awaiting service statistics", "void":"void"}[row["result"]]
    return "–".join(row["players"]) + " · " + suffix


def description(report, name):
    arm = report[name]
    text = (f"{report['priced']} priced fixtures, {arm['no_bets']} no-bets. Match scores cover all {report['settled']} completed fixtures. "
            f"Verified service points for {report['settled_with_two_players_points']} fixtures. "
            f"Service-point Brier {fmt(arm['point_brier'])}, mean match service-point log loss {fmt(arm['mean_fixture_point_log_loss'])}, "
            f"serve-win bias {fmt(arm['bias_pp'],2,' pp')}. {reliability(arm).capitalize()}. ")
    if arm["service_points_played"]:
        text += (f"Expected {arm['expected_service_points_won']:.1f} points won on serve over the observed number played, "
                 f"observed {arm['actual_service_points_won']}/{arm['service_points_played']}. ")
    if report["settled"] == 0:
        text += "Match Brier, log loss and ROI await settlement. "
    if report["turin"]:
        text += "Turin service points won/played — " + ". ".join(box(r) for r in report["turin"]) + "."
    return text.strip()


def add_cards(add, section_data):
    if not section_data:
        return
    from admin_profit_history import daily
    for name, label in NAMES.items():
        a = section_data[name]
        raw = dict(settled=a["wins"]+a["losses"],wins=a["wins"],losses=a["losses"],pending=a["pending_selections"],
                   stake_units=a["settled_units"],pnl_units=a["profit_units"],roi_pct=a["roi_pct"])
        card=add("atp-opponent-return-"+name, "ATP opponent return · "+label, raw,
                 {"generated_at":section_data["as_of"],"settled_fixtures":section_data["settled"]},
                 description(section_data,name),group="Tennis match markets",cohort="Paired ATP paper · from 18 Nov 2026",
                 calibration={"brier":a["match_brier"],"log_loss":a["match_log_loss"]})
        if a["daily"]:
            history = daily([(d,p) for d,n,p in a["daily"]], "Cumulative paper profit by result date at the saved Pinnacle prices.")
            for row, (_, count, _) in zip(history["days"], a["daily"],strict=True):
                row["settled"]=count
            history["settled"]=raw["settled"]
            card["history"]=history
        else:
            card["history"]={"message":"The profit graph starts with the first settled paper selection."}


def weekly_text(report):
    if not report:
        return "ATP opponent return · comparison snapshot unavailable."
    lines=[f"ATP opponent return · {report['priced']} priced, {report['settled']} completed, {report['pending']} pending, {report['void']} void. "
           f"Paired service statistics on {report['settled_with_two_players_points']} fixtures."]
    for name,label in NAMES.items():
        a=report[name]
        roi = "unavailable (no settled stake)" if a["roi_pct"] is None else f"{a['roi_pct']:+.2f}%"
        pl = f"{a['profit_units']:+.3f}u" if a["settled_units"] else "0u"
        lines.append(f"{label} · {a['wins']}W/{a['losses']}L, {a['settled_units']}u settled, {pl}, ROI {roi}, {a['no_bets']} no-bets. "
                     f"Match Brier {fmt(a['match_brier'])}, log loss {fmt(a['match_log_loss'])}, {reliability(a)}. "
                     f"Service log loss {fmt(a['mean_fixture_point_log_loss'])}, Brier {fmt(a['point_brier'])}, bias {fmt(a['bias_pp'],2,' pp')}.")
    if report["market"]["match_brier"] is not None:
        lines.append(f"Pinnacle no-vig · match Brier {fmt(report['market']['match_brier'])}, log loss {fmt(report['market']['match_log_loss'])}.")
    from datetime import datetime
    cutoff=datetime.fromisoformat(report["as_of"])-timedelta(days=7)
    for r in report["turin"]:
        if datetime.fromisoformat((r["verified_at"] or r["scheduled"]).replace("Z","+00:00"))>=cutoff:
            lines.append("Turin · "+box(r))
    return "\n".join(lines)
