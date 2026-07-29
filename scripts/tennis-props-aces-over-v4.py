#!/usr/bin/env python3
"""Register and evaluate the market-anchored ATP ace-over v4 challenger.

The lane is prospective and append-only. Before 200 settled registered
observations, v4 is deliberately identical to frozen v3 and labelled PRE_FIT.
No row from PRE_FIT is eligible for a betting or promotion claim.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
PROPS_DIR = ROOT / "data" / "tennis-props"
DEFAULT_LEDGER = PROPS_DIR / "shadow" / "aces-over-v4-observations.csv"
DEFAULT_REPORT = PROPS_DIR / "backtest" / "aces-over-v4-weekly-report.txt"
DEFAULT_JSON = PROPS_DIR / "backtest" / "aces-over-v4-weekly-report.json"
DEFAULT_GATE = PROPS_DIR / "backtest" / "aces-dfs-v3-all-tour-gate.json"
DEFAULT_SACKMANN = ROOT / "data" / "sackmann"
DEFAULT_ONCOURT = ROOT / "data" / "oncourt"
MIN_PREFIT_SETTLED = 200
SIGNAL_EDGE_PCT = 8.0
# This is the fixed ATP ace-ladder shape used in the pre-registration audit.
# It is not v4's fitted outcome dispersion and must remain frozen for market
# mean/CLV comparability across the PRE_FIT collection period.
LADDER_REFERENCE_ALPHA = 0.35

sys.path.insert(0, str(SCRIPTS_DIR))
from tennis_props_ladder import canonical_quote, fit_market_ladder, over_probability  # noqa: E402


def load_settlement_module():
    path = SCRIPTS_DIR / "tennis-props-settle-shadow.py"
    spec = importlib.util.spec_from_file_location("tennis_props_v4_settlement", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import settlement helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SETTLE = load_settlement_module()

FROZEN_FIELDS = [
    "observation_id",
    "registered_at_utc",
    "date",
    "tour",
    "tournament",
    "surface",
    "player",
    "opponent",
    "market",
    "event_id",
    "match_start_utc",
    "bookmaker",
    "source_file",
    "capture_ts",
    "line",
    "selected_odds",
    "mu_v3",
    "mu_mkt",
    "mu_v4",
    "w_applied",
    "alpha_ladder",
    "alpha_v3",
    "alpha_v4",
    "p_over_v3",
    "p_push_v3",
    "p_over_v4",
    "p_push_v4",
    "p_over_market",
    "edge_v3_pct",
    "edge_v4_pct",
    "ladder_overround",
    "ladder_shape_rmse",
    "ladder_points",
    "ladder_dropped_ceiling",
    "phase",
    "fit_training_n",
    "fit_cutoff",
    "model_sha256",
]

FIELDNAMES = FROZEN_FIELDS + [
    "frozen_sha256",
    "closing_odds",
    "closing_ts_utc",
    "closing_snapshot_count",
    "price_clv_pct",
    "closing_mu_mkt",
    "closing_p_over_market",
    "probability_clv_pp",
    "settlement_status",
    "actual",
    "outcome_over",
    "result",
    "pnl",
    "v3_brier",
    "v4_brier",
    "market_brier",
    "v3_logloss",
    "v4_logloss",
    "market_logloss",
    "v3_count_error",
    "v4_count_error",
    "v3_count_bias",
    "v4_count_bias",
    "v4_signal",
    "settled_at_utc",
    "settlement_note",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def number(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def model_hash(gate: dict[str, Any]) -> str:
    deployment = gate.get("deployment_safe_aces")
    atp = deployment.get("ATP") if isinstance(deployment, dict) else None
    relative = str(atp.get("model_path") or "") if isinstance(atp, dict) else ""
    model_path = ROOT / relative
    if not model_path.exists():
        raise FileNotFoundError(f"Frozen v3 model missing: {model_path}")
    return hashlib.sha256(model_path.read_bytes()).hexdigest()


def candidate_alpha(gate: dict[str, Any]) -> float:
    deployment = gate.get("deployment_safe_aces")
    atp = deployment.get("ATP") if isinstance(deployment, dict) else None
    alpha = number(atp.get("candidate_alpha")) if isinstance(atp, dict) else None
    if alpha is None or alpha <= 0:
        raise ValueError("Missing positive ATP v3 candidate_alpha")
    return alpha


def frozen_digest(row: dict[str, str]) -> str:
    payload = "\x1f".join(str(row.get(field) or "") for field in FROZEN_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_integrity(rows: list[dict[str, str]]) -> None:
    ids: set[str] = set()
    semantic_keys: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows, start=2):
        row_id = str(row.get("observation_id") or "")
        if not row_id or row_id in ids:
            raise RuntimeError(f"v4 ledger duplicate/missing observation_id at CSV row {index}")
        ids.add(row_id)
        semantic_key = (
            str(row.get("event_id") or "").strip()
            or "|".join(
                [
                    str(row.get("date") or ""),
                    str(row.get("tour") or "").upper(),
                    *SETTLE.pair_key(row.get("player"), row.get("opponent")),
                ]
            ),
            SETTLE.norm_text(row.get("player")),
            str(row.get("market") or "aces").strip().lower(),
        )
        if semantic_key in semantic_keys:
            raise RuntimeError(
                "v4 ledger duplicate event/player/market at CSV row "
                f"{index}: {'|'.join(semantic_key)}"
            )
        semantic_keys.add(semantic_key)
        expected = frozen_digest(row)
        if str(row.get("frozen_sha256") or "") != expected:
            raise RuntimeError(f"v4 frozen-field integrity failure: {row_id}")


def observation_id(row: dict[str, str]) -> str:
    event_id = str(row.get("event_id") or "").strip()
    identity = event_id or "|".join(
        [
            str(row.get("date") or ""),
            str(row.get("tour") or "").upper(),
            *SETTLE.pair_key(row.get("player"), row.get("opponent")),
        ]
    )
    return f"{identity}|{SETTLE.norm_text(row.get('player'))}|aces"


def first_day_of_month(value: str) -> date:
    parsed = date.fromisoformat(value)
    return parsed.replace(day=1)


def nb_log_pmf(actual: int, mean: float, alpha: float) -> float:
    if actual < 0 or mean <= 0 or alpha <= 0:
        return -math.inf
    shape = 1.0 / alpha
    probability = shape / (shape + mean)
    return (
        math.lgamma(actual + shape)
        - math.lgamma(shape)
        - math.lgamma(actual + 1)
        + shape * math.log(probability)
        + actual * math.log1p(-probability)
    )


def blend_mean(mu_v3: float, mu_mkt: float, weight: float) -> float:
    return math.exp((1.0 - weight) * math.log(mu_v3) + weight * math.log(mu_mkt))


def eligible_training_rows(rows: list[dict[str, str]], cutoff: date) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        actual = number(row.get("actual"))
        mu_v3 = number(row.get("mu_v3"))
        mu_mkt = number(row.get("mu_mkt"))
        try:
            row_date = date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            continue
        if (
            row_date < cutoff
            and row.get("settlement_status") == "settled"
            and actual is not None
            and mu_v3 is not None
            and mu_mkt is not None
        ):
            output.append(row)
    return output


def fit_parameters(rows: list[dict[str, str]]) -> tuple[float, float]:
    def loss(weight: float, alpha: float) -> float:
        values = []
        for row in rows:
            mean = blend_mean(float(row["mu_v3"]), float(row["mu_mkt"]), weight)
            values.append(-nb_log_pmf(int(float(row["actual"])), mean, alpha))
        return sum(values) / len(values)

    coarse = [
        (loss(weight / 20.0, alpha / 100.0), weight / 20.0, alpha / 100.0)
        for weight in range(21)
        for alpha in range(5, 51, 2)
    ]
    _score, best_weight, best_alpha = min(coarse)
    weights = {
        max(0.0, min(1.0, best_weight + offset / 100.0))
        for offset in range(-6, 7)
    }
    alphas = {
        max(0.02, min(0.8, best_alpha + offset / 1000.0))
        for offset in range(-12, 13, 2)
    }
    _score, weight, alpha = min(
        (loss(candidate_weight, candidate_alpha), candidate_weight, candidate_alpha)
        for candidate_weight in weights
        for candidate_alpha in alphas
    )
    return weight, alpha


def comparison_paths(explicit: list[Path] | None) -> list[Path]:
    if explicit:
        return [path for path in explicit if path.exists()]
    return sorted(PROPS_DIR.glob("comparison-v3-aces-????-??-??.csv"))


def ladder_candidates(
    paths: list[Path],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    grouped: dict[tuple[str, str], list[tuple[dict[str, str], Path]]] = defaultdict(list)
    for source in paths:
        for row in read_csv(source):
            if not (
                str(row.get("tour") or "").upper() == "ATP"
                and str(row.get("surface") or "") in {"Hard", "Clay"}
                and str(row.get("scope") or "") == "player"
                and str(row.get("market") or "").lower() == "aces"
                and str(row.get("matched_board") or "").lower() == "yes"
                and str(row.get("price_pair_status") or "").lower() == "over_only"
            ):
                continue
            capture = str(row.get("capture_ts") or "")
            if capture:
                grouped[(observation_id(row), capture)].append((row, source))

    candidates: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    for (_row_id, capture), items in grouped.items():
        rows = [item[0] for item in items]
        points = [
            (line, odds)
            for row in rows
            if (line := number(row.get("line"))) is not None
            and (odds := number(row.get("over_odds"))) is not None
        ]
        fit = fit_market_ladder(points, alpha=LADDER_REFERENCE_ALPHA)
        if not fit.accepted:
            rejects[fit.reject_reason or "UNKNOWN"] += 1
            continue
        quote = canonical_quote(points)
        if quote is None or fit.mu_mkt is None:
            rejects["NO_CANONICAL_QUOTE"] += 1
            continue
        line, odds = quote
        quote_rows = [
            (row, source)
            for row, source in items
            if number(row.get("line")) == line and number(row.get("over_odds")) == odds
        ]
        if not quote_rows:
            rejects["CANONICAL_ROW_MISSING"] += 1
            continue
        row, source = quote_rows[0]
        candidates.append(
            {
                "row": row,
                "source": source,
                "fit": fit,
                "line": line,
                "odds": odds,
                "capture": capture,
            }
        )
    candidates.sort(key=lambda item: (item["capture"], observation_id(item["row"])))
    return candidates, rejects


def line_probabilities(line: float, mean: float, alpha: float) -> tuple[float, float]:
    p_over = over_probability(line, mean, alpha)
    if abs(line - round(line)) > 1e-9:
        return p_over, 0.0
    # The current ladder is half-integer, but preserve correct push arithmetic.
    from tennis_props_model import count_line_probabilities

    over, _under, push = count_line_probabilities(
        line,
        mean,
        distribution="negative_binomial",
        alpha=alpha,
        tour="ATP",
        market="aces",
    )
    return over, push


def build_registration(
    candidate: dict[str, Any],
    *,
    ledger: list[dict[str, str]],
    gate: dict[str, Any],
    sha256: str,
    now: datetime,
) -> dict[str, str]:
    row = candidate["row"]
    line = float(candidate["line"])
    odds = float(candidate["odds"])
    mu_v3 = number(row.get("projection_mean"))
    mu_mkt = candidate["fit"].mu_mkt
    alpha_v3 = candidate_alpha(gate)
    if mu_v3 is None or mu_v3 <= 0 or mu_mkt is None or mu_mkt <= 0:
        raise ValueError("Candidate is missing positive v3/market means")

    cutoff = first_day_of_month(str(row.get("date") or ""))
    training = eligible_training_rows(ledger, cutoff)
    if len(training) >= MIN_PREFIT_SETTLED:
        weight, alpha_v4 = fit_parameters(training)
        phase = "WALK_FORWARD"
        fit_cutoff = cutoff.isoformat()
    else:
        weight, alpha_v4 = 0.0, alpha_v3
        phase = "PRE_FIT"
        fit_cutoff = ""
    mu_v4 = blend_mean(mu_v3, mu_mkt, weight)
    p_v3, push_v3 = line_probabilities(line, mu_v3, alpha_v3)
    p_v4, push_v4 = line_probabilities(line, mu_v4, alpha_v4)
    p_market, _market_push = line_probabilities(line, mu_mkt, alpha_v3)
    edge_v3 = (p_v3 * odds + push_v3 - 1.0) * 100.0
    edge_v4 = (p_v4 * odds + push_v4 - 1.0) * 100.0
    relative_source = candidate["source"]
    if relative_source.is_relative_to(ROOT):
        relative_source = relative_source.relative_to(ROOT)
    registered = {
        "observation_id": observation_id(row),
        "registered_at_utc": now.isoformat(timespec="seconds"),
        "date": str(row.get("date") or ""),
        "tour": "ATP",
        "tournament": str(row.get("tournament") or ""),
        "surface": str(row.get("surface") or ""),
        "player": str(row.get("player") or ""),
        "opponent": str(row.get("opponent") or ""),
        "market": "aces",
        "event_id": str(row.get("event_id") or ""),
        "match_start_utc": str(row.get("match_start_utc") or ""),
        "bookmaker": str(row.get("bookmaker") or "Bet365"),
        "source_file": str(relative_source),
        "capture_ts": str(candidate["capture"]),
        "line": fmt(line, 3),
        "selected_odds": fmt(odds, 3),
        "mu_v3": fmt(mu_v3),
        "mu_mkt": fmt(mu_mkt),
        "mu_v4": fmt(mu_v4),
        "w_applied": fmt(weight),
        "alpha_ladder": fmt(LADDER_REFERENCE_ALPHA),
        "alpha_v3": fmt(alpha_v3),
        "alpha_v4": fmt(alpha_v4),
        "p_over_v3": fmt(p_v3),
        "p_push_v3": fmt(push_v3),
        "p_over_v4": fmt(p_v4),
        "p_push_v4": fmt(push_v4),
        "p_over_market": fmt(p_market),
        "edge_v3_pct": fmt(edge_v3, 3),
        "edge_v4_pct": fmt(edge_v4, 3),
        "ladder_overround": fmt(candidate["fit"].overround),
        "ladder_shape_rmse": fmt(candidate["fit"].shape_rmse),
        "ladder_points": str(candidate["fit"].n_points),
        "ladder_dropped_ceiling": str(candidate["fit"].dropped_ceiling),
        "phase": phase,
        "fit_training_n": str(len(training)),
        "fit_cutoff": fit_cutoff,
        "model_sha256": sha256,
        "settlement_status": "pending",
        "v4_signal": "true" if phase == "WALK_FORWARD" and edge_v4 >= SIGNAL_EDGE_PCT else "false",
    }
    registered["frozen_sha256"] = frozen_digest(registered)
    return registered


def history_rows(paths: list[Path]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for path in paths:
        output.extend(read_csv(path))
    return output


def update_closing(
    row: dict[str, str],
    history: list[dict[str, str]],
) -> bool:
    start = SETTLE.parse_utc_datetime(row.get("match_start_utc"))
    registered = SETTLE.parse_utc_datetime(row.get("capture_ts"))
    if start is None or registered is None:
        return False
    identity = SETTLE.history_key(row)
    captures: dict[datetime, list[dict[str, str]]] = defaultdict(list)
    for candidate in history:
        captured = SETTLE.parse_utc_datetime(candidate.get("capture_ts"))
        if (
            SETTLE.history_key(candidate) == identity
            and captured is not None
            and registered < captured <= start
        ):
            captures[captured].append(candidate)
    if not captures:
        return False

    alpha = number(row.get("alpha_ladder")) or LADDER_REFERENCE_ALPHA
    accepted: list[tuple[datetime, float, float, float, int]] = []
    event_id = str(row.get("event_id") or "")
    player = SETTLE.norm_text(row.get("player"))
    for captured in sorted(captures):
        ladder_rows = [
            candidate
            for candidate in history
            if str(candidate.get("event_id") or "") == event_id
            and SETTLE.norm_text(candidate.get("player")) == player
            and SETTLE.norm_text(candidate.get("market")) == "aces"
            and SETTLE.parse_utc_datetime(candidate.get("capture_ts")) == captured
        ]
        points = [
            (line, odds)
            for candidate in ladder_rows
            if (line := number(candidate.get("line"))) is not None
            and (odds := number(candidate.get("over_odds"))) is not None
        ]
        fit = fit_market_ladder(points, alpha=alpha)
        selected = [
            candidate
            for candidate in ladder_rows
            if number(candidate.get("line")) == number(row.get("line"))
            and (number(candidate.get("over_odds")) or 0) > 1.0
        ]
        if fit.accepted and fit.mu_mkt is not None and selected:
            odds = number(selected[-1].get("over_odds"))
            if odds is not None:
                accepted.append((captured, odds, fit.mu_mkt, fit.shape_rmse or 0.0, fit.n_points))
    if not accepted:
        return False
    captured, odds, mu_close, _rmse, _points = accepted[-1]
    selected_odds = number(row.get("selected_odds"))
    line = number(row.get("line"))
    open_market_p = number(row.get("p_over_market"))
    if selected_odds is None or line is None or open_market_p is None:
        return False
    close_market_p, _push = line_probabilities(line, mu_close, alpha)
    row["closing_odds"] = fmt(odds, 3)
    row["closing_ts_utc"] = captured.isoformat(timespec="seconds")
    row["closing_snapshot_count"] = str(len(accepted))
    row["price_clv_pct"] = fmt((selected_odds / odds - 1.0) * 100.0, 3)
    row["closing_mu_mkt"] = fmt(mu_close)
    row["closing_p_over_market"] = fmt(close_market_p)
    row["probability_clv_pp"] = fmt((close_market_p - open_market_p) * 100.0, 3)
    return True


def binary_metrics(probability: float, outcome: int) -> tuple[float, float]:
    clipped = max(1e-9, min(1.0 - 1e-9, probability))
    return (clipped - outcome) ** 2, -(
        outcome * math.log(clipped) + (1 - outcome) * math.log(1.0 - clipped)
    )


def score_row(row: dict[str, str]) -> None:
    actual = number(row.get("actual"))
    line = number(row.get("line"))
    if actual is None or line is None:
        return
    mu_v3 = number(row.get("mu_v3"))
    mu_v4 = number(row.get("mu_v4"))
    probabilities = {
        "v3": number(row.get("p_over_v3")),
        "v4": number(row.get("p_over_v4")),
        "market": number(row.get("p_over_market")),
    }
    if mu_v3 is not None:
        row["v3_count_error"] = fmt(abs(actual - mu_v3), 3)
        row["v3_count_bias"] = fmt(mu_v3 - actual, 3)
    if mu_v4 is not None:
        row["v4_count_error"] = fmt(abs(actual - mu_v4), 3)
        row["v4_count_bias"] = fmt(mu_v4 - actual, 3)
    if actual == line:
        row["outcome_over"] = "push"
        row["result"] = "push" if row.get("v4_signal") == "true" else ""
        row["pnl"] = "0.000" if row.get("v4_signal") == "true" else ""
        return
    outcome = int(actual > line)
    row["outcome_over"] = str(outcome)
    for prefix, probability in probabilities.items():
        if probability is None:
            continue
        brier, logloss = binary_metrics(probability, outcome)
        row[f"{prefix}_brier"] = fmt(brier)
        row[f"{prefix}_logloss"] = fmt(logloss)
    if row.get("v4_signal") == "true":
        if outcome:
            row["result"] = "won"
            row["pnl"] = fmt((number(row.get("selected_odds")) or 1.0) - 1.0, 3)
        else:
            row["result"] = "lost"
            row["pnl"] = "-1.000"


def settle_rows(
    rows: list[dict[str, str]],
    *,
    sackmann_dir: Path,
    oncourt_dir: Path,
    now_dt: datetime | None = None,
) -> int:
    now_dt = now_dt or datetime.now(UTC)
    settlement_fields = [
        "actual",
        "outcome_over",
        "result",
        "pnl",
        "v3_brier",
        "v4_brier",
        "market_brier",
        "v3_logloss",
        "v4_logloss",
        "market_logloss",
        "v3_count_error",
        "v4_count_error",
        "v3_count_bias",
        "v4_count_bias",
        "settled_at_utc",
    ]
    for row in rows:
        match_start = SETTLE.parse_utc_datetime(row.get("match_start_utc"))
        if (
            match_start is not None
            and match_start > now_dt
            and row.get("settlement_status") in {"settled", "void"}
        ):
            row["settlement_status"] = "pending"
            row["settlement_note"] = "future_settlement_reset"
            for field in settlement_fields:
                row[field] = ""
    pending = [
        row for row in rows
        if (row.get("settlement_status") or "pending") in {"", "pending"}
    ]
    oncourt_index = SETTLE.load_oncourt_index(oncourt_dir, pending)
    sackmann_index = SETTLE.load_sackmann_index(sackmann_dir)
    settled_now = 0
    now = now_dt.isoformat(timespec="seconds")
    for row in pending:
        match_start = SETTLE.parse_utc_datetime(row.get("match_start_utc"))
        if match_start is not None and match_start > now_dt:
            row["settlement_note"] = "match_not_started"
            continue
        year = SETTLE.parse_year(row.get("date"))
        key = ("ATP", year, SETTLE.pair_key(row.get("player"), row.get("opponent")))
        candidates = oncourt_index.get(key, []) or sackmann_index.get(key, [])
        candidate = SETTLE.choose_candidate(row, candidates)
        if candidate is None:
            row["settlement_note"] = "match_ambiguous" if candidates else "match_not_found"
            continue
        if SETTLE.is_void_score(candidate.get("score")):
            row["settlement_status"] = "void"
            row["result"] = "void" if row.get("v4_signal") == "true" else ""
            row["pnl"] = "0.000" if row.get("v4_signal") == "true" else ""
            row["settled_at_utc"] = now
            row["settlement_note"] = f"void_score:{candidate.get('score', '')}"
            settled_now += 1
            continue
        actual, note = SETTLE.market_count(candidate, SETTLE.norm_text(row.get("player")), "aces")
        if actual is None:
            row["settlement_note"] = note
            continue
        row["settlement_status"] = "settled"
        row["actual"] = str(actual)
        row["settled_at_utc"] = now
        source = candidate.get("_settlement_source") or "sackmann"
        row["settlement_note"] = f"{source}:{candidate.get('tourney_name', '')}:{candidate.get('score', '')}"
        score_row(row)
        settled_now += 1
    for row in rows:
        if row.get("settlement_status") == "settled":
            score_row(row)
    return settled_now


def mean_field(rows: list[dict[str, str]], field: str) -> float | None:
    values = [number(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def report_payload(
    rows: list[dict[str, str]],
    *,
    accepted_ladders: int,
    rejected: Counter[str],
    generated_at: datetime,
) -> dict[str, Any]:
    settled = [row for row in rows if row.get("settlement_status") == "settled"]
    pushed = [row for row in settled if row.get("outcome_over") == "push"]
    scored = [row for row in settled if row.get("outcome_over") in {"0", "1"}]
    postfit = [row for row in scored if row.get("phase") == "WALK_FORWARD"]
    signals = [row for row in settled if row.get("v4_signal") == "true"]
    pnl = sum(number(row.get("pnl")) or 0.0 for row in signals)
    clv = [
        value
        for row in rows
        if (value := number(row.get("price_clv_pct"))) is not None
    ]
    total_ladders = accepted_ladders + sum(rejected.values())
    overrounds = sorted(
        value
        for row in rows
        if (value := number(row.get("ladder_overround"))) is not None
    )
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "status": "PRE_FIT" if len(settled) < MIN_PREFIT_SETTLED else "WALK_FORWARD_EVIDENCE",
        "scope": "ATP player aces, Hard/Clay, shadow only",
        "minimum_prefit_settled": MIN_PREFIT_SETTLED,
        "rows_registered": len(rows),
        "rows_settled": len(settled),
        "rows_scored": len(scored),
        "rows_pushed": len(pushed),
        "rows_void": sum(row.get("settlement_status") == "void" for row in rows),
        "rows_pending": sum((row.get("settlement_status") or "pending") == "pending" for row in rows),
        "promotion_sample": len(postfit),
        "brier_v3": mean_field(postfit, "v3_brier"),
        "brier_v4": mean_field(postfit, "v4_brier"),
        "brier_market": mean_field(postfit, "market_brier"),
        "count_mae_v3": mean_field(postfit, "v3_count_error"),
        "count_mae_v4": mean_field(postfit, "v4_count_error"),
        "count_bias_v3": mean_field(postfit, "v3_count_bias"),
        "count_bias_v4": mean_field(postfit, "v4_count_bias"),
        "signals_settled": len(signals),
        "pnl_units": round(pnl, 4),
        "roi_pct": round(pnl / len(signals) * 100.0, 4) if signals else None,
        "clv_coverage": len(clv),
        "clv_null_count": len(rows) - len(clv),
        "clv_mean_pct": sum(clv) / len(clv) if clv else None,
        "clv_positive_pct": sum(value > 0 for value in clv) / len(clv) * 100.0 if clv else None,
        "ladder_groups_seen": total_ladders,
        "ladder_groups_accepted": accepted_ladders,
        "ladder_accept_rate_pct": accepted_ladders / total_ladders * 100.0 if total_ladders else None,
        "ladder_reject_reasons": dict(sorted(rejected.items())),
        "overround_median": overrounds[len(overrounds) // 2] if overrounds else None,
        "integrity": {
            "player_key_collisions": len(rows) - len({row.get("observation_id") for row in rows}),
            "open_as_close_rows": sum(
                bool(row.get("closing_ts_utc"))
                and row.get("closing_ts_utc") == row.get("capture_ts")
                for row in rows
            ),
            "frozen_hash_failures": 0,
        },
    }


def write_report(text_path: Path, json_path: Path, payload: dict[str, Any]) -> None:
    def metric(value: object, digits: int = 4) -> str:
        parsed = number(value)
        return "-" if parsed is None else f"{parsed:.{digits}f}"

    lines = [
        "ATP Aces Over v4 Registered Challenger",
        f"Generated UTC: {payload['generated_at']}",
        f"Status: {payload['status']}",
        f"Scope: {payload['scope']}",
        "Routing: shadow only; v3 production/recommendation logic is unchanged.",
        "",
        (
            f"Registered {payload['rows_registered']} | settled {payload['rows_settled']} | "
            f"scored {payload['rows_scored']} | pushed {payload['rows_pushed']} | "
            f"pending {payload['rows_pending']} | void {payload['rows_void']}"
        ),
        (
            f"Pre-fit progress: {payload['rows_settled']}/{payload['minimum_prefit_settled']} settled. "
            "PRE_FIT rows are excluded from promotion."
        ),
        (
            f"Walk-forward promotion sample: {payload['promotion_sample']} | "
            f"Brier v3 {metric(payload['brier_v3'])} vs v4 {metric(payload['brier_v4'])} "
            f"vs market {metric(payload['brier_market'])}"
        ),
        (
            f"Signals after fit: {payload['signals_settled']} | P/L {payload['pnl_units']:+.2f}u | "
            f"ROI {metric(payload['roi_pct'], 2)}%"
        ),
        (
            f"CLV coverage {payload['clv_coverage']}/{payload['rows_registered']} | "
            f"mean {metric(payload['clv_mean_pct'], 2)}% | positive {metric(payload['clv_positive_pct'], 1)}%"
        ),
        (
            f"Ladder acceptance {metric(payload['ladder_accept_rate_pct'], 1)}% "
            f"({payload['ladder_groups_accepted']}/{payload['ladder_groups_seen']}) | "
            f"rejects {payload['ladder_reject_reasons']}"
        ),
        f"Integrity: {payload['integrity']}",
        "",
        "Promotion remains blocked until the registered walk-forward sample reaches 600 rows,",
        "150 events, and the Brier, calibration, surface, CLV and integrity gates all pass.",
    ]
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register and score ATP ace-over v4 shadow evidence.")
    parser.add_argument("--comparison", type=Path, action="append")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--sackmann-dir", type=Path, default=DEFAULT_SACKMANN)
    parser.add_argument("--oncourt-dir", type=Path, default=DEFAULT_ONCOURT)
    parser.add_argument("--history-glob", default=str(PROPS_DIR / "inbox" / "bet365-lines-history-*.csv"))
    parser.add_argument("--now", help="UTC ISO timestamp override for tests")
    args = parser.parse_args()

    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(UTC)
        if args.now
        else datetime.now(UTC)
    )
    gate = json.loads(args.gate.read_text(encoding="utf-8-sig"))
    alpha_v3 = candidate_alpha(gate)
    sha256 = model_hash(gate)
    rows = read_csv(args.ledger)
    assert_integrity(rows)

    history_pattern = Path(args.history_glob)
    history = history_rows(sorted(history_pattern.parent.glob(history_pattern.name)))
    for row in rows:
        update_closing(row, history)
    settle_rows(rows, sackmann_dir=args.sackmann_dir, oncourt_dir=args.oncourt_dir, now_dt=now)

    candidates, rejected = ladder_candidates(comparison_paths(args.comparison))
    seen = {row["observation_id"] for row in rows}
    added = 0
    for candidate in candidates:
        candidate_row = candidate["row"]
        row_id = observation_id(candidate_row)
        start = SETTLE.parse_utc_datetime(candidate_row.get("match_start_utc"))
        capture = SETTLE.parse_utc_datetime(candidate.get("capture"))
        if row_id in seen or start is None or capture is None or start <= now:
            continue
        registered = build_registration(candidate, ledger=rows, gate=gate, sha256=sha256, now=now)
        rows.append(registered)
        seen.add(row_id)
        added += 1

    for row in rows:
        update_closing(row, history)
    settled_now = settle_rows(
        rows,
        sackmann_dir=args.sackmann_dir,
        oncourt_dir=args.oncourt_dir,
        now_dt=now,
    )
    assert_integrity(rows)
    rows.sort(key=lambda row: (row.get("date", ""), row.get("observation_id", "")))
    write_csv(args.ledger, rows)
    payload = report_payload(
        rows,
        accepted_ladders=len(candidates),
        rejected=rejected,
        generated_at=now,
    )
    write_report(args.report, args.json, payload)
    print(
        f"Aces-over v4: added={added} settled_now={settled_now} total={len(rows)} "
        f"status={payload['status']} -> {args.ledger}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
