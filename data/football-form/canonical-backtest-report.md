# Canonical Football Form Backtest

Generated: 2026-04-25T13:37:57+00:00

This is research-only. It compares current model outputs with a first canonical rolling-form formula.
No live policy, thresholds, or published picks are changed by this report.

## Count Accuracy

| Model | Market | N | Mean pred | Mean actual | Bias | MAE | RMSE |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| canonical_form_v0_common | corners_total | 20655 | 10.0747 | 9.8394 | 0.2353 | 2.7492 | 3.4356 |
| canonical_form_v0_full | corners_total | 20657 | 10.0746 | 9.8384 | 0.2362 | 2.7498 | 3.4368 |
| current | corners_total | 20655 | 9.737 | 9.8394 | -0.1024 | 2.7876 | 3.5043 |
| canonical_form_v0_common | team_shots | 2464 | 12.7186 | 12.5719 | 0.1467 | 3.7827 | 4.7911 |
| canonical_form_v0_full | team_shots | 41314 | 12.3331 | 12.3411 | -0.008 | 3.6188 | 4.5909 |
| canonical_form_v1_market_common | team_shots | 2464 | 12.8323 | 12.5719 | 0.2604 | 3.7262 | 4.7002 |
| canonical_form_v1_market_full | team_shots | 41314 | 12.4432 | 12.3411 | 0.1021 | 3.5451 | 4.4955 |
| current | team_shots | 2464 | 12.5306 | 12.5719 | -0.0413 | 3.7425 | 4.7684 |

## Probability Calibration

