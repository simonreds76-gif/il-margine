from __future__ import annotations

import html
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HIERARCHY_PATH = ROOT / "data" / "goalscorer" / "serie-a-penalty-takers.json"
HIERARCHY_SLOTS = ("primary", "secondary", "tertiary")
KNOWN_GIVEN_NAME_EQUIVALENTS = {
    frozenset(("tasos", "anastasios")),
}


def norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = normalized.translate(str.maketrans({"ı": "i", "ł": "l", "ø": "o", "đ": "d", "ð": "d", "þ": "th"}))
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


def player_match_score(left: str, right: str) -> int:
    left_key = norm_text(left)
    right_key = norm_text(right)
    if not left_key or not right_key:
        return 0
    if left_key == right_key:
        return 100

    left_tokens = left_key.split()
    right_tokens = right_key.split()
    if len(left_tokens) == len(right_tokens) and sorted(left_tokens) == sorted(right_tokens):
        return 94

    left_first = left_tokens[0]
    right_first = right_tokens[0]
    left_last = left_tokens[-1]
    right_last = right_tokens[-1]

    if left_last == right_last:
        if left_first == right_first:
            return 96
        # Only accept a differing given name when one side is an initial. Two
        # complete given names with the same surname are different people.
        if min(len(left_first), len(right_first)) == 1 and (
            left_first.startswith(right_first) or right_first.startswith(left_first)
        ):
            return 90
        if len(left_tokens) == 1 or len(right_tokens) == 1:
            return 82
        left_given = " ".join(left_tokens[:-1])
        right_given = " ".join(right_tokens[:-1])
        if left_given in right_given or right_given in left_given:
            return 90
        if min(len(left_first), len(right_first)) >= 3 and (
            left_first in right_first or right_first in left_first
        ):
            return 88
        if frozenset((left_first, right_first)) in KNOWN_GIVEN_NAME_EQUIVALENTS:
            return 88
        return 0

    if left_first == right_first:
        last_ratio = SequenceMatcher(None, left_last, right_last).ratio()
        if last_ratio >= 0.88:
            return 88

    if left_key in right_key or right_key in left_key:
        return 76

    full_ratio = SequenceMatcher(None, left_key, right_key).ratio()
    if full_ratio >= 0.9:
        return 72

    overlap = len(set(left_tokens) & set(right_tokens))
    if overlap >= 2:
        return 68
    return 0


def best_name_match(target_name: str, candidate_names: Iterable[str], minimum_score: int = 68) -> Optional[str]:
    scored = []
    for candidate_name in candidate_names:
        score = player_match_score(target_name, candidate_name)
        if score > 0:
            scored.append((score, candidate_name))

    if not scored:
        return None

    scored.sort(key=lambda item: (item[0], norm_text(item[1])), reverse=True)
    best_score, best_name = scored[0]
    if best_score < minimum_score:
        return None

    if len(scored) > 1 and scored[1][0] == best_score and norm_text(scored[1][1]) != norm_text(best_name):
        return None
    return best_name


def load_penalty_hierarchy(
    path: str | Path = DEFAULT_HIERARCHY_PATH,
    team_key_func=None,
) -> Dict[str, dict]:
    hierarchy_path = Path(path)
    if not hierarchy_path.exists():
        return {}

    with hierarchy_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    loaded: Dict[str, dict] = {}
    for team_name, entry in raw.items():
        if str(team_name).startswith("_"):
            continue
        team_key = team_key_func(team_name) if team_key_func else norm_text(team_name)
        item = dict(entry)
        item["team"] = team_name
        item["team_key"] = team_key
        for slot in HIERARCHY_SLOTS:
            item[f"{slot}_key"] = norm_text(item.get(slot, ""))
        loaded[team_key] = item
    return loaded


def penalty_transfer_info(
    hierarchy: Optional[dict],
    available_names: Iterable[str],
) -> dict:
    names = [name for name in available_names if name]
    if not hierarchy or not names:
        return {
            "active_taker": "",
            "active_slot": "",
            "penalty_transfer": False,
            "inherited_from": "",
            "transfer_level": "",
        }

    for slot in HIERARCHY_SLOTS:
        slot_name = hierarchy.get(slot, "")
        if not slot_name:
            continue
        matched_name = best_name_match(slot_name, names)
        if matched_name is None:
            continue
        is_transfer = slot != "primary"
        return {
            "active_taker": matched_name,
            "active_slot": slot,
            "penalty_transfer": is_transfer,
            "inherited_from": hierarchy.get("primary", "") if is_transfer else "",
            "transfer_level": slot if is_transfer else "",
        }

    return {
        "active_taker": "",
        "active_slot": "",
        "penalty_transfer": False,
        "inherited_from": "",
        "transfer_level": "",
    }


def penalty_role_for_player(
    hierarchy: Optional[dict],
    player_name: str,
) -> str:
    if not hierarchy or not player_name:
        return "none"

    for slot in HIERARCHY_SLOTS:
        slot_name = hierarchy.get(slot, "")
        if not slot_name:
            continue
        if best_name_match(player_name, [slot_name]) is not None:
            return slot
    return "none"
