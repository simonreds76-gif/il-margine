# Matchup Model vs Legacy — Backtest Comparison Report

**Sample:** 4,857 matches (2024–2025 ATP, Pinnacle closing odds)  
**Date:** 2026-03-02

---

## Summary

| Metric | Legacy (--no-matchup) | Matchup Model (default) | Winner |
|--------|----------------------|--------------------------|--------|
| **Log loss** | 0.62612 | 0.62382 | Matchup (−0.0023) |
| **Brier score** | 0.21798 | 0.21708 | Matchup |
| **Accuracy (fav wins)** | 65.02% | 65.35% | Matchup |
| **ROI @ Value>2%** | −3.90% | −4.74% | Legacy |
| **ROI @ Value>5%** | −3.36% | −4.82% | Legacy |
| **ROI @ Value>10%** | −2.82% | −6.25% | Legacy |

**Verdict:** Matchup model improves calibration (log loss, Brier, accuracy) but worsens flat-stake ROI at all value thresholds in this sample.

---

## Where We Gained (Matchup Better)

| Segment | Legacy | Matchup | Δ |
|---------|--------|---------|---|
| **Log loss (overall)** | 0.6261 | 0.6238 | −0.23% |
| **Hard courts ROI** | +0.96% | +1.58% | +0.62pp |
| **Masters 1000 ROI** | +5.00% | +5.47% | +0.47pp |
| **Masters Cup ROI** | +13.92% | +16.40% | +2.48pp |
| **50–55% bin calibration** | gap −0.022 | gap −0.001 | tighter |
| **65–70% bin calibration** | gap +0.035 | gap +0.008 | tighter |

---

## Where We Lost (Legacy Better)

| Segment | Legacy | Matchup | Δ |
|---------|--------|---------|---|
| **ROI @ Value>2%** | −3.90% | −4.74% | −0.84pp |
| **ROI @ Value>5%** | −3.36% | −4.82% | −1.46pp |
| **ROI @ Value>10%** | −2.82% | −6.25% | −3.43pp |
| **Grass ROI** | +1.94% | −15.57% | −17.5pp |
| **ATP500 ROI** | +6.97% | −7.59% | −14.6pp |
| **ATP250 ROI** | −13.87% | −12.52% | +1.4pp (matchup slightly better) |

---

## Calibration (Favorite Probability Bins)

| Bin | Legacy pred | Legacy actual | Matchup pred | Matchup actual |
|-----|-------------|---------------|--------------|----------------|
| 50–55% | 0.530 | 0.508 | 0.529 | 0.528 |
| 55–60% | 0.574 | 0.561 | 0.575 | 0.547 |
| 60–65% | 0.623 | 0.599 | 0.623 | 0.604 |
| 65–70% | 0.674 | 0.709 | 0.675 | 0.682 |
| 70–75% | 0.724 | 0.706 | 0.724 | 0.716 |
| 75–80% | 0.774 | 0.785 | 0.775 | 0.760 |
| 80–85% | 0.822 | 0.732 | 0.822 | 0.743 |
| 85–90% | 0.870 | 0.802 | 0.872 | 0.810 |
| 90–95% | 0.922 | 0.874 | 0.922 | 0.867 |

Matchup model is slightly better calibrated in mid-range bins (65–70%, 70–75%); both overconfident at 80%+.

---

## Matchup Model Coverage

- **2024:** 87.9% both_decomposed, 12.1% fallback
- **2025:** 89.5% both_decomposed, 10.5% fallback

---

## Takeaways

1. **Calibration:** Matchup model improves log loss and Brier; predictions are slightly better calibrated.
2. **ROI:** Legacy formula yields better flat-stake ROI in this sample; matchup is worse at higher value thresholds.
3. **Grass & ATP500:** Large drop with matchup model (−17.5pp Grass, −14.6pp ATP500). Worth investigating whether decomposed stats or surface averages are off for these segments.
4. **Hard & Masters 1000:** Matchup model improves ROI in these segments.
5. **Recommendation:** Use matchup for live fair odds (better calibration). For backtest ROI, consider segment-specific tuning or a hybrid (e.g. matchup on Hard/M1000, legacy on Grass/ATP500) pending further analysis.
