"""Private Monitor adapter for the report produced by the scheduled football poll."""
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile

ENDPOINT = "repos/simonreds76-gif/il-margine/contents/data/goalkeeper-saves/half-adjustment-v1/report.json?ref=golden-with-speed-insights"


def latest(root):
    cache = root/"data/goalkeeper-saves/half-adjustment-monitor-cache.json"
    old = json.loads(cache.read_text(encoding="utf8")) if cache.exists() else {}
    now = datetime.now(UTC)
    if old.get("checked_at") and now-datetime.fromisoformat(old["checked_at"]) < timedelta(minutes=15):
        return old
    update = dict(old, checked_at=now.isoformat(), source_status="CLOUD_READ_UNAVAILABLE")
    gh = shutil.which("gh") or "C:/Program Files/GitHub CLI/gh.exe"
    try:
        response = subprocess.run([gh,"api","-H","Accept: application/vnd.github.raw+json",ENDPOINT],
                                  capture_output=True,check=True,timeout=6)
        report = json.loads(response.stdout)
        if set(report.get("arms",{})) != {"current","half"} or report.get("actual_stake")!=0:
            raise ValueError("Incomplete paired report")
        update.update(report=report,source_status="OK")
    except (OSError,subprocess.SubprocessError,ValueError,KeyError):
        pass
    cache.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile(mode="w",dir=cache.parent,delete=False,encoding="utf8") as stream:
        json.dump(update,stream,allow_nan=False)
    os.replace(stream.name,cache)
    return update


def add_cards(root, add):
    packet = latest(root)
    report = packet.get("report") or {}
    for arm,label in (("current","Current matchup adjustment"),("half","Half matchup adjustment")):
        data = report.get("arms",{}).get(arm,{})
        entries = [(b["id"],b["date"],b["pnl"]) for b in data.get("bets",[])]
        status = report.get("status","AWAITING_CLOUD_REPORT") if packet["source_status"]=="OK" else "CLOUD_READ_UNAVAILABLE"
        note = (f"First verified pre-match board per fixture. {report.get('fixtures',0)} paired fixtures, "
                f"{data.get('no_bets',0)} no-bets. Both starting keepers must play 90 minutes. "
                f"Four or more saves scored for {data.get('n',0)} keeper forecasts. "
                "Each qualifying selection risks 0.5 paper units. Compare the two records separately.")
        add("gk-half-"+arm, "Keeper saves · "+label, data, dict(report,status=status),note,
            group="Football research", calibration={k:data.get(k) for k in ("brier","log_loss")},
            entries=entries if data else None)