| Model | Market | Line | N | Actual over | Brier | Log loss |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| canonical_form_v0_common | corners_total | 8.5 | 20655 | 0.6332 | 0.234164 | 0.663943 |
| canonical_form_v0_full | corners_total | 8.5 | 20657 | 0.6332 | 0.234182 | 0.663983 |
| current | corners_total | 8.5 | 20655 | 0.6332 | 0.239777 | 0.677494 |
| canonical_form_v0_common | corners_total | 9.5 | 20655 | 0.5146 | 0.254036 | 0.70317 |
| canonical_form_v0_full | corners_total | 9.5 | 20657 | 0.5146 | 0.254039 | 0.703176 |
| current | corners_total | 9.5 | 20655 | 0.5146 | 0.260443 | 0.721243 |
| canonical_form_v0_common | corners_total | 10.5 | 20655 | 0.3987 | 0.243416 | 0.680944 |
| canonical_form_v0_full | corners_total | 10.5 | 20657 | 0.3987 | 0.24341 | 0.68093 |
| current | corners_total | 10.5 | 20655 | 0.3987 | 0.249076 | 0.700044 |
| canonical_form_v0_common | corners_total | 11.5 | 20655 | 0.2929 | 0.210265 | 0.611865 |
| canonical_form_v0_full | corners_total | 11.5 | 20657 | 0.2929 | 0.210254 | 0.611841 |
| current | corners_total | 11.5 | 20655 | 0.2929 | 0.21434 | 0.628617 |
| canonical_form_v0_common | team_shots | 9.5 | 2464 | 0.6948 | 0.200435 | 0.594522 |
| canonical_form_v0_full | team_shots | 9.5 | 41314 | 0.6854 | 0.196585 | 0.584278 |
| canonical_form_v1_market_common | team_shots | 9.5 | 2464 | 0.6948 | 0.194022 | 0.581699 |
| canonical_form_v1_market_full | team_shots | 9.5 | 41314 | 0.6854 | 0.191258 | 0.574762 |
| current | team_shots | 9.5 | 2464 | 0.6948 | 0.194792 | 0.585727 |
| canonical_form_v0_common | team_shots | 10.5 | 2464 | 0.6149 | 0.22139 | 0.638695 |
| canonical_form_v0_full | team_shots | 10.5 | 41314 | 0.6052 | 0.215828 | 0.625859 |
| canonical_form_v1_market_common | team_shots | 10.5 | 2464 | 0.6149 | 0.215098 | 0.630512 |
| canonical_form_v1_market_full | team_shots | 10.5 | 41314 | 0.6052 | 0.210211 | 0.618623 |
| current | team_shots | 10.5 | 2464 | 0.6149 | 0.21966 | 0.646367 |
| canonical_form_v0_common | team_shots | 11.5 | 2464 | 0.5369 | 0.229042 | 0.654305 |
| canonical_form_v0_full | team_shots | 11.5 | 41314 | 0.5233 | 0.222994 | 0.640495 |
| canonical_form_v1_market_common | team_shots | 11.5 | 2464 | 0.5369 | 0.223026 | 0.648929 |
| canonical_form_v1_market_full | team_shots | 11.5 | 41314 | 0.5233 | 0.217398 | 0.634455 |
| current | team_shots | 11.5 | 2464 | 0.5369 | 0.226782 | 0.663953 |
| canonical_form_v0_common | team_shots | 12.5 | 2464 | 0.4688 | 0.225556 | 0.646639 |
| canonical_form_v0_full | team_shots | 12.5 | 41314 | 0.4462 | 0.21904 | 0.631668 |
| canonical_form_v1_market_common | team_shots | 12.5 | 2464 | 0.4688 | 0.220504 | 0.642707 |
| canonical_form_v1_market_full | team_shots | 12.5 | 41314 | 0.4462 | 0.213897 | 0.626502 |
| current | team_shots | 12.5 | 2464 | 0.4688 | 0.225371 | 0.663574 |
| canonical_form_v0_common | team_shots | 13.5 | 2464 | 0.3973 | 0.217265 | 0.630263 |
| canonical_form_v0_full | team_shots | 13.5 | 41314 | 0.3729 | 0.206706 | 0.604991 |
| canonical_form_v1_market_common | team_shots | 13.5 | 2464 | 0.3973 | 0.212114 | 0.625143 |
| canonical_form_v1_market_full | team_shots | 13.5 | 41314 | 0.3729 | 0.20195 | 0.599502 |
| current | team_shots | 13.5 | 2464 | 0.3973 | 0.215234 | 0.646306 |
| canonical_form_v0_common | team_shots | 14.5 | 2464 | 0.321 | 0.197563 | 0.590446 |
| canonical_form_v0_full | team_shots | 14.5 | 41314 | 0.3026 | 0.187488 | 0.562251 |
| canonical_form_v1_market_common | team_shots | 14.5 | 2464 | 0.321 | 0.193483 | 0.586441 |
| canonical_form_v1_market_full | team_shots | 14.5 | 41314 | 0.3026 | 0.183779 | 0.557381 |
| current | team_shots | 14.5 | 2464 | 0.321 | 0.195981 | 0.608448 |
| canonical_form_v0_common | team_shots | 15.5 | 2464 | 0.2549 | 0.173066 | 0.532963 |
| canonical_form_v0_full | team_shots | 15.5 | 41314 | 0.2434 | 0.164244 | 0.50952 |
| canonical_form_v1_market_common | team_shots | 15.5 | 2464 | 0.2549 | 0.170335 | 0.52873 |
| canonical_form_v1_market_full | team_shots | 15.5 | 41314 | 0.2434 | 0.161067 | 0.503631 |
| current | team_shots | 15.5 | 2464 | 0.2549 | 0.172286 | 0.54712 |

## Read This Properly

- `current` is whatever the existing generated prediction CSV currently contains.
- `canonical_form_v0_common` is tested only on rows where the current generated output also exists.
- `canonical_form_v0_full` is the same formula over the full eligible historical canonical table.
- `canonical_form_v1_market_*` adds a capped pre-match 1X2 win-probability adjustment for expected game state.
- If v0 is worse but close, the canonical layer is still useful as plumbing, not yet as a model replacement.
- If v0 beats current on Brier/log-loss over common lines, then we test it against odds/CLV before promotion.
