#!/usr/bin/env python3
"""Retrospective, fixed OnCourt rate-trend experiment; no live model writes.

The available ledger was selected by the incumbent. Results apply only to those
recorded contracts, not to a full bookmaker board or prospective betting policy.
Historical source publication vintages are unavailable. Exact match-date lags
remove obvious outcome leakage but cannot prove historical data availability.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import runpy
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from tennis_props_model import negative_binomial_line_probabilities

AUDIT = runpy.run_path(str(ROOT / "scripts/tennis-props-feature-audit.py"))
BOARD = runpy.run_path(str(ROOT / "scripts/build-tennis-props-board.py"))
MODEL_IDENTITY_FIELDS = ("model", "model_id", "model_name", "model_version", "variant", "variant_id", "gate_version")
rows, count, match_key, surface = (AUDIT[k] for k in ("rows", "count", "match_key", "surface"))


def norm(value):
    value = str(value or "").strip()
    if "," in value:
        last, first = value.split(",", 1)
        value = first + " " + last
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def stamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def numeric(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (ValueError, TypeError):
        return None


def generic_contract_key(row):
    fields = (row.get('event_id'), norm(row.get('bookmaker')), row.get('tour'),
              norm(row.get('tournament')), str(row.get('date', ''))[:4],
              norm(row.get('player')), norm(row.get('opponent')), row.get('market'))
    line = numeric(row.get('line'))
    side = str(row.get('side') or '').upper()
    if not all(fields) or line is None or side not in ('OVER', 'UNDER'):
        return None
    return (*fields, line, side, *(str(row.get(k) or '') for k in MODEL_IDENTITY_FIELDS))


def temporal_cutoff(row, fixture_day=None):
    capture, entry, kickoff = (stamp(row.get(k)) for k in ("capture_ts", "logged_at_utc", "match_start_utc"))
    if not all((capture, entry, kickoff)):
        return None, "missing_or_invalid_timestamp"
    if capture >= kickoff or entry >= kickoff:
        return None, "poststart_capture_or_registration"
    if capture > entry:
        return None, "capture_after_registration"
    if fixture_day is not None and (capture.date() > fixture_day or entry.date() > fixture_day):
        return None, "registration_after_source_fixture_day"
    return min(capture.date(), entry.date(), fixture_day or kickoff.date()), "ok"


def prepare_ledger(ledger, config):
    eligible, excluded = [], []
    seen = set()
    # Earliest immutable registration wins even if old input has not run quarantine.
    ordered = sorted(ledger, key=lambda r: (str(r.get("logged_at_utc", "")), str(r.get("capture_ts", ""))))
    for row in ordered:
        if row.get("market") not in config["markets"]:
            continue
        reason = None
        if row.get("quarantine_reason") or row.get("duplicate_of_signal_id"):
            reason = "quarantined"
        elif row.get("settlement_status") != "settled" or row.get("result", "").lower() not in {"win", "loss", "push"}:
            reason = "not_a_settled_betting_contract"
        else:
            key = generic_contract_key(row)
            if key is None:
                reason = "missing_stable_contract_identity"
            elif key in seen:
                reason = "duplicate_same_contract"
            else:
                seen.add(key)
        if reason is None:
            _, reason = temporal_cutoff(row)
            if reason == "ok":
                reason = None
        if reason is None:
            values = {k: numeric(row.get(k)) for k in ("line", "selected_odds", "projection_mean", "fair_odds")}
            if (any(v is None for v in values.values()) or values["line"] < 0 or values["selected_odds"] <= 1
                    or values["projection_mean"] <= 0 or values["fair_odds"] < 1 or count(row.get("actual")) is None
                    or row.get("side", "").upper() not in {"OVER", "UNDER"}
                    or row.get("distribution") != "negative_binomial" or row.get("tour") not in config["alpha"]):
                reason = "invalid_frozen_contract"
        if reason:
            excluded.append({"signal_id": row.get("signal_id", ""), "market": row.get("market"), "reason": reason})
        else:
            eligible.append(row)
    return eligible, excluded


def load_source(source, ledger, config):
    """Read source once; exact date + four-part round key, no fuzzy event join."""
    histories, fixtures, identities, quality = {}, {}, {}, Counter()
    cutoffs = [temporal_cutoff(r)[0] for r in ledger]
    earliest = min(cutoffs) - timedelta(days=config["baseline_days"])
    latest = max(stamp(r["match_start_utc"]).date() for r in ledger) + timedelta(days=21)
    courts = {r["id"]: r["name"] for r in rows(source / "courts.csv")}
    for tour in sorted({r["tour"] for r in ledger}):
        suffix = tour.lower()
        wanted_names = {norm(r[k]) for r in ledger if r["tour"] == tour for k in ("player", "opponent")}
        name_ids = defaultdict(set)
        for player in rows(source / f"players_{suffix}.csv"):
            if norm(player.get("name")) in wanted_names:
                name_ids[norm(player["name"])].add(player["id"])
        identities[tour] = {name: next(iter(ids)) for name, ids in name_ids.items() if len(ids) == 1}
        wanted = set(identities[tour].values())
        tournaments = {r["id"]: r for r in rows(source / f"tours_{suffix}.csv")}
        games, conflicts = {}, set()
        for game in rows(source / f"games_{suffix}.csv"):
            try:
                played = date.fromisoformat(game.get("date", "")[:10])
            except ValueError:
                continue
            key = match_key(game)
            tournament = tournaments.get(key[2], {})
            if not (earliest <= played <= latest and wanted.intersection(key[:2])
                    and BOARD["is_supported_main_tour"](tournament)):
                continue
            if any(token in game.get("result", "").upper() for token in ("RET", "W/O", "WO", "DEF", "ABD")):
                quality["retired_or_walkover_game"] += 1
                continue
            if key in games and games[key]["game"] != game:
                conflicts.add(key)
            games[key] = {"game": game, "played": played, "key": key,
                          "fixture_id": tour + "|" + "|".join(key), "tournament": tournament.get("name", ""),
                          "surface": surface(courts.get(tournament.get("court_id"), ""))}
        stats = {}
        for stat in rows(source / f"stat_{suffix}.csv"):
            key = match_key(stat)
            if key not in games:
                continue
            if key in stats and stats[key] != stat:
                conflicts.add(key)
            stats[key] = stat
        histories[tour] = defaultdict(list)
        fixtures[tour] = defaultdict(list)
        for key, game in games.items():
            if key in conflicts:
                quality["conflicting_source_key"] += 1
                continue
            stat = stats.get(key)
            game["stat"] = stat
            fixtures[tour][tuple(sorted(key[:2]))].append(game)
            for prefix, other, player_id in (("w", "l", key[0]), ("l", "w", key[1])):
                if player_id not in wanted:
                    continue
                record = {"player_id": player_id, "played": game["played"], "surface": game["surface"],
                          "fixture_id": game["fixture_id"], "aces_valid": False, "double_faults_valid": False}
                if stat:
                    values = {"sp": count(stat.get(f"{prefix}_svpt")), "rp": count(stat.get(f"{other}_svpt")),
                              "ace": count(stat.get(f"{prefix}_ace")), "allowed": count(stat.get(f"{other}_ace")),
                              "df": count(stat.get(f"{prefix}_df")), "second": count(stat.get(f"{prefix}_w2sof")),
                              "first": count(stat.get(f"{prefix}_fs"))}
                    record.update(values)
                    record["aces_valid"] = (all(values[k] is not None for k in ("sp", "rp", "ace", "allowed"))
                                              and values["sp"] > 0 and values["rp"] > 0
                                              and values["ace"] <= values["sp"] and values["allowed"] <= values["rp"])
                    record["double_faults_valid"] = (all(values[k] is not None for k in ("sp", "second", "df", "first"))
                                                     and values["sp"] > 0 and 0 <= values["df"] <= values["second"] <= values["sp"]
                                                     and values["second"] + values["first"] == values["sp"])
                for market in config["markets"]:
                    quality[f"{market}_{'valid' if record[market + '_valid'] else 'invalid_or_missing'}_player_observations"] += 1
                histories[tour][player_id].append(record)
    return histories, fixtures, identities, dict(quality)


def tournament_identity(value):
    return norm(BOARD["scheduled_tournament_name"](value))


def match_fixture(row, candidate_games, player_id, opponent_id):
    start = stamp(row["match_start_utc"]).date()
    matches = [g for g in candidate_games if set(g["key"][:2]) == {player_id, opponent_id}
               and abs((g["played"] - start).days) <= 7
               and tournament_identity(g["tournament"]) == tournament_identity(row.get("tournament"))
               and (not row.get("round_id") or g["key"][3] == row["round_id"])]
    if len(matches) != 1:
        return None, "ambiguous_source_fixture" if matches else "unmatched_source_fixture"
    fixture = matches[0]
    if not fixture["stat"]:
        return None, "missing_target_stat"
    prefix = "w" if fixture["key"][0] == player_id else "l"
    field = "ace" if row["market"] == "aces" else "df"
    if count(fixture["stat"].get(f"{prefix}_{field}")) != count(row.get("actual")):
        return None, "source_actual_disagrees_with_ledger"
    return fixture, "ok"


def aggregate(history, target_surface, cutoff, days, market):
    eligible = [r for r in history if r["surface"] == target_surface and cutoff - timedelta(days=days) <= r["played"] < cutoff]
    valid = [r for r in eligible if r.get(market + "_valid")]
    fields = ("sp", "rp", "ace", "allowed") if market == "aces" else ("sp", "second", "df")
    return dict({k: sum(r[k] for r in valid) for k in fields}, matches=len(valid), eligible=len(eligible),
                latest=max((r["played"].isoformat() for r in valid), default=""))


def rate_trend(player_history, opponent_history, target_surface, cutoff, market, config):
    values = {}
    roles = [("player", player_history)] + ([("opponent", opponent_history)] if market == "aces" else [])
    for role, history in roles:
        for window, days in (("baseline", config["baseline_days"]), ("recent", config["recent_days"])):
            summary = aggregate(history, target_surface, cutoff, days, market)
            values[f"{role}_{window}"] = summary
            denom = "rp" if role == "opponent" else "sp"
            if summary["matches"] < config[f"{window}_min_matches"] or summary[denom] < config[f"{window}_min_points"]:
                return None, values, f"insufficient_{role}_{window}_support"
    def shrunk_ratio(base, recent, numerator, denominator, prior):
        baseline = base[numerator] / base[denominator] if base[denominator] else 0
        if baseline <= 0:
            return None
        posterior = (recent[numerator] + prior * baseline) / (recent[denominator] + prior)
        return posterior / baseline
    base, recent = values["player_baseline"], values["player_recent"]
    if market == "aces":
        server = shrunk_ratio(base, recent, "ace", "sp", config["point_prior"])
        returned = shrunk_ratio(values["opponent_baseline"], values["opponent_recent"], "allowed", "rp", config["point_prior"])
        trend = math.sqrt(server * returned) if server is not None and returned is not None else None
    else:
        df = shrunk_ratio(base, recent, "df", "second", config["second_serve_prior"])
        share = shrunk_ratio(base, recent, "second", "sp", config["point_prior"])
        trend = df * share if df is not None and share is not None else None
    if trend is None:
        return None, values, "zero_baseline_rate"
    multiplier = max(config["multiplier_min"], min(config["multiplier_max"], 1 - config["trend_blend"] + config["trend_blend"] * trend))
    return multiplier, values, "ok"


def assign_phases(records, fraction):
    fixture_days = {r["fixture_id"]: r["fixture_date"] for r in records}
    days = sorted(set(fixture_days.values()))
    if len(days) < 2:
        return {k: "development" for k in fixture_days}, None
    boundary = min(days[1:], key=lambda d: abs(sum(day < d for day in fixture_days.values()) / len(fixture_days) - fraction))
    return {k: "evaluation" if day >= boundary else "development" for k, day in fixture_days.items()}, boundary


def outcomes(actual, line, side, odds):
    push = actual == line
    win = (actual > line) if side == "OVER" else (actual < line)
    return (0 if push else odds - 1 if win else -1), (None if push else int(win))


def physical_contract_key(row, fixture_id, player_id):
    """One quoted contract in research, even across provider IDs/model labels.

    This never mutates the live ledger's deliberately separate model evidence.
    Earliest registration supplies the single frozen forecast used here.
    """
    return (fixture_id, player_id, row["market"], norm(row["bookmaker"]),
            str(Decimal(row["line"]).normalize()), row["side"].upper())


def prediction(mean, row, config):
    over, under, push = negative_binomial_line_probabilities(float(row["line"]), mean, config["alpha"][row["tour"]][row["market"]])
    win = over if row["side"].upper() == "OVER" else under
    loss = under if row["side"].upper() == "OVER" else over
    conditional = win / (1 - push) if push < 1 else 0.5
    return {"mean": mean, "p_win": win, "p_push": push, "p_conditional": conditional,
            "ev": win * (float(row["selected_odds"]) - 1) - loss}


def score_probability(probability, target):
    if target is None:
        return {"brier": None, "log_loss": None}
    probability = max(1e-12, min(1 - 1e-12, probability))
    return {"brier": (probability - target) ** 2,
            "log_loss": -(target * math.log(probability) + (1 - target) * math.log(1 - probability))}


def paired_interval(records, value, config):
    grouped = defaultdict(list)
    for row in records:
        delta = value(row)
        if delta is not None:
            grouped[row["fixture_id"]].append(delta)
    values = [statistics.mean(v) for v in grouped.values()]
    if not values:
        return {"fixtures": 0, "equal_fixture_mean_delta": None, "ci95": None}
    if len(values) < 2:
        return {"fixtures": len(values), "equal_fixture_mean_delta": statistics.mean(values), "ci95": None}
    rng = random.Random(config["bootstrap_seed"])
    samples = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(config["bootstrap_replicates"]))
    return {"fixtures": len(values), "equal_fixture_mean_delta": statistics.mean(values),
            "ci95": [samples[int(.025 * (len(samples) - 1))], samples[int(.975 * (len(samples) - 1))]]}


def metrics(records, config):
    result = {"contracts": len(records), "fixtures": len({r["fixture_id"] for r in records}),
              "calendar_start": min((r["fixture_date"] for r in records), default=None),
              "calendar_end": max((r["fixture_date"] for r in records), default=None)}
    result["same_historical_selections"] = {"bets": len(records), "stake": len(records),
                                           "pnl": sum(r["pnl"] for r in records),
                                           "roi_pct": 100 * statistics.mean(r["pnl"] for r in records) if records else None}
    for variant in ("incumbent", "challenger", "recorded_incumbent"):
        settled = [r for r in records if r["target"] is not None]
        selected = [r for r in records if r[variant]["ev"] >= config["minimum_ev"]]
        equal_fixture = defaultdict(list)
        for row in records:
            equal_fixture[row["fixture_id"]].append(row["pnl"] if row in selected else 0)
        result[variant] = {"scored_nonpush_contracts": len(settled),
                           "brier": statistics.mean(r[variant]["brier"] for r in settled) if settled else None,
                           "log_loss": statistics.mean(r[variant]["log_loss"] for r in settled) if settled else None,
                           "count_mae": statistics.mean(abs(r[variant]["mean"] - r["actual"]) for r in records) if records else None,
                           "fixed_ev_filter": {"bets": len(selected), "fixtures": len({r["fixture_id"] for r in selected}),
                                               "stake": len(selected), "pnl": sum(r["pnl"] for r in selected),
                                               "roi_pct": 100 * statistics.mean(r["pnl"] for r in selected) if selected else None,
                                               "pnl_per_available_contract": sum(r["pnl"] for r in selected) / len(records) if records else None,
                                               "equal_fixture_pnl_per_contract": statistics.mean(statistics.mean(v) for v in equal_fixture.values()) if equal_fixture else None}}
    result["paired_challenger_minus_incumbent"] = {
        metric: paired_interval(records, lambda r, m=metric: r["challenger"][m] - r["incumbent"][m] if r["target"] is not None else None, config)
        for metric in ("brier", "log_loss")}
    result["paired_challenger_minus_incumbent"]["fixed_filter_pnl_per_available_contract"] = paired_interval(
        records, lambda r: r["pnl"] * (int(r["challenger"]["ev"] >= config["minimum_ev"]) - int(r["incumbent"]["ev"] >= config["minimum_ev"])), config)
    return result


def evaluate(ledger, source, config):
    eligible, excluded = prepare_ledger(ledger, config)
    if not eligible:
        return [], excluded, {"source_quality": {}, "temporal_eligible_contracts": 0, "evaluation_start": None, "metrics": {}}
    histories, fixtures, identities, quality = load_source(source, eligible, config)
    evaluated = []
    physical_contracts = set()
    for row in eligible:
        tour, market = row["tour"], row["market"]
        player, opponent = (identities[tour].get(norm(row[k])) for k in ("player", "opponent"))
        reason = "unmatched_or_ambiguous_player" if not player or not opponent else None
        fixture = None
        if reason is None:
            fixture, reason = match_fixture(row, fixtures[tour].get(tuple(sorted((player, opponent))), []), player, opponent)
        if reason == "ok":
            cutoff, reason = temporal_cutoff(row, fixture["played"])
        if reason == "ok":
            physical_key = physical_contract_key(row, fixture["fixture_id"], player)
            if physical_key in physical_contracts:
                reason = "duplicate_physical_contract_after_source_join"
            else:
                physical_contracts.add(physical_key)
        support = {}
        if reason == "ok":
            multiplier, support, reason = rate_trend(histories[tour][player], histories[tour][opponent], fixture["surface"], cutoff, market, config)
        if reason == "ok":
            incumbent = prediction(float(row["projection_mean"]), row, config)
            if abs(incumbent["p_conditional"] - 1 / float(row["fair_odds"])) > config["probability_reconstruction_tolerance"]:
                reason = "frozen_probability_reconstruction_mismatch"
        if reason != "ok":
            excluded.append({"signal_id": row["signal_id"], "market": market, "reason": reason, "support": support})
            continue
        # Paired rate-effect scores use the identical frozen distribution kernel.
        # Also expose the rounded recorded entry comparator, never silently label
        # a reconstructed probability as the exact recorded entry probability.
        recorded_incumbent = dict(incumbent, p_conditional=1 / float(row["fair_odds"]))
        reconstruction_delta = incumbent["p_conditional"] - recorded_incumbent["p_conditional"]
        recorded_push = numeric(row.get("fair_p_push"))
        if recorded_push is not None and 0 <= recorded_push < 1:
            recorded_incumbent["p_push"] = recorded_push
        recorded_incumbent["p_win"] = recorded_incumbent["p_conditional"] * (1 - recorded_incumbent["p_push"])
        recorded_incumbent["ev"] = recorded_incumbent["p_win"] * float(row["selected_odds"]) - (1 - recorded_incumbent["p_push"])
        challenger = prediction(float(row["projection_mean"]) * multiplier, row, config)
        pnl, target = outcomes(count(row["actual"]), float(row["line"]), row["side"].upper(), float(row["selected_odds"]))
        record = {k: row.get(k, "") for k in ("signal_id", "player", "opponent", "tournament", "bookmaker", "event_id", "tour", "market", "line", "side", "selected_odds", "capture_ts", "logged_at_utc", "match_start_utc", *MODEL_IDENTITY_FIELDS)}
        record.update(fixture_id=fixture["fixture_id"], fixture_date=fixture["played"].isoformat(), cutoff=cutoff.isoformat(),
                      surface=fixture["surface"], multiplier=multiplier, support=support, actual=count(row["actual"]), pnl=pnl, target=target,
                      reconstruction_probability_delta=reconstruction_delta,
                      incumbent=dict(incumbent, **score_probability(incumbent["p_conditional"], target)),
                      recorded_incumbent=dict(recorded_incumbent, **score_probability(recorded_incumbent["p_conditional"], target)),
                      challenger=dict(challenger, **score_probability(challenger["p_conditional"], target)))
        evaluated.append(record)
    phases, boundary = assign_phases(evaluated, config["development_fixture_fraction"])
    for record in evaluated:
        record["phase"] = phases[record["fixture_id"]]
    report_metrics = {phase: {market: metrics([r for r in evaluated if r["market"] == market and (phase == "all" or r["phase"] == phase)], config)
                              for market in config["markets"]} for phase in ("development", "evaluation", "all")}
    # Combined policy PnL is additive; count likelihoods and errors stay separated by market.
    combined_policy = {phase: {k: v for k, v in metrics([r for r in evaluated if phase == "all" or r["phase"] == phase], config).items()
                              if k in {"contracts", "fixtures", "calendar_start", "calendar_end", "same_historical_selections"}}
                       for phase in ("development", "evaluation", "all")}
    return evaluated, excluded, {"source_quality": quality, "temporal_eligible_contracts": len(eligible),
                                "evaluation_start": boundary, "metrics": report_metrics, "paired_universe": combined_policy,
                                "reconstruction_probability_audit": {
                                    "mean_absolute_delta": statistics.mean(abs(r["reconstruction_probability_delta"]) for r in evaluated) if evaluated else None,
                                    "max_absolute_delta": max((abs(r["reconstruction_probability_delta"]) for r in evaluated), default=None),
                                    "scoring_arms": "incumbent = reconstructed frozen mean/kernel; challenger = same kernel with declared rate multiplier; recorded_incumbent = original rounded entry fair-odds probability"}}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_markdown(report, path):
    lines = ["# Fresh OnCourt rate-trend challenger v1", "", "**Retrospective exploratory analysis. No live formulas, gates, routing or ledgers changed. Automatic promotion is disabled.**", "",
             "The same historical quoted side, line and price are used for both forecasts. The ledger was selected by the incumbent; these are conditional results on its old selections. Source publication vintages are unknown, so this is not a point-in-time or prospective backtest.", "",
             "One fixed candidate preserves the incumbent mean's workload and venue assumptions, adjusting it by a 50% blend of recent-to-baseline rate trends, clipped to 0.8–1.2. History uses exact OnCourt match/round keys and dates strictly before the earliest capture day, registration day and fixture day. Same-day results are excluded. Priors and support thresholds are in the hashed config; no parameters are fitted. Paired scores use the same reconstructed distribution kernel in both arms; the separate recorded_incumbent arm uses original rounded entry probabilities.", "",
             f"Input ledger: {report['input_rows']} rows. Paired evaluation: {report['paired_contracts']} contracts, {report['paired_fixtures']} physical fixtures. Evaluation starts {report['evaluation_start']}; whole fixture dates stay together. This retrospective holdout was defined today, after historical outcomes existed.", "",
             "| Period / market | Contracts / fixtures | Incumbent Brier | Challenger Brier | Incumbent filter bets / ROI | Challenger filter bets / ROI |", "|---|---:|---:|---:|---:|---:|"]
    def formatted(value):
        return "n/a" if value is None else f"{value:.4f}"
    for phase in ("development", "evaluation", "all"):
        for market, values in report["metrics"].get(phase, {}).items():
            a, b = (values[v]["fixed_ev_filter"] for v in ("incumbent", "challenger"))
            lines.append(f"| {phase} / {market} | {values['contracts']} / {values['fixtures']} | {formatted(values['incumbent']['brier'])} | {formatted(values['challenger']['brier'])} | {a['bets']} / {formatted(a['roi_pct'])}% | {b['bets']} / {formatted(b['roi_pct'])}% |")
    lines += ["", "The fixed filter accepts expected return ≥3% with one unit per retained contract. Raw same-selection ROI is identical for both models. Strategy deltas include zero PnL for skipped contracts across the full common fixture universe. Paired intervals resample physical fixtures and weight fixtures equally; multiple contracts do not become independent matches. Count errors and probability scores are reported separately for aces and double faults.", "",
              "## Decision", "", report["promotion_decision"]["reason"], "", "Status: **" + report["promotion_decision"]["status"] + "**.", "",
              "## Raw identical-selection results", "", "```json", json.dumps(report["paired_universe"], indent=2), "```", "",
              "## Reconstructed versus recorded probability check", "", "```json", json.dumps(report.get("reconstruction_probability_audit", {}), indent=2), "```", "",
              "## Exclusions by market", "", "```json", json.dumps(report["exclusions_by_market"], indent=2), "```", "", "## Evaluation paired deltas (challenger minus incumbent)", ""]
    for market, values in report["metrics"].get("evaluation", {}).items():
        lines += [f"### {market}", "", "```json", json.dumps(values["paired_challenger_minus_incumbent"], indent=2), "```", ""]
    lines += ["## Frozen requirements for a subsequent prospective paper study", ""] + [f"- {item}" for item in report["next_prospective_requirements"]]
    lines += ["", "## Limits", ""] + [f"- {item}" for item in report["limitations"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", type=Path, default=ROOT / "data/tennis-props/shadow/aces-dfs-shadow-signals.csv")
    parser.add_argument("--oncourt-dir", type=Path, default=ROOT / "data/oncourt")
    parser.add_argument("--config", type=Path, default=ROOT / "config/tennis-props-fresh-data-challenger-v1.json")
    parser.add_argument("--output-prefix", type=Path, default=ROOT / "data/tennis-props/experiments/fresh-data-challenger-v1")
    args = parser.parse_args()
    # Hash immutable input snapshots before calculation; refuse changed input below.
    input_paths = [args.signals, args.config, Path(__file__).resolve(), ROOT / "scripts/tennis_props_model.py",
                   ROOT / "scripts/tennis-props-feature-audit.py", ROOT / "scripts/build-tennis-props-board.py",
                   ROOT / "scripts/tennis-props-shadow-tracker.py", args.oncourt_dir / "courts.csv"]
    input_paths += [args.oncourt_dir / f"{kind}_{tour}.csv" for tour in ("atp", "wta") for kind in ("players", "tours", "games", "stat")]
    hashes = {str(path): sha256(path) for path in input_paths}
    config = json.loads(args.config.read_text(encoding="utf-8"))
    ledger = list(rows(args.signals))
    evaluated, excluded, report = evaluate(ledger, args.oncourt_dir, config)
    if any(sha256(path) != hashes[str(path)] for path in input_paths):
        raise RuntimeError("Research input changed during run; outputs not published")
    report.update(experiment_id=config["experiment_id"], status="RETROSPECTIVE_EXPLORATORY_NO_PROMOTION", automatic_promotion=False,
                  generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), config=config, input_sha256=hashes,
                  input_rows=len(ledger), paired_contracts=len(evaluated), paired_fixtures=len({r["fixture_id"] for r in evaluated}),
                  included_by_market=dict(Counter(r["market"] for r in evaluated)),
                  included_tournaments=dict(Counter(r["tournament"] for r in evaluated)),
                  exclusions_by_market={market: dict(Counter(r["reason"] for r in excluded if r["market"] == market)) for market in config["markets"]},
                  limitations=["Incumbent-selected sample: no full board or unselected offers; ROI is conditional on historical selected contracts.",
                               "Historical source publication vintages unavailable; corrected/backfilled statistics may not have been observable at the original price time.",
                               "Candidate and chronological split specified retrospectively today, after outcomes existed; no untouched prospective validation or guarantee of improved ROI.",
                               "Frozen workload/exposure snapshots absent: candidate retains incumbent workload and venue assumptions and changes relative rate trends only.",
                               "Small, tournament-concentrated sample; fixture bootstrap intervals do not correct selection bias, source-vintage uncertainty or tournament dependence.",
                               "Source matching excludes ambiguous players/fixtures, conflicting counts, post-start registrations and insufficient rate support; exclusions can change sample composition.",
                               "Only main-tour source matches with exact dates and rounds; indoor/acrylic hard courts grouped with hard, as in the existing feature audit.",
                               "Primary paired arms use the same reconstructed frozen distribution kernel; the separate recorded_incumbent arm uses original rounded entry fair odds. Reconstruction discrepancies are reported; no dispersion fit or side/line optimization.",
                               "Research retains one earliest entry per exact physical fixture/player/market/book/line/side, collapsing provider aliases or model labels without changing live model-specific ledger identity."])
    report["promotion_decision"] = {
        "status": "BLOCKED_PENDING_PROSPECTIVE_EVIDENCE",
        "reason": "This retrospective, incumbent-selected sample cannot establish a future ROI improvement. A new prospective study with archived input vintages is required before any promotion; the numerical results below are exploratory only.",
        "live_formula_changes": False}
    report["next_prospective_requirements"] = [
        "Freeze this candidate/config hash, dispersion, same-side 3% EV rule and one-unit sizing before collection; no parameter search or outcome-driven changes during the study.",
        "Archive full supported bookmaker offer snapshots, incumbent exposure/probabilities, candidate features and source content hashes with capture/publication timestamps before kickoff. Log all eligible offers including both-arm skips; do not reuse only incumbent-selected bets.",
        "Use exact physical fixture/round identity and earliest immutable contract registration. Retain distinct bookmaker/line/side contracts, pair both strategies over the same opportunity universe, and cluster all contracts from a fixture.",
        "Run paper-only for at least eight calendar weeks, 200 independent fixtures per market and four tournaments. These are operational review floors, not a power calculation or guarantee; insufficient precision requires more evidence without changing the candidate.",
        "At the declared review point report aces and DFs separately, stratify ATP/WTA, retain zero PnL for skips, and bootstrap physical fixtures. Any lane without enough data remains blocked.",
        "A promotion review requires positive paired strategy PnL improvement and positive absolute strategy ROI with lower 95% bounds above zero, and improved Brier score with its paired upper 95% bound below zero without worse log loss. These conservative requirements are for the next study and were not used to select this retrospective candidate.",
        "Keep automatic promotion disabled. Validate freshness, source coverage, settlement integrity and calibration before a separate human review changes live routing."]
    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    prefix.with_name(prefix.name + "-observations.json").write_text(json.dumps({"paired": evaluated, "excluded": excluded}, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, prefix.with_suffix(".md"))
    print(json.dumps({k: report[k] for k in ("status", "paired_contracts", "paired_fixtures", "evaluation_start", "exclusions_by_market", "metrics")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
