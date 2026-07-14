# Team Fouls v1: M1 Empirical Registration Baseline

Generated: 2026-07-14T22:48:10Z
Source: `data/corners-ou/historical/all-historical-matches.csv` (21,587/21,589 usable rows)

**Status: research only. M0 market coverage remains blocking; no signals or lock are authorized.**

## Leg structure and raw frailty ceilings

| League | n | HF mean | HF VMR | AF mean | AF VMR | Total VMR | corr(HF,AF) | nu ceiling | alpha H | alpha A | Away gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Bundesliga | 3,671 | 12.14 | 1.376 | 12.65 | 1.431 | 1.761 | 0.255 | 0.0289 | 0.0021 | 0.0052 | +0.51 |
| EPL | 4,560 | 10.61 | 1.108 | 10.97 | 1.151 | 1.245 | 0.102 | 0.0107 | -0.0005 | 0.0031 | +0.36 |
| La Liga | 4,560 | 13.35 | 1.284 | 13.35 | 1.321 | 1.329 | 0.020 | 0.0019 | 0.0193 | 0.0221 | -0.00 |
| Ligue 1 | 4,236 | 12.52 | 1.149 | 12.90 | 1.240 | 1.367 | 0.144 | 0.0135 | -0.0016 | 0.0051 | +0.39 |
| Serie A | 4,560 | 13.20 | 1.267 | 13.55 | 1.338 | 1.520 | 0.167 | 0.0163 | 0.0040 | 0.0087 | +0.35 |
| POOLED | 21,587 | 12.37 | 1.319 | 12.68 | 1.366 | 1.588 | 0.182 | 0.0196 | 0.0062 | 0.0093 | +0.31 |

## Referee registration

- EPL coverage: 100.0%; all other target leagues: 0.0%.
- Eligible EPL referees: 36 (`n >= 10`).
- Unweighted referee grand mean: 21.81 total fouls.
- Within-referee SD: 4.97; true between-referee SD: 1.15.
- Empirical `k=18.6`; registered conservative `k=18`.

## Registered F1 inputs

- Leg quantiles p10/p25/p50/p75/p90: 7 / 10 / 12 / 15 / 18.
- Evaluation lines: 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5.
- Validation folds: 2024-2025, 2025-2026.
- Home fouls/cards correlation: +0.371.
- Opening-odds closeness/total-fouls correlation: +0.202.
- Total-shots/total-fouls correlation: -0.183.
- Cards verdict: **REJECT dedicated model**; retain cards only as a registered fouls feature.
