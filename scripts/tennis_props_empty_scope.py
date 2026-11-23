"""Recognise a checked, empty main-tour props window in the existing refresh."""
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json

from tennis_bookmaker_check import check_receipt, stamp
from tennis_pairing_consistency import board_state, expected_props, native_epoch


STATE = "NO_ELIGIBLE_PROPS_FIXTURES"


def empty_csv(path, fields):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        return fields.issubset(reader.fieldnames or ()) and next(reader, None) is None


def verified_empty(root, day, *, now=None, not_before=None, require_board=False, days_ahead=3):
    """Return comparable evidence only when both independent checks agree."""
    now = now or datetime.now(timezone.utc)
    if day != now.astimezone(timezone.utc).date().isoformat():
        return None
    receipt, error = check_receipt(root, day, now=now)
    if error or not receipt or receipt.get("all_sources_checked") is not True:
        return None
    inbox = root / "data/tennis-props/inbox"
    try:
        for source in receipt["sources"].values():
            if (source["status"] != "NO_VERIFIED_MARKETS" or source["quotes"] != 0
                    or source["error_types"] != []):
                return None
            if not_before and stamp(source["checked_at"]) < not_before:
                return None
        if not_before and stamp(receipt["generated_at"]) < not_before:
            return None
        two_way = {"event_id", "bookmaker", "line", "market", "over_odds", "under_odds"}
        three_way = {"event_id", "bookmaker", "player1_odds", "draw_odds", "player2_odds"}
        for kind, prefix, fields in (
            ("props", "bet365-lines", two_way),
            ("most_aces", "betmgm-most-aces-1x2", three_way),
            ("most_df", "most-df-1x2", three_way),
        ):
            name = f"{prefix}-{day}.csv"
            if receipt["artifacts"][kind]["name"] != name or not empty_csv(inbox / name, fields):
                return None
        for prefix, fields in (("betsbk-lines", two_way), ("bet365-most-aces-1x2", three_way)):
            extra = inbox / f"{prefix}-{day}.csv"
            if extra.exists() and not empty_csv(extra, fields):
                return None
        if require_board:
            board = board_state(root, day, days_ahead=days_ahead)
            if (board["state"] != "CURRENT" or board["coverage"] != "COMPLETE"
                    or board["expected_fixtures"] or board["actual_sides"]
                    or not board["board_sha256"] or not board["player_history_current"]):
                return None
            epoch = board["native_epoch"]
        else:
            epoch = native_epoch(root)
            held = []
            if expected_props(root, day, days_ahead, held) or held:
                return None
        # A stale/header-only export alone cannot establish an empty day.
        extraction = json.loads((root / "data/oncourt/extraction-status.json").read_bytes())
        completed = stamp(extraction.get("completed_at"))
        if (extraction["state"] != "VERIFIED" or not completed or completed > now
                or completed.astimezone(timezone.utc).date().isoformat() != day):
            return None
        if any(v["sha256"] != extraction["exports"][k]["sha256"] for k, v in epoch.items()):
            return None
        return {"state": STATE, "as_of": day, "days_ahead": days_ahead,
                "eligible_fixtures": 0, "price_rows": 0, "sources_checked": len(receipt["sources"]),
                "bookmakers_checked_at": receipt["generated_at"], "schedule_verified_at": completed.isoformat(),
                "bookmaker_receipt_sha256": sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest(),
                "schedule_sha256": {k: v["sha256"] for k, v in epoch.items()}}
    except (OSError, KeyError, TypeError, ValueError, csv.Error):
        return None
