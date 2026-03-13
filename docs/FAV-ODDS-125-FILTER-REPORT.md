# Model Fav Odds < 1.25 Filter — Backtest Report

**Date:** 2026-03  
**Data:** ATP 2022–2025 (9,889 matches)  
**Baseline filters:** Model vs Pinnacle fav implied gap > 10pp (always applied)

---

## Filter Rule

Skip the entire match from signals when model favourite odds < 1.25:

```python
model_fav_odds = min(odds1, odds2)
if model_fav_odds < 1.25:
    continue
```

**Rationale:** The model cannot price extreme mismatches. Both favourite and dog signals are unreliable (e.g. Shapovalov +141.9% "value" vs Sinner).

---

## Exclusions

| Filter | Without fav<1.25 | With fav<1.25 |
|--------|------------------|--------------|
| Model vs Pin fav gap >10pp | 2,464 | 2,464 |
| Model fav odds <1.25 | — | 1,670 |
| **Total excluded from ROI** | **2,464** | **3,578** |

---

## ROI by Value Threshold

| Threshold | Metric | Without fav<1.25 | With fav<1.25 | Change |
|-----------|--------|------------------|---------------|--------|
| **Value>2%** | Bets | 5,575 | 4,806 | -769 |
| | Wins | 2,219 | 1,973 | -246 |
| | ROI | -5.81% | **-3.05%** | **+2.76pp** |
| | P/L | -323.7u | -146.7u | +177.0u |
| | Max losing streak | 17 | 17 | — |
| **Value>5%** | Bets | 4,616 | 3,999 | -617 |
| | Wins | 1,707 | 1,569 | -138 |
| | ROI | -6.42% | **-3.23%** | **+3.19pp** |
| | P/L | -296.4u | -129.2u | +167.2u |
| | Max losing streak | 19 | 19 | — |
| **Value>10%** | Bets | 3,364 | 2,917 | -447 |
| | Wins | 1,058 | 1,025 | -33 |
| | ROI | -9.35% | **-4.74%** | **+4.61pp** |
| | P/L | -314.4u | -138.2u | +176.2u |
| | Max losing streak | 20 | 18 | -2 |

---

## Segmentation by Surface (5% threshold)

| Surface | Matches | Metric | Without fav<1.25 | With fav<1.25 | Change |
|---------|---------|--------|------------------|---------------|--------|
| **Hard** | 5,638 | Log loss | 0.62324 | 0.62324 | — |
| | | ROI | -3.56% | **+0.76%** | **+4.32pp** |
| **Clay** | 3,046 | Log loss | 0.62276 | 0.62276 | — |
| | | ROI | -10.60% | **-8.61%** | **+1.99pp** |
| **Grass** | 1,205 | Log loss | 0.61647 | 0.61647 | — |
| | | ROI | -8.81% | **-7.70%** | **+1.11pp** |

---

## Segmentation by Series (5% threshold)

| Series | Matches | Metric | Without fav<1.25 | With fav<1.25 | Change |
|--------|---------|--------|------------------|---------------|--------|
| **ATP250** | 3,896 | Log loss | 0.65597 | 0.65597 | — |
| | | ROI | -6.47% | **-5.26%** | **+1.21pp** |
| **Masters 1000** | 2,468 | Log loss | 0.62953 | 0.62953 | — |
| | | ROI | -1.71% | **+1.18%** | **+2.89pp** |
| **Grand Slam** | 1,898 | Log loss | 0.55361 | 0.55361 | — |
| | | ROI | -8.73% | **-4.16%** | **+4.57pp** |
| **ATP500** | 1,569 | Log loss | 0.61201 | 0.61201 | — |
| | | ROI | -12.24% | **-6.56%** | **+5.68pp** |
| **Masters Cup** | 58 | Log loss | 0.57351 | 0.57351 | — |
| | | ROI | -4.97% | **+18.79%** | **+23.76pp** |

---

## Summary

| Category | Without | With | Improvement |
|----------|---------|------|-------------|
| Value>2% ROI | -5.81% | -3.05% | +2.76pp |
| Value>5% ROI | -6.42% | -3.23% | +3.19pp |
| Value>10% ROI | -9.35% | -4.74% | +4.61pp |
| Hard | -3.56% | +0.76% | +4.32pp |
| Clay | -10.60% | -8.61% | +1.99pp |
| Grass | -8.81% | -7.70% | +1.11pp |
| ATP250 | -6.47% | -5.26% | +1.21pp |
| Masters 1000 | -1.71% | +1.18% | +2.89pp |
| Grand Slam | -8.73% | -4.16% | +4.57pp |
| ATP500 | -12.24% | -6.56% | +5.68pp |
| Masters Cup | -4.97% | +18.79% | +23.76pp |

**Conclusion:** The fav odds < 1.25 filter improves ROI in every category. Hard and Masters 1000 turn positive. Grand Slam improves by 4.57pp. The filter is wired into `strict-policy-report.py`, `fair-odds/route.ts`, and `backtest-fair-odds.py`.

**A/B test:** Run with `--no-misprice-fav-odds` to disable the filter for comparison.
