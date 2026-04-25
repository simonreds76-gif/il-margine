# Team-Shots Feature Gap Diagnostic

Generated: 2026-04-25T19:23:23+00:00
Latest form date: `2026-04-23`
Recent cutoff: `2026-01-23`

No live policy changed. This report compares current vs canonical lambda design.

## Headline

| Sample | N | Current MAE | Canonical MAE | Delta | Current bias | Canonical bias | Mean canonical-current lambda | Canonical worse share | Canonical lower share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full_common | 2464 | 3.7425 | 3.7262 | -0.0163 | -0.0412 | 0.2605 | 0.3017 | 0.5016 | 0.4002 |
| last_90_common | 1140 | 3.7321 | 3.7699 | 0.0379 | 0.0184 | 0.3447 | 0.3262 | 0.5000 | 0.3982 |

## Feature Inventory Diff

| Area | Current model | Canonical v1 | Diagnostic read |
| --- | --- | --- | --- |
| formula | multiplicative: league_avg * attack_ratio * opponent_concession_ratio | additive: 55% attack input + 45% opponent concession input | Primary suspect if canonical is too conservative in high-volume games. |
| history weighting | 20-match exponential moving average with decay 0.93 | 70% r10 + 30% r5 blend when recent window has at least 3 rows | Current may be smoother; canonical may over/under-react to short windows. |
| venue | venue-specific team attack; pooled opponent defence; no extra home multiplier on venue lambda | venue-specific team attack and venue-specific opponent concession | Canonical may overfit venue concession splits, especially with smaller away/home samples. |
| league baseline | causal league average with hard baseline until 40 team observations | causal prior/t12 fields exist, but promoted lambda uses raw shot inputs plus capped ratios only in diagnostics | Current product formula is league-relative by construction. |
| xG | 25% xG lambda blend when team and opponent xG histories are both usable | small capped xG-per-shot quality adjustment | xG is sparse, but current may extract signal in covered rows. |
| market/game state | not in the count lambda | capped 1X2 win-probability adjustment | Already tested: disabling the cap did not fix last-90 aggregate. |
| probability distribution | Poisson probability surface from venue lambda | negative-binomial probability surface from canonical lambda | NB improved probability calibration but does not fix count lambda. |

## Last-90 By League

| league | N | Current MAE | Canonical MAE | Delta | Current bias | Canonical bias | Mean lambda gap | Canonical worse | Canonical lower |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bundesliga | 222 | 3.8478 | 3.8572 | 0.0094 | -0.1195 | 0.2426 | 0.3621 | 0.4369 | 0.4054 |
| epl | 224 | 3.4593 | 3.5884 | 0.1291 | 0.0380 | 0.5118 | 0.4737 | 0.5268 | 0.3661 |
| la-liga | 242 | 3.8294 | 3.7148 | -0.1146 | 0.2675 | 0.4245 | 0.1570 | 0.4545 | 0.4256 |
| ligue-1 | 212 | 3.5528 | 3.6434 | 0.0906 | -0.4230 | 0.0018 | 0.4249 | 0.5519 | 0.3774 |
| serie-a | 240 | 3.9397 | 4.0260 | 0.0863 | 0.2665 | 0.5053 | 0.2388 | 0.5333 | 0.4125 |

## Last-90 By Venue

| venue | N | Current MAE | Canonical MAE | Delta | Current bias | Canonical bias | Mean lambda gap | Canonical worse | Canonical lower |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| away | 570 | 3.5861 | 3.5693 | -0.0168 | 0.3890 | 0.1837 | -0.2053 | 0.4825 | 0.5316 |
| home | 570 | 3.8780 | 3.9706 | 0.0925 | -0.3521 | 0.5056 | 0.8578 | 0.5175 | 0.2649 |

## Last-90 By Win-Prob Gap Bucket

| gap_bucket | N | Current MAE | Canonical MAE | Delta | Current bias | Canonical bias | Mean lambda gap | Canonical worse | Canonical lower |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0-10pp | 218 | 3.8463 | 3.7777 | -0.0687 | 0.2234 | 0.7019 | 0.4785 | 0.4679 | 0.3899 |
| 10-25pp | 350 | 3.6709 | 3.7898 | 0.1189 | -0.0893 | 0.3129 | 0.4022 | 0.5229 | 0.3771 |
| 25-40pp | 260 | 3.5550 | 3.5763 | 0.0213 | -0.0728 | 0.3091 | 0.3820 | 0.5000 | 0.3846 |
| 40-55pp | 186 | 3.7826 | 3.9249 | 0.1423 | -0.0254 | 0.2696 | 0.2950 | 0.5000 | 0.3871 |
| 55pp+ | 126 | 3.9952 | 3.8720 | -0.1231 | 0.2160 | -0.0012 | -0.2171 | 0.4921 | 0.5159 |

