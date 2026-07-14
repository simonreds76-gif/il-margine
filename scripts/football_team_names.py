#!/usr/bin/env python3
"""Canonical club keys for joining football form and external market feeds.

Settlement normalization is deliberately left unchanged. This extra layer maps
the long club names used by odds providers to the abbreviations in the frozen
football-data form history.
"""

from __future__ import annotations

from typing import Any

from settlement_utils import normalize_team_name


FORM_TEAM_ALIASES = {
    "bayer leverkusen": "leverkusen",
    "borussia dortmund": "dortmund",
    "eintracht frankfurt": "ein frankfurt",
    "fsv mainz": "mainz",
    "hellas verona": "verona",
    "lazio rome": "lazio",
    "paris saint germain": "paris sg",
    "real oviedo": "oviedo",
    "saint etienne": "st etienne",
    "wolverhampton": "wolves",
}


def football_form_team_key(value: Any) -> str:
    normalized = normalize_team_name(str(value or ""))
    return FORM_TEAM_ALIASES.get(normalized, normalized)
