#!/usr/bin/env python3
"""Regression checks for serializable goalscorer calibrators."""

from __future__ import annotations

import json

from goalscorer_calibration_lib import apply_calibrator, fit_calibrator


def main() -> None:
    probabilities = [0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60] * 30
    labels = [0, 0, 0, 0, 0, 0, 1, 0, 1, 1] * 30
    for kind in ("platt", "beta", "isotonic"):
        calibrator = fit_calibrator(kind, probabilities, labels)
        restored = json.loads(json.dumps(calibrator))
        before = [apply_calibrator(calibrator, probability) for probability in probabilities]
        after = [apply_calibrator(restored, probability) for probability in probabilities]
        assert max(abs(left - right) for left, right in zip(before, after)) < 1e-12
        ordered = [apply_calibrator(calibrator, probability) for probability in sorted(set(probabilities))]
        assert all(left <= right + 1e-12 for left, right in zip(ordered, ordered[1:])), (kind, ordered)
    print("GOALSCORER_CALIBRATION_OK")


if __name__ == "__main__":
    main()
