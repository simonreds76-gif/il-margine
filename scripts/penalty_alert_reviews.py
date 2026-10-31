"""Read the same private editorial decisions used by hosted Admin.

This is read-only. A missing/unreachable authoritative store must stop notification,
not turn previously closed tickets back into new alerts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CLOSED = {"ignored", "applied", "accepted", "done", "dismissed", "deferred"}


@lru_cache(maxsize=1)
def monitor():
    spec = importlib.util.spec_from_file_location(
        "_penalty_monitor_identity", ROOT / "scripts/build-goalscorer-monitor-snapshot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ticket_id(row):
    return str(row.get("row_id") or monitor().penalty_review_identity(row))


def is_closed(row, state):
    return state["tickets"].get(ticket_id(row), {}).get("status") in CLOSED


def load_reviews(root=ROOT):
    # Jobs can supply scoped env vars; Windows and settlement already use .env.local.
    env = dict(os.environ)
    for name in (".env.local", "env.local"):
        path = root / name
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                key, sep, value = line.partition("=")
                if sep and not key.strip().startswith("#"):
                    env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    url = env.get("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url.startswith("https://") or not key:
        raise RuntimeError("Penalty Admin decisions unavailable: missing private storage configuration; no alert sent")
    request = urllib.request.Request(
        url + "/rest/v1/admin_penalty_state?id=eq.editorial&select=revision,payload",
        headers={"apikey": key, "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            rows = json.load(response)
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError("Missing singleton")
        record = rows[0]
        state = record["payload"]
        if (not isinstance(record["revision"], int)
                or not isinstance(state.get("tickets"), dict)
                or not isinstance(state.get("clubs"), dict)
                or not isinstance(state.get("audit"), list)):
            raise ValueError("Invalid editorial state")
        for entry in state["tickets"].values():
            if (not isinstance(entry, dict) or entry.get("status") not in CLOSED | {"active"}
                    or not entry.get("updated_at")):
                raise ValueError("Invalid ticket decision")
        local_path = root / "data/goalscorer/penalty-duty-review-state.json"
        local = json.loads(local_path.read_text(encoding="utf-8-sig"))["items"] if local_path.exists() else {}
        if not isinstance(local, dict):
            raise ValueError("Invalid local decisions")
        # Hosted entries, including explicit reopen, override legacy local decisions.
        return {**state, "tickets": {**local, **state["tickets"]}, "revision": record["revision"]}
    except Exception:
        # Never expose URLs containing credentials or HTTP authorization headers.
        raise RuntimeError("Penalty Admin decisions unavailable or invalid; no alert sent") from None


def club_key(league, club):
    model = monitor()
    compact = lambda s: re.sub(r"[^a-z0-9]", "", model.norm_text(s))
    aliases = {compact(k): compact(v) for k, v in model.TEAM_ALIASES.items()}
    name = compact(club)
    return str(league).lower() + "|" + aliases.get(name, name)


def editorial_hierarchy(state, league, club, season):
    """Use the same season-scoped Admin authority as the public club page."""
    entry = state.get("clubs", {}).get(club_key(league, club), {})
    order = entry.get("order") or {}
    if not season or entry.get("season") != season:
        return None
    if not all(isinstance(order.get(slot), str) for slot in ("primary", "secondary", "tertiary")):
        return None
    return {**order, "_generated_at": entry.get("at", ""),
            "_source_path": "admin_penalty_state:editorial"}


def apply_editorial_hierarchy(context, approved, as_of):
    """An order saved before the fixture overrides stale, nonempty context slots.

    Player-specific lineup observations follow the player, never the old rank.
    Later or undated edits cannot rewrite historical pre-match evidence.
    """
    merged = dict(context)
    if not approved or not as_of:
        return merged
    try:
        saved = datetime.fromisoformat(str(approved.get("_generated_at", "")).replace("Z", "+00:00"))
        cutoff = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
        if saved.tzinfo is None or cutoff.tzinfo is None or saved > cutoff:
            return merged
    except (ValueError, TypeError):
        return merged
    slots = ("primary", "secondary", "tertiary")
    if not all(isinstance(approved.get(slot), str) for slot in slots):
        return merged
    from goalscorer_penalty_utils import norm_text
    observations = {norm_text(context.get(slot) or ""): {
        suffix: context.get(slot + suffix, "") for suffix in ("_lineup_status", "_match_name")
    } for slot in slots if context.get(slot)}
    for slot in slots:
        player = approved[slot].strip()
        merged[slot] = player
        for suffix in ("_lineup_status", "_match_name"):
            merged[slot + suffix] = observations.get(norm_text(player), {}).get(suffix, "")
    active = norm_text(context.get("active_taker_pre_match") or "")
    merged["active_slot_pre_match"] = next((s for s in slots if active and norm_text(merged[s]) == active), "")
    if not merged["active_slot_pre_match"]:
        merged["active_taker_pre_match"] = ""
    merged["_generated_at"] = approved["_generated_at"]
    merged["_source_path"] = approved.get("_source_path") or "admin_penalty_state:editorial"
    merged.pop("_hierarchy_unrecorded", None)
    return merged


def reviewed_clubs(state):
    dates = {}

    def add(club, at):
        try:
            league, team = club.split("|", 1)
            key = club_key(league, team)
            day = datetime.fromisoformat(str(at).replace("Z", "+00:00")).date()
            dates[key] = max(day, dates.get(key, day))
        except (ValueError, TypeError):
            return

    for item in state["audit"]:
        if item.get("action") in {"done", "save", "ticket_ignored", "ticket_accepted", "ticket_applied"}:
            add(item.get("club", ""), item.get("at"))
    # The original Monitor records no club in its audit, but event IDs identify it.
    for identity, entry in state["tickets"].items():
        parts = identity.split("|")
        if entry.get("status") in CLOSED - {"deferred"} and len(parts) == 5:
            add(parts[1] + "|" + parts[2], entry.get("updated_at"))
    return dates


def filter_quality(payload, state, today=None):
    """Renew age reminders after a human review; retain independent structural issues."""
    today = today or datetime.now(timezone.utc).date()
    reviewed = reviewed_clubs(state)
    kept = []
    for row in payload.get("hierarchy_quality", []):
        if row.get("status") == "hierarchy_review_due":
            day = reviewed.get(club_key(row.get("league", ""), row.get("club", "")))
            existing = re.search(r"review: (\d{4}-\d{2}-\d{2})", str(row.get("detail", "")))
            existing_day = datetime.fromisoformat(existing[1]).date() if existing else None
            if day and 0 <= (today - day).days <= 21:
                continue
            if day and day <= today and (existing_day is None or day > existing_day):
                row = {**row, "detail": f"Last penalty-role review: {day}; review due after 21 days."}
        kept.append(row)
    return {**payload, "hierarchy_quality": kept}


def issue_key(row):
    # A changed player/status/review date is new evidence; age alone is not.
    return json.dumps({k: row.get(k) for k in
                       ("status", "league", "club", "rank", "player", "detail")},
                      sort_keys=True, ensure_ascii=False)


def load_sent(path):
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return set(payload["items"])


def save_sent(path, keys):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema_version": 1, "items": sorted(keys)}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
