"""Daily comparison estimates from smoothed player rates, independent of quotes.

Keep this versioned calculation separate from the legacy tip selection model.
Use its existing 900-minute shrinkage and team goal budget, rather than raw xG
shares that can give a new striker part of a fixed 2% fallback pool.
"""
import math

VERSION = "daily_shrunk_rates_v2_20260909"


def allocate_rates(candidates, predictions, model, lineup, is_home):
    entries = {e.get("name"): e for e in (lineup or {}).get("home_starters" if is_home else "away_starters", [])}
    weights = []
    for c in candidates:
        role = entries.get(c.get("lineup_match_name"), {}).get("role_group")
        position = c.get("position") or "Unknown"
        if position.lower() in {"sub", "unknown", ""}:
            position = {"DEF": "DC", "MID": "MC", "FW": "FW"}.get(role, position)
        recent, long = c.get("player_recent"), c.get("player_long")
        rate = model["build_player_rate"](recent, long, position) if recent else model["position_prior"](position)
        minutes = min(90.0, max(0.0, c.get("expected_minutes", 0.0)))
        weights.append(max(0.0, rate) * minutes / 90.0 * c.get("daily_role_factor", 1.0))
    total = sum(weights)
    estimates = []
    for c, old, weight in zip(candidates, predictions, weights):
        share = weight / total * (1 - model["UNALLOCATED_SHARE_FLOOR"]) if total else 0.0
        non_pen = old["team_expected_npxg"] * share
        penalty = max(0.0, old.get("penalty_lambda", 0.0))
        recent = c.get("player_recent") or {}
        limited = bool(c.get("context_only_prior") or recent.get("n_matches", 0) < model["MIN_PLAYER_MATCHES"])
        estimates.append(dict(probability=-math.expm1(-(non_pen + penalty)), non_pen_lambda=non_pen,
            penalty_lambda=penalty, rate_basis="position_prior" if not recent else "shrunk_player_history",
            limited_data=limited, history_matches=recent.get("n_matches", 0),
            history_minutes=c.get("history_minutes", 0.0), method="fallback" if limited else "model"))
    return estimates
