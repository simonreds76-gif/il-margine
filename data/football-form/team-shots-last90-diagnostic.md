# Team Shots Last-90 Diagnostic

Generated: 2026-04-25T14:43:33+00:00
Latest form date: `2026-04-23`
Recent cutoff: `2026-01-23`

No live policy changed. This report diagnoses the count-lambda regression only.

## Headline

| Sample | Model | N | MAE | Bias | RMSE |
| --- | --- | ---: | ---: | ---: | ---: |
| full_common | current | 2464 | 3.7425 | -0.0412 | 4.7684 |
| full_common | canonical_market | 2464 | 3.7262 | 0.2605 | 4.7002 |
| full_common | canonical_no_market | 2464 | 3.7827 | 0.1468 | 4.7911 |
| last_90_common | current | 1140 | 3.7321 | 0.0184 | 4.7842 |
| last_90_common | canonical_market | 1140 | 3.7699 | 0.3447 | 4.7742 |
| last_90_common | canonical_no_market | 1140 | 3.7948 | 0.2324 | 4.8529 |

## Diagnostic Read

- Cap-disabled recent MAE beats capped recent MAE: `no`
- Current last-90 MAE minus current full-window MAE: `-0.0104`
- If cap-disabled is better, the market-game-state cap is the first suspect. If not, inspect ingestion/history buckets before tuning.

## Last-90 By League

| league | N | Current MAE | Canonical market MAE | Cap disabled MAE | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| bundesliga | 222 | 3.8478 | 3.8572 | 3.8974 | cap helps; canonical lags current |
| epl | 224 | 3.4593 | 3.5884 | 3.6116 | cap helps; canonical lags current |
| la-liga | 242 | 3.8294 | 3.7148 | 3.7757 | cap helps |
| ligue-1 | 212 | 3.5528 | 3.6434 | 3.7075 | cap helps; canonical lags current |
| serie-a | 240 | 3.9397 | 4.026 | 3.9672 | cap hurts; canonical lags current |

## Last-90 By Win-Prob Gap Bucket

| gap_bucket | N | Current MAE | Canonical market MAE | Cap disabled MAE | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| 0-10pp | 218 | 3.8463 | 3.7777 | 3.7872 | cap helps |
| 10-25pp | 350 | 3.6709 | 3.7898 | 3.791 | cap helps; canonical lags current |
| 25-40pp | 260 | 3.555 | 3.5763 | 3.536 | cap hurts; canonical lags current |
| 40-55pp | 186 | 3.7826 | 3.9249 | 4.1182 | cap helps; canonical lags current |
| 55pp+ | 126 | 3.9952 | 3.872 | 3.8751 | cap helps |

## Last-90 By Matchday Bucket

| matchday_bucket | N | Current MAE | Canonical market MAE | Cap disabled MAE | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| md_11_plus | 1140 | 3.7321 | 3.7699 | 3.7948 | cap helps; canonical lags current |

## Last-90 By History Bucket

| history_bucket | N | Current MAE | Canonical market MAE | Cap disabled MAE | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| 10_plus | 1140 | 3.7321 | 3.7699 | 3.7948 | cap helps; canonical lags current |

## Largest Recent Canonical Market Errors

| Date | League | Match | Team | Actual | Current | Canonical | Cap disabled | Gap bucket | Matchday | Min history |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 2026-02-11 | epl | Nott'm Forest vs Wolves | Nott'm Forest | 35.0 | 13.36 | 12.88 | 11.91 | 25-40pp | 72 | 10 |
| 2026-04-17 | ligue-1 | Lens vs Toulouse | Lens | 41.0 | 15.40 | 19.45 | 17.65 | 40-55pp | 86 | 10 |
| 2026-02-08 | serie-a | Juventus vs Lazio | Juventus | 34.0 | 18.30 | 17.29 | 15.52 | 40-55pp | 80 | 10 |
| 2026-02-15 | ligue-1 | Le Havre vs Toulouse | Toulouse | 25.0 | 9.56 | 9.21 | 8.95 | 10-25pp | 64 | 10 |
| 2026-01-23 | serie-a | Inter vs Pisa | Inter | 34.0 | 21.31 | 18.29 | 16.33 | 55pp+ | 69 | 10 |
| 2026-04-18 | bundesliga | Leverkusen vs Augsburg | Leverkusen | 35.0 | 18.93 | 20.20 | 18.05 | 40-55pp | 90 | 10 |
| 2026-02-15 | serie-a | Parma vs Verona | Parma | 27.0 | 12.55 | 12.48 | 12.11 | 10-25pp | 84 | 10 |
| 2026-01-27 | bundesliga | Werder Bremen vs Hoffenheim | Werder Bremen | 26.0 | 11.22 | 11.56 | 12.14 | 10-25pp | 58 | 10 |
| 2026-04-12 | bundesliga | FC Koln vs Werder Bremen | FC Koln | 25.0 | 10.34 | 11.23 | 10.91 | 10-25pp | 88 | 10 |
| 2026-02-01 | serie-a | Como vs Atalanta | Como | 28.0 | 13.84 | 14.43 | 14.09 | 10-25pp | 75 | 10 |
