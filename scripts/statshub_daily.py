"""Run the private StatsHub matchweek pilot on a standard GitHub runner."""
import os
import sys
from statshub_daily_io import Provider, Store, telegram_private, timestamp

def probe():
    store=Store()
    api=Provider(store)
    value=api.read("getFixturesByDate",{"competitionId":"serie-a.17atem7","date":"2026-11-22","days":1,"timeZone":"Europe/London"})
    if not value.get("fixtureCount"): raise ValueError("Fixture probe failed")
    print("StatsHub cloud read and renewable authentication verified.",flush=True)
    report=store.get("daily/report.json")
    if report is None:
        store.put("daily/report.json",{"pilot":"2026-11-20","status":"Scheduled","updated":timestamp(),"days":{}},replace=False)
    if store.get("daily/report.json",{}).get("pilot")!="2026-11-20":
        raise ValueError("Private report did not round-trip")
    public_url=store.base+"/object/public/statshub-daily-private/daily/report.json"
    import requests
    r=requests.get(public_url,timeout=12)
    if r.ok or "2026-11-20" in r.text:
        raise ValueError("Private report protection failed")
    print("Admin data saved privately. Anonymous public read denied.",flush=True)
    telegram_private()
    print("Telegram direct recipient verified. No test notification sent.",flush=True)

if __name__=="__main__":
    try:
        if os.getenv("MODE")=="probe": probe()
        else:
            from statshub_daily_board import run
            run()
    except Exception as exc:
        # Never print request URLs, Telegram tokens, provider bodies or shortlist data in public CI.
        safe_types=(RuntimeError,ValueError)
        print(str(exc)[:150] if type(exc) in safe_types and type(exc).__module__=="builtins" else type(exc).__name__,file=sys.stderr)
        sys.exit(1)
