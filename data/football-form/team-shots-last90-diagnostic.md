# Team Shots Last-90 Diagnostic

Generated: 2026-04-25T16:02:45+00:00
Latest form date: `2026-04-23`
Recent cutoff: `2026-01-23`

No live policy changed. This report diagnoses the count-lambda regression only.

## Headline

| Sample | Model | N | MAE | Bias | RMSE |
| --- | --- | ---: | ---: | ---: | ---: |
| full_common | current | 2464 | 3.7425 | -0.0412 | 4.7684 |
| full_common | canonical_market | 2464 | 3.7262 | 0.2605 | 4.7002 |
| full_common | canonical_no_market | 2464 | 3.7827 | 0.1468 | 4.7911 |
| full_common | canonical_market_t12 | 2464 | 3.7509 | 0.3439 | 4.7226 |
| last_90_common | current | 1140 | 3.7321 | 0.0184 | 4.7842 |
| last_90_common | canonical_market | 1140 | 3.7699 | 0.3447 | 4.7742 |
| last_90_common | canonical_no_market | 1140 | 3.7948 | 0.2324 | 4.8529 |
| last_90_common | canonical_market_t12 | 1140 | 3.8024 | 0.4867 | 4.804 |

## Diagnostic Read

- Cap-disabled recent MAE beats capped recent MAE: `no`
- Current last-90 MAE minus current full-window MAE: `-0.0104`
- If cap-disabled is better, the market-game-state cap is the first suspect. If not, inspect ingestion/history buckets before tuning.
- `canonical_market_t12` is a trailing-12-month league-level normalization replay; it is diagnostic only, not a live policy.

## Last-90 By League

| league | N | Current MAE | Canonical market MAE | Cap disabled MAE | T12 replay MAE | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| bundesliga | 222 | 3.8478 | 3.8572 | 3.8974 | 3.8865 | cap helps; t12 does not help; canonical lags current |
| epl | 224 | 3.4593 | 3.5884 | 3.6116 | 3.5217 | cap helps; t12 helps; canonical lags current |
| la-liga | 242 | 3.8294 | 3.7148 | 3.7757 | 3.8776 | cap helps; t12 does not help |
| ligue-1 | 212 | 3.5528 | 3.6434 | 3.7075 | 3.6724 | cap helps; t12 does not help; canonical lags current |
| serie-a | 240 | 3.9397 | 4.026 | 3.9672 | 4.0254 | cap hurts; t12 helps; canonical lags current |

## Last-90 By Win-Prob Gap Bucket

| gap_bucket | N | Current MAE | Canonical market MAE | Cap disabled MAE | T12 replay MAE | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0-10pp | 218 | 3.8463 | 3.7777 | 3.7872 | 3.8083 | cap helps; t12 does not help |
| 10-25pp | 350 | 3.6709 | 3.7898 | 3.791 | 3.8335 | cap helps; t12 does not help; canonical lags current |
| 25-40pp | 260 | 3.555 | 3.5763 | 3.536 | 3.6044 | cap hurts; t12 does not help; canonical lags current |
| 40-55pp | 186 | 3.7826 | 3.9249 | 4.1182 | 3.928 | cap helps; t12 does not help; canonical lags current |
| 55pp+ | 126 | 3.9952 | 3.872 | 3.8751 | 3.9285 | cap helps; t12 does not help |

## Last-90 By Matchday Bucket

| matchday_bucket | N | Current MAE | Canonical market MAE | Cap disabled MAE | T12 replay MAE | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| md_11_plus | 1140 | 3.7321 | 3.7699 | 3.7948 | 3.8024 | cap helps; t12 does not help; canonical lags current |

## Last-90 By History Bucket

| history_bucket | N | Current MAE | Canonical market MAE | Cap disabled MAE | T12 replay MAE | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 10_plus | 1140 | 3.7321 | 3.7699 | 3.7948 | 3.8024 | cap helps; t12 does not help; canonical lags current |