## Worst Canonical-vs-Current Last-90 Rows

| Date | League | Match | Team | Venue | Actual | Current | Canonical | Current err | Canon err | Canon-current lambda | Attack | Defence | Current base | Current xG | Current recent | Canon base | Quality effect | Market effect |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-03-22 | bundesliga | Mainz vs Ein Frankfurt | Mainz | home | 8.0 | 13.07 | 17.94 | 5.07 | 9.94 | 4.87 | 16.17 | 16.31 | 11.90 | 14.31 | 13.85 | 16.23 | 1.10 | 0.61 |
| 2026-04-04 | la-liga | Ath Madrid vs Barcelona | Barcelona | away | 22.0 | 18.46 | 14.00 | -3.54 | -8.00 | -4.46 | 17.68 | 7.33 | 17.10 | 21.49 | 18.07 | 13.02 | 0.57 | 0.41 |
| 2026-02-11 | epl | Aston Villa vs Brighton | Aston Villa | home | 15.0 | 14.64 | 19.65 | -0.36 | 4.65 | 5.01 | 18.65 | 17.14 | 14.40 | 14.32 | 17.00 | 17.97 | 0.67 | 1.01 |
| 2026-01-31 | la-liga | Elche vs Barcelona | Barcelona | away | 30.0 | 25.47 | 21.19 | -4.53 | -8.81 | -4.28 | 19.34 | 16.70 | 24.50 | 29.15 | 23.69 | 18.15 | 0.77 | 2.27 |
| 2026-02-21 | serie-a | Lecce vs Inter | Inter | away | 24.0 | 20.06 | 15.93 | -3.94 | -8.07 | -4.13 | 18.22 | 8.24 | 20.22 | 25.96 | 18.89 | 13.73 | 0.60 | 1.60 |
| 2026-01-30 | ligue-1 | Lens vs Le Havre | Lens | home | 15.0 | 16.57 | 20.57 | 1.57 | 5.57 | 4.00 | 14.90 | 20.60 | 16.46 | 19.01 | 13.53 | 17.46 | 0.92 | 2.19 |
| 2026-03-13 | bundesliga | M'gladbach vs St Pauli | M'gladbach | home | 10.0 | 11.59 | 15.58 | 1.59 | 5.58 | 3.99 | 13.95 | 14.18 | 11.72 | 13.25 | 11.96 | 14.05 | 0.65 | 0.88 |
| 2026-02-11 | epl | Sunderland vs Liverpool | Liverpool | away | 23.0 | 14.46 | 10.49 | -8.54 | -12.51 | -3.97 | 10.30 | 8.37 | 16.72 | 15.21 | 12.49 | 9.43 | 0.31 | 0.75 |
| 2026-02-07 | la-liga | Barcelona vs Mallorca | Barcelona | home | 24.0 | 24.71 | 19.32 | 0.71 | -4.68 | -5.39 | 17.80 | 15.43 | 26.15 | 30.00 | 21.59 | 16.73 | 0.52 | 2.07 |
| 2026-02-18 | serie-a | Milan vs Como | Milan | home | 6.0 | 12.72 | 16.55 | 6.72 | 10.55 | 3.83 | 19.30 | 9.93 | 10.50 | 13.82 | 13.12 | 15.08 | 1.01 | 0.46 |
| 2026-02-06 | ligue-1 | Metz vs Lille | Lille | away | 16.0 | 15.28 | 11.48 | -0.72 | -4.52 | -3.80 | 8.34 | 12.28 | 15.40 | 15.37 | 12.26 | 10.11 | 0.33 | 1.05 |
| 2026-03-07 | bundesliga | FC Koln vs Dortmund | Dortmund | away | 13.0 | 14.42 | 18.04 | 1.42 | 5.04 | 3.62 | 15.82 | 15.83 | 14.59 | 16.86 | 14.72 | 15.83 | 1.07 | 1.14 |
| 2026-03-16 | epl | Brentford vs Wolves | Brentford | home | 10.0 | 15.48 | 19.07 | 5.48 | 9.07 | 3.59 | 13.03 | 20.12 | 15.08 | 19.29 | 15.10 | 16.22 | 1.15 | 1.70 |
| 2026-01-25 | epl | Arsenal vs Man United | Man United | away | 10.0 | 10.27 | 13.86 | 0.27 | 3.86 | 3.59 | 20.89 | 7.74 | 9.95 | 9.34 | 11.70 | 14.97 | 0.43 | -1.54 |
| 2026-02-22 | epl | Tottenham vs Arsenal | Tottenham | home | 6.0 | 7.49 | 10.96 | 1.49 | 4.96 | 3.47 | 15.68 | 7.74 | 7.38 | 5.96 | 9.51 | 12.11 | 0.04 | -1.19 |
| 2026-02-22 | ligue-1 | Nice vs Lorient | Nice | home | 8.0 | 11.51 | 14.90 | 3.51 | 6.90 | 3.39 | 14.70 | 14.22 | 10.68 | 9.38 | 12.71 | 14.48 | -0.16 | 0.58 |
| 2026-01-25 | serie-a | Atalanta vs Parma | Atalanta | home | 21.0 | 18.42 | 15.04 | -2.58 | -5.96 | -3.38 | 14.44 | 12.24 | 16.70 | 0.00 | 17.29 | 13.45 | 0.00 | 1.59 |
| 2026-04-12 | la-liga | Celta vs Oviedo | Celta | home | 9.0 | 14.37 | 17.72 | 5.37 | 8.72 | 3.35 | 13.15 | 20.28 | 13.40 | 0.00 | 16.01 | 16.36 | 0.00 | 1.36 |
| 2026-04-18 | bundesliga | Hoffenheim vs Dortmund | Hoffenheim | home | 13.0 | 13.36 | 16.70 | 0.36 | 3.70 | 3.34 | 18.29 | 13.15 | 12.70 | 11.94 | 15.33 | 15.98 | 0.72 | 0.00 |
| 2026-04-04 | bundesliga | Freiburg vs Bayern Munich | Bayern Munich | away | 21.0 | 19.37 | 16.04 | -1.63 | -4.96 | -3.33 | 13.27 | 14.16 | 20.88 | 23.43 | 15.82 | 13.67 | 0.69 | 1.69 |
| 2026-03-14 | epl | Burnley vs Bournemouth | Bournemouth | away | 22.0 | 17.25 | 13.93 | -4.75 | -8.07 | -3.32 | 10.32 | 15.55 | 17.81 | 19.39 | 16.31 | 12.68 | 0.43 | 0.83 |
| 2026-01-24 | epl | Burnley vs Tottenham | Burnley | home | 9.0 | 8.91 | 12.32 | -0.09 | 3.32 | 3.41 | 12.90 | 12.68 | 8.66 | 7.38 | 11.65 | 12.80 | 0.11 | -0.59 |
| 2026-04-22 | la-liga | Sociedad vs Getafe | Sociedad | home | 13.0 | 12.84 | 16.33 | -0.16 | 3.33 | 3.49 | 14.20 | 17.06 | 13.00 | 13.17 | 13.05 | 15.49 | 0.35 | 0.49 |
| 2026-02-08 | serie-a | Sassuolo vs Inter | Inter | away | 23.0 | 20.16 | 17.02 | -2.84 | -5.98 | -3.14 | 16.67 | 12.73 | 20.51 | 21.79 | 19.52 | 14.90 | 0.33 | 1.79 |
| 2026-04-21 | la-liga | Ath Bilbao vs Osasuna | Ath Bilbao | home | 7.0 | 13.91 | 17.03 | 6.91 | 10.03 | 3.12 | 15.33 | 16.14 | 14.07 | 11.68 | 15.56 | 15.70 | 0.25 | 1.09 |

## Read

- If canonical is mostly lower than current in the worst rows, the next test should start with the formula shape: current's multiplicative league-relative lambda vs canonical's additive blend.
- If the gap is mostly venue-specific, test pooled opponent defence vs venue-specific opponent concession before adding new features.
- If both models underpredict extreme actuals, a tail/tempo feature is needed after the formula diff is understood.
