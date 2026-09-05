#!/usr/bin/env python3
"""Review club penalty hierarchies without replacing curated judgments.

Default: refresh the internal evidence/review queue. --apply-safe is opt-in.
Manual override, lock, release and revert commands use a persistent control file,
an exclusive writer lock, optimistic revisions and a recoverable write journal.
This program never publishes, sends alerts, or writes to a remote database.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import unicodedata
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LEAGUES = ("epl", "la-liga", "serie-a", "bundesliga", "ligue-1")
SLOTS = ("primary", "secondary", "tertiary")
MAX_SOURCE_HOURS = 48
EVENT_DAYS = 45


class Conflict(ValueError):
    pass


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def norm(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c)).lower()).strip()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def read_json(path, default=None):
    if not path.exists():
        return copy.deepcopy(default)
    # Corrupt state must stop writes, never silently reset controls or audit.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def data_dir(root):
    return root / "data/goalscorer"


def state_path(root):
    return data_dir(root) / "club-penalty-controls.json"


def state(root):
    value = read_json(state_path(root), {"schema_version": 1, "revision": 0, "clubs": {}, "audit": []})
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("revision"), int) or not isinstance(value.get("clubs"), dict) or not isinstance(value.get("audit"), list):
        raise Conflict("Invalid penalty control store; restore or repair it before writing")
    return value


@contextmanager
def writer_lock(root):
    lock = data_dir(root) / ".club-penalty-writer.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise Conflict("Penalty writer is locked; another update or interrupted process needs attention") from exc
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "created_at": now_utc().isoformat()}))
        yield
    finally:
        lock.unlink(missing_ok=True)


def ensure_no_pending(root):
    for path in (data_dir(root) / "penalty-transactions").glob("*.json"):
        if read_json(path).get("status") == "prepared":
            raise Conflict(f"Interrupted penalty transaction {path.stem}; run --recover before further changes")


def commit(root, new_state, league, before, after, audit):
    hierarchy_path = data_dir(root) / f"{league}-penalty-takers.json"
    old_state = state(root)
    journal_path = data_dir(root) / "penalty-transactions" / f"{audit['id']}.json"
    new_state = copy.deepcopy(new_state)
    new_state["revision"] = old_state["revision"] + 1
    summary = {k: v for k, v in audit.items() if k not in {"before_entry", "after_entry"}}
    summary.update(before_hierarchy=hierarchy(audit["before_entry"]), after_hierarchy=hierarchy(audit["after_entry"]))
    new_state["audit"].append(summary)
    # Full club snapshots live once in the immutable journal; control summaries
    # never embed the entire prior audit/history or the other clubs' evidence.
    journal = {"schema_version": 1, "status": "prepared", "id": audit["id"], "league": league, "audit": audit, "summary": summary,
               "before_hierarchy_hash": digest(before), "after_hierarchy_hash": digest(after),
               "before_state_hash": digest(old_state), "after_state_hash": digest(new_state), "after_revision": new_state["revision"]}
    atomic_json(journal_path, journal)
    if digest(before) != digest(after):
        atomic_json(hierarchy_path, after)
    atomic_json(state_path(root), new_state)
    journal["status"] = "committed"
    atomic_json(journal_path, journal)


def recover(root):
    """Complete only recorded transactions whose files still match known states."""
    recovered = []
    for path in sorted((data_dir(root) / "penalty-transactions").glob("*.json")):
        journal = read_json(path)
        if journal.get("status") != "prepared":
            continue
        league = journal.get("league")
        if league not in LEAGUES:
            raise Conflict("Unknown league in recovery journal")
        hierarchy_path = data_dir(root) / f"{league}-penalty-takers.json"
        current_hierarchy, current_state = read_json(hierarchy_path), state(root)
        if (digest(current_hierarchy) not in {journal["before_hierarchy_hash"], journal["after_hierarchy_hash"]}
                or digest(current_state) not in {journal["before_state_hash"], journal["after_state_hash"]}):
            raise Conflict("Recovery refused: newer edits do not match the recorded transaction")
        audit = journal["audit"]
        club_id = audit["club_id"]
        current_hierarchy[club_id.partition("|")[2]] = audit["after_entry"]
        if digest(current_state) == journal["before_state_hash"]:
            current_state["revision"] = journal["after_revision"]
            current_state["clubs"][club_id] = audit["after_control"]
            current_state["audit"].append(journal["summary"])
        atomic_json(hierarchy_path, current_hierarchy)
        atomic_json(state_path(root), current_state)
        journal["status"] = "committed"
        journal["recovered_at"] = now_utc().isoformat()
        atomic_json(path, journal)
        recovered.append(journal["id"])
    return recovered


def fresh(value, now, hours=MAX_SOURCE_HOURS):
    parsed = timestamp(value)
    return parsed is not None and timedelta(0) <= now - parsed <= timedelta(hours=hours)


def safe_url(value):
    parsed = urlparse(str(value or ""))
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def hierarchy(row):
    return {slot: str(row.get(slot) or "").strip() for slot in SLOTS}


def sources_from_command(command):
    sources = command.get("sources") or []
    if not isinstance(sources, list) or not sources or len(sources) > 10:
        raise ValueError("Manual hierarchy changes need 1–10 supporting source links")
    result = []
    for source in sources:
        if not isinstance(source, dict) or not safe_url(source.get("url")):
            raise ValueError("Each supporting source needs a valid HTTPS URL")
        result.append({"label": str(source.get("label") or "Editorial source")[:100], "url": str(source["url"]),
                       "date": str(source.get("date") or now_utc().date().isoformat())[:10], "note": str(source.get("note") or "")[:500]})
    return result


def collect_evidence(root, now):
    previous = read_json(data_dir(root) / "club-penalty-event-evidence.json", {"events": []})
    events = {str(row.get("id")): row for row in previous.get("events", []) if row.get("id")}
    source_health = {}
    for league in LEAGUES:
        prefix = "" if league == "serie-a" else league + "-"
        path = data_dir(root) / f"{prefix}penalty-duty-live-review.json"
        payload = read_json(path, {})
        complete = payload.get("source_health", {}).get("complete") is True
        source_health[league] = {"path": str(path.relative_to(root)).replace("\\", "/"),
                                 "observed_at": payload.get("generated_at"), "fresh": fresh(payload.get("generated_at"), now),
                                 "complete": complete, "errors": payload.get("source_health", {}).get("errors", []),
                                 "status": "ok" if complete and fresh(payload.get("generated_at"), now) else "stale_or_incomplete"}
        for row in payload.get("rows", []):
            event_rows = row.get("event_evidence")
            if not isinstance(event_rows, list) or not event_rows:
                event_rows = [{"id": f"legacy|{league}|{row.get('date')}|{norm(row.get('team'))}|{norm(row.get('actual_taker'))}",
                               "event_date": row.get("date"), "taker": row.get("actual_taker"), "team": row.get("team"),
                               "match": row.get("match"), "primary": row.get("primary_pre_match"), "primary_on_pitch": None,
                               "proof_reason": "legacy event lacks exact match/source/on-pitch evidence"}]
            for evidence in event_rows:
                item = dict(evidence, league=league, observed_at=evidence.get("observed_at") or payload.get("generated_at"),
                            review_source=row.get("review_source"), source_path=source_health[league]["path"])
                item.setdefault("team", row.get("team"))
                if not item.get("id"):
                    continue
                prior = events.get(item["id"])
                if prior and any(prior.get(k) not in (None, "") and prior.get(k) != item.get(k) for k in ("taker", "team", "event_date", "primary", "primary_on_pitch")):
                    item["source_correction"] = True
                    item["previous_evidence"] = {k: prior.get(k) for k in ("taker", "team", "event_date", "primary", "primary_on_pitch", "observed_at")}
                elif prior and prior.get("source_correction"):
                    item["source_correction"] = True
                    item["previous_evidence"] = prior.get("previous_evidence")
                events[item["id"]] = item
    retained = []
    resolutions = read_json(data_dir(root) / "penalty-duty-review-state.json", {"items": {}}).get("items", {})
    for item in events.values():
        try:
            age = (now.date() - datetime.fromisoformat(str(item.get("event_date"))[:10]).date()).days
        except ValueError:
            continue
        if 0 <= age <= EVENT_DAYS:
            # Legacy review IDs use surnames and several historical team aliases.
            # An ambiguous matching editorial decision blocks automation; it does
            # not authorize a different club/player assignment.
            decisions = [{"id": key, "status": decision.get("status")} for key, decision in resolutions.items()
                         if len(key.split("|")) == 5 and key.split("|")[0] == item.get("event_date")
                         and key.split("|")[1] == item.get("league")
                         and norm(key.split("|")[4]) == (norm(item.get("taker")).split() or [""])[-1]
                         and decision.get("status") not in (None, "active")]
            item["manual_ticket_decisions"] = decisions
            retained.append(item)
    return retained, source_health


def club_review(league, club, entry, season, control, events, squad, source_health, now):
    current = hierarchy(entry)
    relevant = [r for r in events if r["league"] == league and norm(r.get("team")) == norm(club)]
    review = {"id": f"{league}|{club}", "league": league, "club": club, "season": season, "current": current,
              "entry_hash": digest(entry), "proposed": None, "status": "unchanged", "confidence": "low",
              "reasons": [], "evidence": relevant, "control": control, "source_observed_at": source_health[league].get("observed_at")}
    reasons = review["reasons"]
    if control.get("locked") or control.get("override") or entry.get("manual_lock") or entry.get("manual_override"):
        review["status"] = "locked"
        reasons.append("Manual lock/override preserves the filed hierarchy")
        return review
    squad_rows = [r for r in squad.get("rows", []) if r.get("league") == league and norm(r.get("club")) == norm(club)]
    squad_names = squad.get("club_squads", {}).get(f"{league}|{club}", [])
    exact_squad = {norm(name) for name in squad_names}
    for row in squad_rows:
        if row.get("status") == "present" and norm(row.get("matched_squad_name")) in exact_squad:
            exact_squad.add(norm(row.get("player")))
    if not fresh(squad.get("generated_at"), now) or not exact_squad:
        reasons.append("Current squad source is stale or missing")
    elif any(norm(name) not in exact_squad for name in current.values() if name) or any(r.get("status") not in {"present"} for r in squad_rows if r.get("player")):
        reasons.append("A filed player is missing or ambiguous in the current squad")
    if source_health[league]["status"] != "ok":
        reasons.append("Penalty event scan is stale, incomplete or lacks coverage metadata")
    if reasons:
        review["status"] = "stale" if not relevant else "review"
        return review
    candidates = [r for r in relevant if norm(r.get("taker")) != norm(current["primary"])]
    if not candidates:
        review["confidence"] = "high" if relevant else "low"
        reasons.append("No conflicting penalty assignment observed; curated dates and order remain unchanged")
        return review
    review["status"] = "review"
    if entry.get("hierarchy_status") in {"conditional", "disputed", "unknown"} or not current["primary"]:
        reasons.append("The filed order is conditional/disputed; editorial judgment is required")
    if any(r.get("source_correction") for r in relevant):
        reasons.append("Provider corrected event identity/context; review the retained versions")
    if any(r.get("manual_ticket_decisions") for r in relevant):
        reasons.append("An existing manual ticket decision covers this evidence; preserve it for editorial review")
    last_review = max(str(entry.get("last_updated") or ""), str((entry.get("last_reviewed") or {}).get("date") or ""))[:10]
    eligible = []
    for event in candidates:
        proof = event.get("on_pitch_proof") or {}
        valid = (event.get("competitive") is True and event.get("finished") is True and event.get("penalty_kind") == "in_match"
                 and event.get("primary_on_pitch") is True and norm(event.get("primary")) == norm(current["primary"])
                 and proof.get("method") == "completed_lineup_timeline" and proof.get("reason") == "on_pitch"
                 and proof.get("player_id") and norm(proof.get("player")) == norm(current["primary"])
                 and proof.get("minute") == event.get("minute") and isinstance(event.get("minute"), int) and event["minute"] > 0
                 and event.get("match_id") and event.get("source_event_id") and safe_url(event.get("source_url"))
                 and event.get("event_date", "") > last_review and event.get("season") == season
                 and norm(event.get("taker")) in exact_squad and timestamp(event.get("observed_at")) is not None
                 and timestamp(event.get("observed_at")) <= now
                 and timestamp(event.get("observed_at")).date().isoformat() >= event.get("event_date", ""))
        if valid:
            eligible.append(event)
    by_taker = defaultdict(set)
    for event in eligible:
        by_taker[norm(event["taker"])].add(str(event["match_id"]))
    qualifying = [name for name, matches in by_taker.items() if len(matches) >= 2]
    if len(qualifying) != 1:
        reasons.append("Need one candidate with at least two distinct recent competitive fixtures and exact incumbent-on-pitch proof after the last editorial review")
    else:
        candidate = qualifying[0]
        if candidate not in {norm(current["secondary"]), norm(current["tertiary"])}:
            reasons.append("An unranked candidate needs editorial confirmation before entering the hierarchy")
        latest_relevant = [r for r in relevant if r.get("event_date", "") > last_review]
        if any(norm(r.get("taker")) != candidate for r in latest_relevant):
            reasons.append("Recent assignments disagree; a shared or situational duty cannot be automatically ranked")
        if any(r not in eligible for r in latest_relevant):
            reasons.append("Some recent events lack complete context; uncertainty must be reviewed")
        if not reasons:
            name = next(name for name in current.values() if norm(name) == candidate)
            ordered = [name] + [name for name in current.values() if name and norm(name) != candidate]
            review["proposed"] = dict(zip(SLOTS, (ordered + ["", ""])[:3]))
            review["status"] = "ready"
            review["confidence"] = "high"
            reasons.append("Two distinct completed competitive matches support the same ranked candidate over the incumbent while both were on pitch; current squad verified")
    return review


def build_report(root, now):
    controls = state(root)
    events, health = collect_evidence(root, now)
    squad = read_json(data_dir(root) / "club-penalty-squad-audit.json", {})
    clubs = []
    for league in LEAGUES:
        payload = read_json(data_dir(root) / f"{league}-penalty-takers.json", {})
        season = payload.get("_meta", {}).get("season", {}).get("label", "")
        for club, entry in payload.items():
            if club.startswith("_") or not isinstance(entry, dict):
                continue
            clubs.append(club_review(league, club, entry, season, controls["clubs"].get(f"{league}|{club}", {}), events, squad, health, now))
    return {"schema_version": 1, "generated_at": now.isoformat(), "mode": "review", "revision": controls["revision"],
            "source_health": health, "squad_observed_at": squad.get("generated_at"), "summary": dict(Counter(r["status"] for r in clubs)),
            "clubs": clubs, "audit": controls["audit"][-100:], "policy": {"source_max_age_hours": MAX_SOURCE_HOURS, "event_window_days": EVENT_DAYS,
            "distinct_matches_required": 2, "automatic_apply_requires_opt_in": True, "membership_is_not_injury_availability": True,
            "default_retains_curated_hierarchies": True}}, events


def changed_entry(entry, order, evidence, actor, reason, now, transaction_id):
    updated = copy.deepcopy(entry)
    updated.update(order)
    date = now.date().isoformat()
    vacancy = any(not name for name in order.values())
    updated.update(last_updated=date, public_updated_at=date,
                   last_verified={"date": date, "by": actor, "method": "reviewed_live_penalty_event" if actor == "automatic_evidence_review" else "reviewed_manual_hierarchy_override"},
                   hierarchy_status="conditional" if vacancy else "probable", condition_note=reason + (" Unfilled positions remain under review." if vacancy else ""))
    # The existing full-season editorial review remains dated to that actual
    # review. A targeted event/override is not silently relabelled as a new audit.
    updated["confidence"] = {slot: "medium" if order[slot] else None for slot in SLOTS}
    evidence_type = "roster_integrity_review" if vacancy else "competitive_penalty_duty_review" if actor == "automatic_evidence_review" else "current_season_board_review"
    updated["latest_evidence"] = {"id": transaction_id, "date": date, "type": evidence_type, "source_count": len({source["url"] for source in evidence})}
    updated.setdefault("flags", {}).update(carryover_from_previous_season=False, weak_evidence=vacancy)
    updated.setdefault("evidence_log", []).append({"id": transaction_id, "date": date, "type": evidence_type, "headline": reason, "editorial_note": reason,
                                                   "sources": evidence, "review": {"status": "approved", "reviewed_by": actor, "reviewed_at": now.isoformat()},
                                                   "affects_hierarchy": True, "detection": actor})
    updated.setdefault("change_log", []).append({"id": transaction_id, "changed_at": now.isoformat(), "change_type": "hierarchy_change", "reason": reason,
                                                 "from": hierarchy(entry), "to": order, "evidence_ids": [transaction_id]})
    return updated


def apply_command(root, command, now, actor="local_admin"):
    ensure_no_pending(root)
    controls = state(root)
    if command.get("expected_revision") != controls["revision"]:
        raise Conflict("Review revision changed; reload before editing")
    club_id = str(command.get("id") or "")
    league, separator, club = club_id.partition("|")
    if not separator or league not in LEAGUES:
        raise ValueError("Unknown club or league")
    path = data_dir(root) / f"{league}-penalty-takers.json"
    before = read_json(path, {})
    if club not in before or club.startswith("_"):
        raise ValueError("Club is not in the current published hierarchy")
    entry = before[club]
    if command.get("expected_entry_hash") != digest(entry):
        raise Conflict("Hierarchy changed since review; reload before editing")
    action = command.get("action")
    reason = str(command.get("reason") or "").strip()
    if not 5 <= len(reason) <= 1200:
        raise ValueError("Enter a reason between 5 and 1200 characters")
    transaction_id = uuid.uuid4().hex
    before_control = copy.deepcopy(controls["clubs"].get(club_id, {}))
    control = copy.deepcopy(before_control)
    new_entry = copy.deepcopy(entry)
    if action in {"override", "apply_safe"}:
        order = command.get("hierarchy")
        if action == "apply_safe":
            report, _ = build_report(root, now)
            reviewed = next(r for r in report["clubs"] if r["id"] == club_id)
            if reviewed["status"] != "ready":
                raise Conflict("Candidate no longer meets the automatic evidence gate")
            order = reviewed["proposed"]
            evidence = [{"label": "FotMob completed match and lineup", "url": e["source_url"], "date": e["event_date"], "note": f"{e['taker']} took with {e['primary']} on pitch"} for e in reviewed["evidence"]]
        else:
            evidence = sources_from_command(command)
        if not isinstance(order, dict) or set(order) != set(SLOTS) or any(not isinstance(order[k], str) or len(order[k]) > 120 for k in SLOTS):
            raise ValueError("Supply primary, secondary and tertiary names (empty backups are allowed)")
        order = {k: order[k].strip() for k in SLOTS}
        names = [norm(name) for name in order.values() if name]
        if any(name in {"tbc", "tbd", "n a", "unknown", "not yet verified"} or not name for name in names):
            raise ValueError("Use real player names or leave an unverified slot empty")
        if len(names) != len(set(names)) or (order["tertiary"] and not order["secondary"]) or (not order["primary"] and names):
            raise ValueError("Hierarchy names must be unique and ordered without gaps")
        new_entry = changed_entry(entry, order, evidence, actor, reason, now, transaction_id)
        new_entry["evidence_log"][-1]["season"] = before.get("_meta", {}).get("season", {}).get("label", "")
        previous_membership = {norm(value.get("player")): value for value in (entry.get("squad_membership") or {}).values() if isinstance(value, dict)}
        current_squad = read_json(data_dir(root) / "club-penalty-squad-audit.json", {})
        membership_rows = [row for row in current_squad.get("rows", []) if row.get("league") == league and norm(row.get("club")) == norm(club) and safe_url(row.get("source_url"))]
        new_entry["squad_membership"] = {}
        for slot, name in order.items():
            if not name:
                continue
            if action == "apply_safe":
                matching = next((row for row in membership_rows if norm(row.get("player")) == norm(name)), None)
                if matching is None:
                    raise Conflict("Current squad verification lacks an exact candidate source")
                membership = {"player": name, "status": "confirmed", "source_url": matching["source_url"], "checked_at": current_squad["generated_at"][:10]}
            else:
                membership = copy.deepcopy(previous_membership.get(norm(name))) or {"player": name, "status": "confirmed", "source_url": evidence[0]["url"], "checked_at": now.date().isoformat(), "method": "manual_editorial_attestation"}
            new_entry["squad_membership"][slot] = membership
        new_entry["unavailable_candidates"] = [row for row in new_entry.get("unavailable_candidates", []) if norm(row.get("player")) not in set(names)]
        if action == "override":
            control.update(locked=True, override=order, reason=reason)
    elif action == "lock":
        control.update(locked=True, reason=reason)
    elif action == "unlock":
        # Unlocking never silently drops a manual override.
        control.update(locked=False, reason=reason)
    elif action == "release":
        control.update(locked=False, override=None, reason=reason)
    elif action == "revert":
        previous = next((r for r in controls["audit"] if r.get("id") == command.get("transaction_id") and r.get("club_id") == club_id), None)
        if not previous or digest(entry) != previous["after_entry_hash"] or digest(before_control) != digest(previous["after_control"]):
            raise Conflict("Revert would overwrite newer changes; select the latest matching transaction")
        journal = read_json(data_dir(root) / "penalty-transactions" / f"{previous['id']}.json")
        if not journal or journal.get("status") != "committed":
            raise Conflict("Original transaction journal is unavailable; cannot safely revert")
        new_entry = copy.deepcopy(journal["audit"]["before_entry"])
        # Restore the filed judgment and its original verification date, while
        # accurately recording that the public hierarchy changed again today.
        new_entry.update(last_updated=now.date().isoformat(), public_updated_at=now.date().isoformat())
        new_entry.setdefault("evidence_log", []).append({"id": transaction_id, "date": now.date().isoformat(),
            "type": "current_season_board_review", "headline": "Previous hierarchy restored", "editorial_note": reason,
            "sources": [], "review": {"status": "approved", "reviewed_by": actor, "reviewed_at": now.isoformat()},
            "affects_hierarchy": True, "detection": "manual_revert", "reverts": previous["id"]})
        new_entry.setdefault("change_log", []).append({"id": transaction_id, "changed_at": now.isoformat(), "change_type": "hierarchy_revert",
            "reason": reason, "from": hierarchy(entry), "to": hierarchy(new_entry), "evidence_ids": [transaction_id]})
        control.update(locked=True, override=hierarchy(new_entry), reason=reason)
    else:
        raise ValueError("Unknown hierarchy action")
    control.update(updated_at=now.isoformat(), actor=actor)
    controls["clubs"][club_id] = control
    after = copy.deepcopy(before)
    after[club] = new_entry
    audit = {"id": transaction_id, "at": now.isoformat(), "actor": actor, "action": action, "club_id": club_id, "reason": reason,
             "before_entry": entry, "after_entry": new_entry, "before_entry_hash": digest(entry), "after_entry_hash": digest(new_entry),
             "before_control": before_control, "after_control": control, "reverts": command.get("transaction_id") if action == "revert" else None}
    commit(root, controls, league, before, after, audit)
    return audit


def run(root, *, apply_safe=False, inspect_only=False, command=None, now=None):
    now = now or now_utc()
    if inspect_only:
        ensure_no_pending(root)
        return build_report(root, now)[0]
    with writer_lock(root):
        ensure_no_pending(root)
        if command:
            apply_command(root, command, now)
        report, events = build_report(root, now)
        applied = []
        if apply_safe:
            for club in report["clubs"]:
                if club["status"] == "ready":
                    audit = apply_command(root, {"action": "apply_safe", "id": club["id"], "expected_revision": state(root)["revision"],
                                               "expected_entry_hash": club["entry_hash"], "reason": club["reasons"][0]}, now, "automatic_evidence_review")
                    applied.append(audit["id"])
            report, events = build_report(root, now)
        report["mode"] = "apply_safe" if apply_safe else "review"
        report["applied_transactions"] = applied
        atomic_json(data_dir(root) / "club-penalty-event-evidence.json", {"schema_version": 1, "updated_at": now.isoformat(), "events": events})
        atomic_json(data_dir(root) / "club-penalty-hierarchy-review.json", report)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--inspect", action="store_true", help="Read-only JSON report for the local admin panel")
    parser.add_argument("--apply-safe", action="store_true", help="Apply only currently qualified, unlocked candidates")
    parser.add_argument("--command-json", help="Manual command JSON with expected revision and entry hash")
    parser.add_argument("--recover", action="store_true", help="Complete a verified interrupted transaction")
    parser.add_argument("--summary", action="store_true", help="Print compact automation status")
    args = parser.parse_args()
    try:
        if args.recover:
            with writer_lock(args.root):
                result = {"recovered": recover(args.root)}
        else:
            result = run(args.root, apply_safe=args.apply_safe, inspect_only=args.inspect,
                         command=json.loads(args.command_json) if args.command_json else None)
        if args.summary:
            result = {key: result.get(key) for key in ("generated_at", "mode", "revision", "summary", "applied_transactions", "recovered") if key in result}
        print(json.dumps({"ok": True, "report": result}, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "conflict": isinstance(exc, Conflict)}))
        return 2 if isinstance(exc, Conflict) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
