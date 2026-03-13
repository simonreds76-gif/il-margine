# Return Decomposition — Hard | Masters 1000 Backtest Comparison

**Segment:** Hard courts + Masters 1000 only (863 matches)  
**Date:** 2026-03-02

---

## Summary

| Metric | Without Return Decomp | With Return Decomp | Δ |
|--------|------------------------|---------------------|---|
| **Log loss** | 0.62465 | 0.62194 | −0.0027 (better) |
| **Brier score** | 0.21717 | 0.21608 | −0.0011 (better) |
| **Accuracy** | 66.28% | 66.98% | +0.7pp |
| **ROI @ Value>2%** | +11.41% | +10.98% | −0.4pp |
| **ROI @ Value>5%** | +13.03% | +11.99% | −1.0pp |
| **ROI @ Value>10%** | +13.87% | +15.10% | **+1.2pp** |

---

## Verdict

**Return decomposition improves calibration** (log loss, Brier, accuracy) and **improves ROI at the highest value threshold** (10%: +1.2pp). At 5% value, it slightly reduces ROI (−1.0pp).

The 6.7pp differentiation from the matchup model self-test translates to:
- Better probability estimates (log loss −0.27%)
- Stronger ROI at Value>10% (+1.2pp)
- Slight ROI drop at Value>5% (−1.0pp)

**Recommendation:** Keep return decomposition. The calibration gain is real; the 5% ROI dip may be noise in a 863-match sample. Re-run across more years/periods to confirm stability.

---

## Commands Used

```bash
# Without return decomposition
python scripts/backtest-fair-odds.py --filter-hard-m1000 --no-decomposed-return

# With return decomposition (default)
python scripts/backtest-fair-odds.py --filter-hard-m1000
```
