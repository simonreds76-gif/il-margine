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

def rehearsal():
    from statshub_daily_board import morning, digest
    from statshub_daily_focus import FOCUS_LIMIT
    from statshub_daily_contracts import LEAGUES, PLAYER_PRICE_MIN, PLAYER_STATS, identity
    class TransientReads:
        def __init__(self,api,limit=40):
            self.api=api
            self.log=[]
            self.cache={}
            self.limit=limit
        def read(self,name,args,slot):
            import json
            key=json.dumps([name,args],sort_keys=True)
            if key in self.cache: return self.cache[key]
            if len(self.log)>=self.limit: return None
            self.log.append(name)
            result=dict(data=self.api.read(name,args),at=timestamp())
            self.cache[key]=result
            return result
    store=Store()
    before=store.get("daily/report.json")
    api=Provider(store)
    focused=TransientReads(api,FOCUS_LIMIT)
    board=morning(TransientReads(api),"2026-11-20",focus_read=focused)
    assert len(focused.log)<=FOCUS_LIMIT and len(board.get("focus",[]))<=3
    assert "Matchup review incomplete" not in board["coverage"]
    print(f"Rehearsal: {len(board.get('focus',[]))} focus fixtures, {len(focused.log)} context reads; no picks sent.",flush=True)
    assert board["fixtures"] and board["completeBoards"] and all(k in board["coverage"] for k in LEAGUES)
    picks=board["picks"]
    assert all(p["side"]=="player" and p["stat"] in PLAYER_STATS and p["odds"]>=p["minimum"]>=PLAYER_PRICE_MIN
               and p["starts"]>=10 for p in picks)
    assert len({(identity(p["matchId"]),identity(p["player"])) for p in picks})==len(picks)
    assert not board.get("focusWatch")
    messages=digest("2026-11-20",board)
    assert all(len(m.encode("utf-16-le"))<=8192 for m in messages)
    assert store.get("daily/report.json")==before
    print("Five league boards, all Friday fixture price boards and private digest rendering verified. No rehearsal selections recorded or delivered.")

if __name__=="__main__":
    try:
        if os.getenv("MODE")=="probe": probe()
        elif os.getenv("MODE")=="rehearse": rehearsal()
        else:
            from statshub_daily_board import run
            run()
    except Exception as exc:
        # Never print request URLs, Telegram tokens, provider bodies or shortlist data in public CI.
        safe_types=(RuntimeError,ValueError)
        print(str(exc)[:150] if type(exc) in safe_types and type(exc).__module__=="builtins" else type(exc).__name__,file=sys.stderr)
        sys.exit(1)