## Largest Recent Canonical Market Errors

| Date | League | Match | Team | Actual | Current | Canonical | Cap disabled | T12 replay | Gap bucket | Matchday | Min history |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 2026-02-11 | epl | Nott'm Forest vs Wolves | Nott'm Forest | 35.0 | 13.36 | 12.88 | 11.91 | 12.50 | 25-40pp | 72 | 10 |
| 2026-04-17 | ligue-1 | Lens vs Toulouse | Lens | 41.0 | 15.40 | 19.45 | 17.65 | 19.70 | 40-55pp | 86 | 10 |
| 2026-02-08 | serie-a | Juventus vs Lazio | Juventus | 34.0 | 18.30 | 17.29 | 15.52 | 17.23 | 40-55pp | 80 | 10 |
| 2026-02-15 | ligue-1 | Le Havre vs Toulouse | Toulouse | 25.0 | 9.56 | 9.21 | 8.95 | 9.43 | 10-25pp | 64 | 10 |
| 2026-01-23 | serie-a | Inter vs Pisa | Inter | 34.0 | 21.31 | 18.29 | 16.33 | 18.12 | 55pp+ | 69 | 10 |
| 2026-04-18 | bundesliga | Leverkusen vs Augsburg | Leverkusen | 35.0 | 18.93 | 20.20 | 18.05 | 20.42 | 40-55pp | 90 | 10 |
| 2026-02-15 | serie-a | Parma vs Verona | Parma | 27.0 | 12.55 | 12.48 | 12.11 | 12.47 | 10-25pp | 84 | 10 |
| 2026-01-27 | bundesliga | Werder Bremen vs Hoffenheim | Werder Bremen | 26.0 | 11.22 | 11.56 | 12.14 | 11.64 | 10-25pp | 58 | 10 |
| 2026-04-12 | bundesliga | FC Koln vs Werder Bremen | FC Koln | 25.0 | 10.34 | 11.23 | 10.91 | 11.38 | 10-25pp | 88 | 10 |
| 2026-02-01 | serie-a | Como vs Atalanta | Como | 28.0 | 13.84 | 14.43 | 14.09 | 14.36 | 10-25pp | 75 | 10 |

## Largest Error Input Spot Check

| Date | League | Team | Attack input | Opp def input | Quality adj | Market adj | T12 ratio | Prior shots | T12 shots |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-02-11 | epl | Nott'm Forest | 10.37 | 13.26 | 1.021 | 1.081 | 0.970 | 12.71 | 12.33 |
| 2026-04-17 | ligue-1 | Lens | 20.52 | 13.64 | 1.013 | 1.102 | 1.013 | 12.08 | 12.23 |
| 2026-02-08 | serie-a | Juventus | 16.40 | 14.07 | 1.011 | 1.114 | 0.996 | 12.23 | 12.19 |
| 2026-02-15 | ligue-1 | Toulouse | 8.46 | 9.32 | 1.012 | 1.029 | 1.023 | 12.07 | 12.36 |
| 2026-01-23 | serie-a | Inter | 17.06 | 14.65 | 1.022 | 1.120 | 0.991 | 12.22 | 12.11 |
| 2026-04-18 | bundesliga | Leverkusen | 19.15 | 15.04 | 1.043 | 1.119 | 1.011 | 12.92 | 13.06 |
| 2026-02-15 | serie-a | Parma | 12.00 | 12.24 | 1.000 | 1.031 | 0.999 | 12.23 | 12.21 |
| 2026-01-27 | bundesliga | Werder Bremen | 13.62 | 10.69 | 0.987 | 0.952 | 1.007 | 12.91 | 13.01 |
| 2026-04-12 | bundesliga | FC Koln | 12.30 | 8.60 | 1.026 | 1.030 | 1.013 | 12.92 | 13.09 |
| 2026-02-01 | serie-a | Como | 15.90 | 11.27 | 1.020 | 1.024 | 0.996 | 12.23 | 12.17 |
