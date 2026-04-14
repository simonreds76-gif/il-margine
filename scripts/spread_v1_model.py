from __future__ import annotations

import math
from typing import Any


FEATURE_NAMES = [
    "surface_clay",
    "line_abs_centered",
    "line_bucket_3_5",
    "line_bucket_4_5",
    "line_bucket_5_5_plus",
    "p1_match_prob_centered",
    "market_logit_delta",
    "overround",
]

MODEL_TYPE = "spread_v1_additive_logit_offset_v1"
DEFAULT_MAX_ABS_LOGIT_ADJUSTMENT = 1.25


def clamp_prob(value: float, lo: float = 1e-6, hi: float = 1.0 - 1e-6) -> float:
    return max(lo, min(hi, float(value)))


def logit(prob: float) -> float:
    q = clamp_prob(prob)
    return math.log(q / (1.0 - q))


def sigmoid(z: float) -> float:
    if z >= 0.0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def devig_two_way(odds1: float, odds2: float) -> tuple[float, float] | None:
    if odds1 is None or odds2 is None:
        return None
    if odds1 <= 1.0 or odds2 <= 1.0:
        return None
    inv1 = 1.0 / float(odds1)
    inv2 = 1.0 / float(odds2)
    total = inv1 + inv2
    if total <= 0:
        return None
    return inv1 / total, inv2 / total


def feature_vector(
    *,
    base_prob: float,
    surface: str,
    line: float,
    p1_match_prob: float,
    odds1: float,
    odds2: float,
) -> dict[str, float] | None:
    devig = devig_two_way(odds1, odds2)
    if devig is None:
        return None
    market_prob_p1, _ = devig
    abs_line = abs(float(line))
    rounded_line = round(abs_line, 1)
    inv1 = 1.0 / float(odds1)
    inv2 = 1.0 / float(odds2)

    return {
        "surface_clay": 1.0 if str(surface or "").strip().lower() == "clay" else 0.0,
        "line_abs_centered": abs_line - 4.5,
        "line_bucket_3_5": 1.0 if rounded_line == 3.5 else 0.0,
        "line_bucket_4_5": 1.0 if rounded_line == 4.5 else 0.0,
        "line_bucket_5_5_plus": 1.0 if rounded_line >= 5.5 else 0.0,
        "p1_match_prob_centered": clamp_prob(p1_match_prob) - 0.5,
        "market_logit_delta": logit(market_prob_p1) - logit(base_prob),
        "overround": (inv1 + inv2) - 1.0,
    }


def model_status(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"valid": False, "reason": "missing"}
    correction = payload.get("correction_model")
    if not isinstance(correction, dict):
        return {"valid": False, "reason": "missing"}
    valid = bool(correction.get("valid"))
    reason = str(correction.get("reason") or ("ok" if valid else "invalid")).strip()
    usable_scope = correction.get("usable_scope") if isinstance(correction.get("usable_scope"), dict) else {}
    return {
        "valid": valid,
        "reason": reason or ("ok" if valid else "invalid"),
        "fit_timestamp": correction.get("fit_timestamp") or "",
        "usable_scope": usable_scope,
        "model_type": correction.get("model_type") or "",
    }


def apply_correction(
    calibration_payload: dict[str, Any] | None,
    *,
    base_prob: float,
    surface: str,
    line: float,
    p1_match_prob: float,
    odds1: float,
    odds2: float,
    league: str | None = None,
    best_of: str | None = None,
) -> tuple[float, str]:
    status = model_status(calibration_payload)
    if not status["valid"]:
        return clamp_prob(base_prob), str(status["reason"])

    correction = calibration_payload.get("correction_model") or {}
    usable_scope = status.get("usable_scope") or {}
    surfaces = {str(item).strip() for item in usable_scope.get("surfaces") or [] if str(item).strip()}
    leagues = {str(item).strip() for item in usable_scope.get("leagues") or [] if str(item).strip()}
    best_of_scope = str(usable_scope.get("best_of") or "").strip().lower()

    if surfaces and str(surface or "").strip() not in surfaces:
        return clamp_prob(base_prob), "out-of-scope-surface"
    if leagues and str(league or "").strip() and str(league or "").strip() not in leagues:
        return clamp_prob(base_prob), "out-of-scope-league"
    if best_of_scope and str(best_of or "").strip().lower() and str(best_of or "").strip().lower() != best_of_scope:
        return clamp_prob(base_prob), "out-of-scope-best-of"

    features = feature_vector(
        base_prob=base_prob,
        surface=surface,
        line=line,
        p1_match_prob=p1_match_prob,
        odds1=odds1,
        odds2=odds2,
    )
    if features is None:
        return clamp_prob(base_prob), "invalid-market-odds"

    coefficients = correction.get("coefficients") if isinstance(correction.get("coefficients"), dict) else {}
    intercept = float(correction.get("intercept") or 0.0)
    adjustment = intercept
    for name in FEATURE_NAMES:
        adjustment += float(coefficients.get(name) or 0.0) * float(features.get(name) or 0.0)

    max_abs = float(correction.get("max_abs_logit_adjustment") or DEFAULT_MAX_ABS_LOGIT_ADJUSTMENT)
    adjustment = max(-max_abs, min(max_abs, adjustment))
    corrected = sigmoid(logit(base_prob) + adjustment)
    return clamp_prob(corrected), "ok"
