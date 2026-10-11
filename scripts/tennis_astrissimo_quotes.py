"""Bounded fresh Pinnacle quote matching; same contract as category research."""
from datetime import datetime,timedelta,timezone
import csv,io,hashlib,math
from tennis_tournament_category import normalized
MAX_BYTES=1_000_000

def utc(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (TypeError, ValueError):
        return None

def full_name(value):
    return " ".join(sorted(normalized(value).split()))

def tournament_tokens(value):
    ignore = {"atp", "challenger", "masters", "1000", "500", "250", "qualifying", "qualification"}
    return set(normalized(value).split()) - ignore

def load_quotes(root, now):
    folder = root / "data/pinnacle-history"
    files = sorted([p for day in (now, now - timedelta(days=1))
                    for p in folder.glob(f"pinnacle-history-{day:%Y%m%d}-*.csv")], reverse=True)[:8]
    rows, hashes = [], {}
    for file in files:
        if file.stat().st_size > MAX_BYTES:
            continue
        data = file.read_bytes()
        hashes[file.name] = hashlib.sha256(data).hexdigest()
        for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig"))):
            captured, kickoff = utc(row.get("captured_at")), utc(row.get("kickoff_iso"))
            if not captured or not kickoff or not captured <= now < kickoff:
                continue
            if now - captured > timedelta(hours=2) or kickoff - now > timedelta(days=7):
                continue
            if str(row.get("bookmaker", "")).casefold() != "pinnacle":
                continue
            rows.append(row)
    return rows, hashes

def quote_for(row, quotes):
    pair = (full_name(row.get("player1")), full_name(row.get("player2")))
    tokens = tournament_tokens(row.get("event_key") or row.get("tour_name"))
    if not all(pair) or not tokens:
        return None, "missing_identity"
    matched = []
    for q in quotes:
        names = (full_name(q.get("player1_name")), full_name(q.get("player2_name")))
        if set(names) != set(pair) or not tokens <= tournament_tokens(q.get("league_name")):
            continue
        if (row.get("official_category") == "Challenger") != (q.get("league") == "Challenger"):
            continue
        matched.append((q, names != pair))
    if not matched:
        return None, "no_recent_verified_prematch_quote"
    if len({q.get("kickoff_iso") for q, _ in matched}) != 1:
        return None, "ambiguous_start_time"
    q, reverse = max(matched, key=lambda item: utc(item[0]["captured_at"]))
    try:
        a, b = float(q["odds2" if reverse else "odds1"]), float(q["odds1" if reverse else "odds2"])
    except (KeyError, ValueError):
        return None, "invalid_quote"
    if not all(math.isfinite(x) and x > 1 for x in (a, b)):
        return None, "invalid_quote"
    return {"odds1": a, "odds2": b, "captured_at": q["captured_at"],
            "kickoff_iso": q["kickoff_iso"], "market_p1": (1/a) / (1/a + 1/b)}, "verified"
