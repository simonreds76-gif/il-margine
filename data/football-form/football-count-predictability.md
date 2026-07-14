# Football Count Predictability Diagnostics

Generated: 2026-07-14T18:36:08Z
Source matches: 21589

Causal EMA20 attack/opponent-allowance predictions are compared with a prior league mean. Same-day fixtures are scored before any same-day update. This measures count predictability only, not betting edge.

| Market | N | Corr | Model MAE | League MAE | MAE improvement | Total var/mean |
|---|---:|---:|---:|---:|---:|---:|
| Shots | 41990 | 0.447 | 3.637 | 4.029 | 9.7% | 1.386 |
| Shots On Target | 41990 | 0.385 | 1.827 | 1.966 | 7.0% | 1.183 |
| Corners | 41990 | 0.273 | 2.151 | 2.242 | 4.0% | 1.180 |
| Fouls | 41990 | 0.439 | 2.922 | 3.192 | 8.5% | 1.588 |
| Cards | 33042 | 0.224 | 1.029 | 1.039 | 0.9% | 0.816 |

Interpretation: a positive MAE improvement justifies further modelling research. It does not authorize signals without paired real prices, settlement and CLV.
