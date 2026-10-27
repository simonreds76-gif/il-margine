"""Use the approved Odds-API allocation; never auto-select an unavailable book.

This applies only to new Odds-API requests, not historical rows, other providers
or direct connected-browser captures. Legacy scheduler arguments are translated
at the collector boundary so an old Bet365 argument cannot break a free scan.
"""
import json
from pathlib import Path

ALLOCATION = Path(__file__).resolve().parents[1] / "config" / "odds-api-bookmaker-allocation.json"


def selected_bookmakers(requested: str = "", path: Path = ALLOCATION, *, scope: str = "") -> str:
    allocation = json.loads(path.read_text(encoding="utf-8-sig"))
    configured = allocation["selected_bookmakers"]
    if scope:
        configured = allocation.get("market_bookmakers", {}).get(scope, configured)
    approved = list(dict.fromkeys(str(b).strip() for b in configured if str(b).strip()))
    account = {str(b).casefold() for b in allocation.get("account_bookmakers", approved)}
    if any(b.casefold() not in account for b in approved):
        raise ValueError("Configured bookmaker is not in the verified account allocation")
    if not approved:
        raise ValueError("No approved Odds-API bookmakers; refusing automatic account selection")
    allowed = {b.casefold(): b for b in approved}
    requested_books = list(dict.fromkeys(b.strip() for b in requested.split(",") if b.strip()))
    result = [allowed[b.casefold()] for b in requested_books if b.casefold() in allowed]
    # Bet365 is the retired free source, so legacy calls use the approved pair.
    retired = {str(b).casefold() for b in allocation.get("replaced_capture_bookmakers", [])}
    if not requested_books or any(b.casefold() in retired for b in requested_books):
        result = approved
    if not result:
        raise ValueError("Requested bookmaker is outside the approved Odds-API allocation")
    resolved = ",".join(result)
    if requested and resolved != requested:
        print(f"Odds-API allocation: {requested} -> {resolved}; returned quotes retain their actual bookmaker")
    return resolved
