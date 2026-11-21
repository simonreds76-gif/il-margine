"""Bounded private comparison on the hosted runner. No delivery or publication."""
from datetime import datetime, timedelta, timezone
from contextlib import closing
import base64
import gzip
import hashlib
import json
import os
import time

import websocket

from desk_reference_compare import ROOT, compare, is_qual, stamp
from pinnradar_tennis import Store

END = datetime(2026, 11, 23, 15, 19, 57, tzinfo=timezone.utc)
PREFIX = "research/desk-reference-20261121"
HOST_HASH = "aa92f3c0bb451d1c9ed72f2e9582620752c1c0e381d32ab457d9d8e9408f9298"
MAX_WINDOWS = 6


def now():
    return datetime.now(timezone.utc)


def recent(store, at):
    for day in dict.fromkeys([at.date(), (at - timedelta(minutes=30)).date()]):
        tape = store.get(f"presentation/desk-tapes/{day}.json") or {}
        for name, observed in sorted(tape.get("slots", {}).items(), key=lambda item: item[1], reverse=True):
            if not timedelta(0) <= at - stamp(observed) <= timedelta(minutes=30):
                continue
            snap = store.get(f"snapshots/{day:%Y/%m/%d}/{name}")
            if snap and snap.get("observed") == observed:
                return snap
    return None


def available(snapshot, at, qualifiers):
    live = set(snapshot.get("in_play_fixtures", []))
    return {str(row["id"]) for row in snapshot["events"].values()
            if row["fixture"] not in live and stamp(row["start"]) > at
            and (not qualifiers or is_qual(row["league"])) and row.get("contracts")}


def capture(access, targets, path, seconds):
    host = access["host"]
    if hashlib.sha256(host.encode("ascii")).hexdigest() != HOST_HASH:
        raise ValueError("Unexpected stream endpoint")
    stop = time.monotonic() + seconds
    known = set()
    snapshot_complete = False
    with closing(websocket.create_connection(f"wss://{host}/v1/stream", timeout=12, redirect_limit=0)) as socket:
        socket.send(json.dumps({"type":"login", "token":access["key"], "accept_delay":True}))
        if json.loads(socket.recv()).get("type") != "welcome":
            raise RuntimeError("Feed authentication failed")
        socket.send(json.dumps({"type":"subscribe", "sports":[2], "channels":["pre"], "snapshot":True}))
        with path.open("x", encoding="utf-8") as out:
            def write(frame):
                out.write(json.dumps({"received":now().isoformat(), "frame":frame}, separators=(",", ":")) + "\n")

            def wanted(row):
                child = str(row.get("id", ""))
                if "parentId" in row and str(row["parentId"]) not in targets or (
                        "units" in row and row["units"] != "Games"):
                    known.discard(child)
                elif str(row.get("parentId")) in targets and row.get("units") == "Games":
                    known.add(child)
                return child in known

            while time.monotonic() < stop:
                try:
                    frame = json.loads(socket.recv())
                except websocket.WebSocketTimeoutException:
                    if not snapshot_complete and time.monotonic() > stop - seconds + 40:
                        raise RuntimeError("Opening snapshot timed out")
                    continue
                kind = frame.get("type")
                if kind == "ping":
                    socket.send(json.dumps({"type":"pong"}))
                elif kind == "snapshot":
                    write({"type":kind, "final":bool(frame.get("final")),
                           "events":[row for row in frame.get("events", []) if wanted(row)]})
                    snapshot_complete |= bool(frame.get("final"))
                elif kind == "odds":
                    data = frame.get("data", {})
                    if data.get("sport_id") == 2 and data.get("topic","").endswith("/pre") and wanted(data.get("rec", {})):
                        write({"type":kind, "data":{k:data[k] for k in ("sport_id","topic","ts","op","rec") if k in data}})
                elif kind in {"error", "missed"} or kind == "feed" and frame.get("state",frame.get("status")) != "up":
                    write({"type":"missed"})
                    break
            else:
                write({"type":"capture_end"})
    if not snapshot_complete:
        raise RuntimeError("Incomplete opening snapshot")
    return len(known)


def persist_raw(store, prefix, path):
    digest = hashlib.sha256()
    sizes = []
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            archive = base64.b64encode(gzip.compress(chunk, mtime=0)).decode("ascii")
            if not store.put(f"{prefix}/raw-{len(sizes):04}.json", {"gzip_base64":archive}):
                raise RuntimeError("Duplicate capture part")
            sizes.append(len(chunk))
    store.put(prefix + "/manifest.json", {"sha256":digest.hexdigest(), "part_sizes":sizes})


def main():
    at = now()
    if at >= END:
        print("Private comparison window has ended.")
        return
    store = Store()
    status_file = PREFIX + "/status.json"
    status = store.get(status_file) or {"windows":[], "verified_qualifying":False}
    rehearsal = os.environ.get("REFERENCE_PROBE") == "true"
    if not rehearsal and (status["verified_qualifying"] or len(status["windows"]) >= MAX_WINDOWS):
        return
    snap = recent(store, at)
    if not snap:
        raise RuntimeError("No recent primary scan for comparison")
    targets = available(snap, at, qualifiers=not rehearsal)
    status.update(checked=at.isoformat(), primary_at=snap["observed"], qualifying_count=len(available(snap, at, True)))
    if not targets:
        store.put(status_file, status, replace=True)
        print("No eligible upcoming lines on this scan.")
        return
    if not rehearsal and any(w["scan"] == snap["observed"] for w in status["windows"]):
        return
    ref = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    prefix = PREFIX + "/windows/" + ref
    if not store.put(prefix + "/started.json", {"at":at.isoformat(), "rehearsal":rehearsal}):
        raise RuntimeError("Window already started")
    if not rehearsal:
        status["windows"].append({"ref":ref, "scan":snap["observed"]})
        store.put(status_file, status, replace=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / (ref + ".jsonl")
    seconds = min(45 if rehearsal else 3600, max(1, int((END-now()).total_seconds())))
    try:
        matched = capture(json.loads(os.environ["DESK_RESEARCH_FEED_ACCESS"]), targets, path, seconds)
    finally:
        if path.exists() and path.stat().st_size:
            persist_raw(store, prefix, path)
    report = compare(path, store=store)
    store.put(prefix + "/comparison.json", report)
    store.verify_snapshot(prefix + "/comparison.json", report)
    if rehearsal and (not matched or not report["matched_fixtures"] or not report["stream_seeded_sides"]):
        raise RuntimeError("No exact fixture and games-market matches in rehearsal")
    paired = sum(is_qual(row.get("event", "")) and row.get("first") is not None
                 and sum(p["stream"] is not None for p in row["scans"]) >= 2
                 for row in report["alerted_lines"])
    if not rehearsal:
        status["verified_qualifying"] = bool(paired)
    status["latest_probe" if rehearsal else "latest_capture"] = {
        "ref":ref, "matched":report["matched_fixtures"], "sides":report["stream_seeded_sides"],
        "paired_qualifying_alerts":paired, "finished":now().isoformat()}
    store.put(status_file, status, replace=True)
    print("Private capture, comparison and storage verification completed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit("Private comparison failed: " + type(exc).__name__) from None
