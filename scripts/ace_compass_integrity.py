"""Completed singles only; one unambiguous result/stat line per exact match."""
import re
from collections import Counter, defaultdict


def revision_transition_allowed(previous_hash, config):
    allowed = {
        "source-contract-v3": {'2a0130a79ff868a21f36abfbf51682144992558103b64899ae214729a78de633'},
        "completed-singles-by-phase-v1": {"82a9d822d2a17fdb9acf88db8779d0d4648fc28679a4d28fa290a358ecd13294"},
        "same-event-phase-reference-v2": {
            "82a9d822d2a17fdb9acf88db8779d0d4648fc28679a4d28fa290a358ecd13294",
            "190de593f4a85e44ce9e02cc265923eb665f8bd6b8306bdf953f02a9b5ca3966",
        },
    }
    registered = config.get("supersedes_config_hashes", [config.get("supersedes_config_hash")])
    return previous_hash in allowed.get(config.get("implementation_revision"), set()) and previous_hash in registered


def revision_records(records, revision):
    if not revision:
        return records, []
    return ([r for r in records if r.get("implementation_revision") == revision],
            [r for r in records if r.get("implementation_revision") != revision])


def event_phase(round_id):
    try:
        value = int(str(round_id))
    except (TypeError, ValueError):
        return None
    return "qualifying" if 0 < value < 4 else "main_draw" if value in {4, 5, 6, 7, 8, 9, 10, 11, 12} else None


def completed_score(value):
    text = str(value or "").strip()
    if not text or re.search(r"RET|W/O|DEF|ABN|\[", text, re.I):
        return False
    sets = re.findall(r"(\d+)-(\d+)(?:\(\d+\))?", text)
    if not sets or re.sub(r"\d+-\d+(?:\(\d+\))?|\s", "", text):
        return False
    scores = [(int(a), int(b)) for a, b in sets]
    if any(not ((max(a, b) == 6 and min(a, b) <= 4) or (max(a, b) >= 7 and abs(a-b) == 2) or {a, b} == {6, 7}) for a, b in scores):
        return False
    wins, losses = sum(a > b for a, b in scores), sum(b > a for a, b in scores)
    return wins in {2, 3} and losses < wins and scores[-1][0] > scores[-1][1]


def clean_event_rows(stats, games, names):
    def key(row):
        return tuple(str(row.get(field) or "") for field in ("winner_id", "loser_id", "tour_id", "round_id"))
    game_groups, stat_groups = defaultdict(list), defaultdict(list)
    for row in games:
        game_groups[key(row)].append(row)
    for row in stats:
        stat_groups[key(row)].append(row)
    good_stats, good_games, excluded = [], [], Counter()
    for identity, records in game_groups.items():
        if len({(r.get("date"), r.get("result")) for r in records}) != 1:
            excluded["conflicting_results"] += 1
            continue
        game = records[0]
        if any(not names.get(player) or "/" in names[player] for player in identity[:2]) or identity[0] == identity[1]:
            excluded["doubles_or_unknown_identity"] += 1
            continue
        if not completed_score(game.get("result")):
            excluded["unfinished_or_invalid_score"] += 1
            continue
        candidates = stat_groups.get(identity, [])
        if not candidates:
            excluded["missing_statistics"] += 1
            continue
        if len({tuple(sorted(row.items())) for row in candidates}) != 1:
            excluded["conflicting_statistics"] += 1
            continue
        stat = candidates[0]
        try:
            for side in ("w", "l"):
                points = int(stat.get(f"{side}_svpt") or stat.get(f"{side}_fsof") or "")
                aces, dfs = int(stat.get(f"{side}_ace", "")), int(stat.get(f"{side}_df", ""))
                if points <= 0 or min(aces, dfs) < 0 or aces + dfs > points:
                    raise ValueError("invalid counts")
        except (TypeError, ValueError):
            excluded["invalid_or_missing_counts"] += 1
            continue
        good_stats.append(stat)
        good_games.append(game)
        excluded["duplicate_rows_removed"] += len(records) - 1 + len(candidates) - 1
    return good_stats, good_games, dict(excluded)


def match_best_of(tour, tournament, round_id, *, slam=False):
    """Conventional singles. Explicit OnCourt round identity is required.

    Round 8 is round robin. Men's Wimbledon Q3 is BO5; Q1/Q2 and
    other Slam qualifying are BO3. Next Gen is unsupported, never guessed.
    Used for the audited 2021-2026 cohort, not a historical format registry.
    """
    try:
        rnd = int(str(round_id))
    except (TypeError, ValueError):
        return None
    phase = event_phase(rnd)
    name = re.sub(r"[^a-z0-9]+", " ", str(tournament or "").lower())
    if phase is None or "next gen" in name or "nextgen" in name or "laver cup" in name:
        return None
    if str(tour).upper() not in {"ATP", "WTA"}:
        return None
    if str(tour).upper() == "WTA":
        return 3
    wimbledon = bool(re.search(r"\bwimbledon\b", name))
    is_slam = slam or any(x in name for x in (
        "australian open", "roland garros", "french open", "wimbledon", "us open", "u s open", "grand slam"))
    return 5 if (wimbledon and rnd == 3) or (is_slam and phase == "main_draw") else 3


def event_condition_eligible(tournament):
    """An edition is not a single court-condition unit at multi-site events.

    Valid ordinary singles may still enter player history. No artificial venue
    aggregate until match-level venue identity is available.
    """
    name = str(tournament or "").lower()
    return not any(token in name for token in (
        "united cup", "atp cup", "davis cup", "billie jean king", "fed cup", "laver cup", "next gen", "nextgen"))
