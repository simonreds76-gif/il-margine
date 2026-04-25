# Canonical Football Form Backtest

Generated: 2026-04-25T16:01:35+00:00

This is research-only. It compares current model outputs with a first canonical rolling-form formula.
No live policy, thresholds, or published picks are changed by this report.

## Count Accuracy

| Model | Market | Sample | N | Mean pred | Mean actual | Bias | MAE | RMSE |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| canonical_form_v0 | corners_total | common | 20655 | 10.0747 | 9.8394 | 0.2353 | 2.7492 | 3.4356 |
| canonical_form_v0_t12 | corners_total | common | 20655 | 9.9706 | 9.8394 | 0.1312 | 2.7556 | 3.4485 |
| current | corners_total | common | 20655 | 9.737 | 9.8394 | -0.1024 | 2.7876 | 3.5043 |
| canonical_form_v0 | corners_total | canonical_only | 2 | 9.8308 | 0.0 | 9.8308 | 9.8308 | 9.9031 |
| canonical_form_v0_t12 | corners_total | canonical_only | 2 | 9.9318 | 0.0 | 9.9318 | 9.9318 | 9.9924 |
| canonical_form_v0 | corners_total | full | 20657 | 10.0746 | 9.8384 | 0.2362 | 2.7498 | 3.4368 |
| canonical_form_v0_t12 | corners_total | full | 20657 | 9.9707 | 9.8384 | 0.1323 | 2.7563 | 3.4497 |
| canonical_form_v0 | corners_total | last_90_common | 570 | 9.6137 | 9.5491 | 0.0646 | 2.6309 | 3.2712 |
| canonical_form_v0_t12 | corners_total | last_90_common | 570 | 9.3327 | 9.5491 | -0.2164 | 2.652 | 3.3007 |
| current | corners_total | last_90_common | 570 | 9.0671 | 9.5491 | -0.482 | 2.6663 | 3.3694 |
| canonical_form_v0 | corners_total | last_90_full | 570 | 9.6137 | 9.5491 | 0.0646 | 2.6309 | 3.2712 |
| canonical_form_v0_t12 | corners_total | last_90_full | 570 | 9.3327 | 9.5491 | -0.2164 | 2.652 | 3.3007 |
| canonical_form_v0 | team_shots | common | 2464 | 12.7186 | 12.5719 | 0.1467 | 3.7827 | 4.7911 |
| canonical_form_v1_market | team_shots | common | 2464 | 12.8323 | 12.5719 | 0.2604 | 3.7262 | 4.7002 |
| canonical_form_v1_market_nb | team_shots | common | 2464 | 12.8323 | 12.5719 | 0.2604 | 3.7262 | 4.7002 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 2464 | 12.9157 | 12.5719 | 0.3438 | 3.7509 | 4.7226 |
| current | team_shots | common | 2464 | 12.5306 | 12.5719 | -0.0413 | 3.7425 | 4.7684 |
| canonical_form_v0 | team_shots | canonical_only | 38850 | 12.3086 | 12.3265 | -0.0179 | 3.6083 | 4.5779 |
| canonical_form_v1_market | team_shots | canonical_only | 38850 | 12.4185 | 12.3265 | 0.092 | 3.5336 | 4.4822 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 38850 | 12.4185 | 12.3265 | 0.092 | 3.5336 | 4.4822 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 38850 | 12.4483 | 12.3265 | 0.1218 | 3.5619 | 4.5162 |
| canonical_form_v0 | team_shots | full | 41314 | 12.3331 | 12.3411 | -0.008 | 3.6188 | 4.5909 |
| canonical_form_v1_market | team_shots | full | 41314 | 12.4432 | 12.3411 | 0.1021 | 3.5451 | 4.4955 |
| canonical_form_v1_market_nb | team_shots | full | 41314 | 12.4432 | 12.3411 | 0.1021 | 3.5451 | 4.4955 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 41314 | 12.4762 | 12.3411 | 0.1351 | 3.5731 | 4.5288 |
| canonical_form_v0 | team_shots | last_90_common | 1140 | 12.8499 | 12.6175 | 0.2324 | 3.7948 | 4.8529 |
| canonical_form_v1_market | team_shots | last_90_common | 1140 | 12.9622 | 12.6175 | 0.3447 | 3.7699 | 4.7742 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 1140 | 12.9622 | 12.6175 | 0.3447 | 3.7699 | 4.7742 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 1140 | 13.1042 | 12.6175 | 0.4867 | 3.8024 | 4.804 |
| current | team_shots | last_90_common | 1140 | 12.636 | 12.6175 | 0.0185 | 3.732 | 4.7842 |
| canonical_form_v0 | team_shots | last_90_full | 1140 | 12.8499 | 12.6175 | 0.2324 | 3.7948 | 4.8529 |
| canonical_form_v1_market | team_shots | last_90_full | 1140 | 12.9622 | 12.6175 | 0.3447 | 3.7699 | 4.7742 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 1140 | 12.9622 | 12.6175 | 0.3447 | 3.7699 | 4.7742 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 1140 | 13.1042 | 12.6175 | 0.4867 | 3.8024 | 4.804 |

## Probability Calibration

| Model | Market | Sample | Line | N | Actual over | Brier | Log loss |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| canonical_form_v0 | corners_total | common | 8.5 | 20655 | 0.6332 | 0.234164 | 0.663943 |
| canonical_form_v0_t12 | corners_total | common | 8.5 | 20655 | 0.6332 | 0.235408 | 0.66671 |
| current | corners_total | common | 8.5 | 20655 | 0.6332 | 0.239777 | 0.677494 |
| canonical_form_v0 | corners_total | common | 9.5 | 20655 | 0.5146 | 0.254036 | 0.70317 |
| canonical_form_v0_t12 | corners_total | common | 9.5 | 20655 | 0.5146 | 0.255499 | 0.706746 |
| current | corners_total | common | 9.5 | 20655 | 0.5146 | 0.260443 | 0.721243 |
| canonical_form_v0 | corners_total | common | 10.5 | 20655 | 0.3987 | 0.243416 | 0.680944 |
| canonical_form_v0_t12 | corners_total | common | 10.5 | 20655 | 0.3987 | 0.24467 | 0.684633 |
| current | corners_total | common | 10.5 | 20655 | 0.3987 | 0.249076 | 0.700044 |
| canonical_form_v0 | corners_total | common | 11.5 | 20655 | 0.2929 | 0.210265 | 0.611865 |
| canonical_form_v0_t12 | corners_total | common | 11.5 | 20655 | 0.2929 | 0.210948 | 0.614563 |
| current | corners_total | common | 11.5 | 20655 | 0.2929 | 0.21434 | 0.628617 |
| canonical_form_v0 | corners_total | canonical_only | 8.5 | 2 | 0.0 | 0.419429 | 1.077527 |
| canonical_form_v0_t12 | corners_total | canonical_only | 8.5 | 2 | 0.0 | 0.433324 | 1.105617 |
| canonical_form_v0 | corners_total | canonical_only | 9.5 | 2 | 0.0 | 0.285806 | 0.769585 |
| canonical_form_v0_t12 | corners_total | canonical_only | 9.5 | 2 | 0.0 | 0.29593 | 0.791164 |
| canonical_form_v0 | corners_total | canonical_only | 10.5 | 2 | 0.0 | 0.179207 | 0.536751 |
| canonical_form_v0_t12 | corners_total | canonical_only | 10.5 | 2 | 0.0 | 0.185475 | 0.552731 |
| canonical_form_v0 | corners_total | canonical_only | 11.5 | 2 | 0.0 | 0.103097 | 0.364687 |
| canonical_form_v0_t12 | corners_total | canonical_only | 11.5 | 2 | 0.0 | 0.10644 | 0.376038 |
| canonical_form_v0 | corners_total | full | 8.5 | 20657 | 0.6332 | 0.234182 | 0.663983 |
| canonical_form_v0_t12 | corners_total | full | 8.5 | 20657 | 0.6332 | 0.235427 | 0.666753 |
| canonical_form_v0 | corners_total | full | 9.5 | 20657 | 0.5146 | 0.254039 | 0.703176 |
| canonical_form_v0_t12 | corners_total | full | 9.5 | 20657 | 0.5146 | 0.255503 | 0.706754 |
| canonical_form_v0 | corners_total | full | 10.5 | 20657 | 0.3987 | 0.24341 | 0.68093 |
| canonical_form_v0_t12 | corners_total | full | 10.5 | 20657 | 0.3987 | 0.244664 | 0.68462 |
| canonical_form_v0 | corners_total | full | 11.5 | 20657 | 0.2929 | 0.210254 | 0.611841 |
| canonical_form_v0_t12 | corners_total | full | 11.5 | 20657 | 0.2929 | 0.210938 | 0.614539 |
| canonical_form_v0 | corners_total | last_90_common | 8.5 | 570 | 0.6 | 0.241215 | 0.676757 |
| canonical_form_v0_t12 | corners_total | last_90_common | 8.5 | 570 | 0.6 | 0.242906 | 0.680169 |
| current | corners_total | last_90_common | 8.5 | 570 | 0.6 | 0.252339 | 0.701956 |
| canonical_form_v0 | corners_total | last_90_common | 9.5 | 570 | 0.4912 | 0.251907 | 0.698118 |
| canonical_form_v0_t12 | corners_total | last_90_common | 9.5 | 570 | 0.4912 | 0.255049 | 0.70623 |
| current | corners_total | last_90_common | 9.5 | 570 | 0.4912 | 0.260442 | 0.723925 |
| canonical_form_v0 | corners_total | last_90_common | 10.5 | 570 | 0.3702 | 0.235092 | 0.663814 |
| canonical_form_v0_t12 | corners_total | last_90_common | 10.5 | 570 | 0.3702 | 0.23888 | 0.675787 |
| current | corners_total | last_90_common | 10.5 | 570 | 0.3702 | 0.243554 | 0.698496 |
| canonical_form_v0 | corners_total | last_90_common | 11.5 | 570 | 0.2649 | 0.194359 | 0.57694 |
| canonical_form_v0_t12 | corners_total | last_90_common | 11.5 | 570 | 0.2649 | 0.197189 | 0.587357 |
| current | corners_total | last_90_common | 11.5 | 570 | 0.2649 | 0.19763 | 0.601575 |
| canonical_form_v0 | corners_total | last_90_full | 8.5 | 570 | 0.6 | 0.241215 | 0.676757 |
| canonical_form_v0_t12 | corners_total | last_90_full | 8.5 | 570 | 0.6 | 0.242906 | 0.680169 |
| canonical_form_v0 | corners_total | last_90_full | 9.5 | 570 | 0.4912 | 0.251907 | 0.698118 |
| canonical_form_v0_t12 | corners_total | last_90_full | 9.5 | 570 | 0.4912 | 0.255049 | 0.70623 |
| canonical_form_v0 | corners_total | last_90_full | 10.5 | 570 | 0.3702 | 0.235092 | 0.663814 |
| canonical_form_v0_t12 | corners_total | last_90_full | 10.5 | 570 | 0.3702 | 0.23888 | 0.675787 |
| canonical_form_v0 | corners_total | last_90_full | 11.5 | 570 | 0.2649 | 0.194359 | 0.57694 |
| canonical_form_v0_t12 | corners_total | last_90_full | 11.5 | 570 | 0.2649 | 0.197189 | 0.587357 |
| canonical_form_v0 | team_shots | common | 9.5 | 2464 | 0.6948 | 0.200435 | 0.594522 |
| canonical_form_v1_market | team_shots | common | 9.5 | 2464 | 0.6948 | 0.194022 | 0.581699 |
| canonical_form_v1_market_nb | team_shots | common | 9.5 | 2464 | 0.6948 | 0.188491 | 0.555155 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 9.5 | 2464 | 0.6948 | 0.189473 | 0.557673 |
| current | team_shots | common | 9.5 | 2464 | 0.6948 | 0.194792 | 0.585727 |
| canonical_form_v0 | team_shots | common | 10.5 | 2464 | 0.6149 | 0.22139 | 0.638695 |
| canonical_form_v1_market | team_shots | common | 10.5 | 2464 | 0.6149 | 0.215098 | 0.630512 |
| canonical_form_v1_market_nb | team_shots | common | 10.5 | 2464 | 0.6149 | 0.207896 | 0.601347 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 10.5 | 2464 | 0.6149 | 0.20925 | 0.604568 |
| current | team_shots | common | 10.5 | 2464 | 0.6149 | 0.21966 | 0.646367 |
| canonical_form_v0 | team_shots | common | 11.5 | 2464 | 0.5369 | 0.229042 | 0.654305 |
| canonical_form_v1_market | team_shots | common | 11.5 | 2464 | 0.5369 | 0.223026 | 0.648929 |
| canonical_form_v1_market_nb | team_shots | common | 11.5 | 2464 | 0.5369 | 0.215436 | 0.620042 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 11.5 | 2464 | 0.5369 | 0.21654 | 0.622506 |
| current | team_shots | common | 11.5 | 2464 | 0.5369 | 0.226782 | 0.663953 |
| canonical_form_v0 | team_shots | common | 12.5 | 2464 | 0.4688 | 0.225556 | 0.646639 |
| canonical_form_v1_market | team_shots | common | 12.5 | 2464 | 0.4688 | 0.220504 | 0.642707 |
| canonical_form_v1_market_nb | team_shots | common | 12.5 | 2464 | 0.4688 | 0.21361 | 0.616963 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 12.5 | 2464 | 0.4688 | 0.214514 | 0.618824 |
| current | team_shots | common | 12.5 | 2464 | 0.4688 | 0.225371 | 0.663574 |
| canonical_form_v0 | team_shots | common | 13.5 | 2464 | 0.3973 | 0.217265 | 0.630263 |
| canonical_form_v1_market | team_shots | common | 13.5 | 2464 | 0.3973 | 0.212114 | 0.625143 |
| canonical_form_v1_market_nb | team_shots | common | 13.5 | 2464 | 0.3973 | 0.20548 | 0.599461 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 13.5 | 2464 | 0.3973 | 0.206538 | 0.601704 |
| current | team_shots | common | 13.5 | 2464 | 0.3973 | 0.215234 | 0.646306 |
| canonical_form_v0 | team_shots | common | 14.5 | 2464 | 0.321 | 0.197563 | 0.590446 |
| canonical_form_v1_market | team_shots | common | 14.5 | 2464 | 0.321 | 0.193483 | 0.586441 |
| canonical_form_v1_market_nb | team_shots | common | 14.5 | 2464 | 0.321 | 0.188057 | 0.5607 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 14.5 | 2464 | 0.321 | 0.189033 | 0.562693 |
| current | team_shots | common | 14.5 | 2464 | 0.321 | 0.195981 | 0.608448 |
| canonical_form_v0 | team_shots | common | 15.5 | 2464 | 0.2549 | 0.173066 | 0.532963 |
| canonical_form_v1_market | team_shots | common | 15.5 | 2464 | 0.2549 | 0.170335 | 0.52873 |
| canonical_form_v1_market_nb | team_shots | common | 15.5 | 2464 | 0.2549 | 0.165983 | 0.506399 |
| canonical_form_v1_market_nb_t12 | team_shots | common | 15.5 | 2464 | 0.2549 | 0.166568 | 0.507496 |
| current | team_shots | common | 15.5 | 2464 | 0.2549 | 0.172286 | 0.54712 |
| canonical_form_v0 | team_shots | canonical_only | 9.5 | 38850 | 0.6848 | 0.19634 | 0.583628 |
| canonical_form_v1_market | team_shots | canonical_only | 9.5 | 38850 | 0.6848 | 0.191082 | 0.574321 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 9.5 | 38850 | 0.6848 | 0.188222 | 0.555928 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 9.5 | 38850 | 0.6848 | 0.18904 | 0.557948 |
| canonical_form_v0 | team_shots | canonical_only | 10.5 | 38850 | 0.6046 | 0.215475 | 0.625045 |
| canonical_form_v1_market | team_shots | canonical_only | 10.5 | 38850 | 0.6046 | 0.209901 | 0.617869 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 10.5 | 38850 | 0.6046 | 0.205451 | 0.596864 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 10.5 | 38850 | 0.6046 | 0.206313 | 0.599062 |
| canonical_form_v0 | team_shots | canonical_only | 11.5 | 38850 | 0.5224 | 0.22261 | 0.639619 |
| canonical_form_v1_market | team_shots | canonical_only | 11.5 | 38850 | 0.5224 | 0.217041 | 0.633537 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 11.5 | 38850 | 0.5224 | 0.211514 | 0.611582 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 11.5 | 38850 | 0.5224 | 0.212368 | 0.613771 |
| canonical_form_v0 | team_shots | canonical_only | 12.5 | 38850 | 0.4448 | 0.218627 | 0.630719 |
| canonical_form_v1_market | team_shots | canonical_only | 12.5 | 38850 | 0.4448 | 0.213478 | 0.625474 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 12.5 | 38850 | 0.4448 | 0.207734 | 0.603405 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 12.5 | 38850 | 0.4448 | 0.208643 | 0.605737 |
| canonical_form_v0 | team_shots | canonical_only | 13.5 | 38850 | 0.3713 | 0.206036 | 0.603388 |
| canonical_form_v1_market | team_shots | canonical_only | 13.5 | 38850 | 0.3713 | 0.201306 | 0.597875 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 13.5 | 38850 | 0.3713 | 0.195988 | 0.576185 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 13.5 | 38850 | 0.3713 | 0.19695 | 0.578485 |
| canonical_form_v0 | team_shots | canonical_only | 14.5 | 38850 | 0.3015 | 0.186849 | 0.560463 |
| canonical_form_v1_market | team_shots | canonical_only | 14.5 | 38850 | 0.3015 | 0.183164 | 0.555538 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 14.5 | 38850 | 0.3015 | 0.178429 | 0.534246 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 14.5 | 38850 | 0.3015 | 0.179377 | 0.536518 |
| canonical_form_v0 | team_shots | canonical_only | 15.5 | 38850 | 0.2426 | 0.163685 | 0.508034 |
| canonical_form_v1_market | team_shots | canonical_only | 15.5 | 38850 | 0.2426 | 0.160479 | 0.502039 |
| canonical_form_v1_market_nb | team_shots | canonical_only | 15.5 | 38850 | 0.2426 | 0.157118 | 0.482493 |
| canonical_form_v1_market_nb_t12 | team_shots | canonical_only | 15.5 | 38850 | 0.2426 | 0.158031 | 0.484623 |
| canonical_form_v0 | team_shots | full | 9.5 | 41314 | 0.6854 | 0.196585 | 0.584278 |
| canonical_form_v1_market | team_shots | full | 9.5 | 41314 | 0.6854 | 0.191258 | 0.574762 |
| canonical_form_v1_market_nb | team_shots | full | 9.5 | 41314 | 0.6854 | 0.188238 | 0.555882 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 9.5 | 41314 | 0.6854 | 0.189065 | 0.557932 |
| canonical_form_v0 | team_shots | full | 10.5 | 41314 | 0.6052 | 0.215828 | 0.625859 |
| canonical_form_v1_market | team_shots | full | 10.5 | 41314 | 0.6052 | 0.210211 | 0.618623 |
| canonical_form_v1_market_nb | team_shots | full | 10.5 | 41314 | 0.6052 | 0.205597 | 0.597131 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 10.5 | 41314 | 0.6052 | 0.206488 | 0.599391 |
| canonical_form_v0 | team_shots | full | 11.5 | 41314 | 0.5233 | 0.222994 | 0.640495 |
| canonical_form_v1_market | team_shots | full | 11.5 | 41314 | 0.5233 | 0.217398 | 0.634455 |
| canonical_form_v1_market_nb | team_shots | full | 11.5 | 41314 | 0.5233 | 0.211748 | 0.612086 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 11.5 | 41314 | 0.5233 | 0.212617 | 0.614292 |
| canonical_form_v0 | team_shots | full | 12.5 | 41314 | 0.4462 | 0.21904 | 0.631668 |
| canonical_form_v1_market | team_shots | full | 12.5 | 41314 | 0.4462 | 0.213897 | 0.626502 |
| canonical_form_v1_market_nb | team_shots | full | 12.5 | 41314 | 0.4462 | 0.208084 | 0.604214 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 12.5 | 41314 | 0.4462 | 0.208993 | 0.606518 |
| canonical_form_v0 | team_shots | full | 13.5 | 41314 | 0.3729 | 0.206706 | 0.604991 |
| canonical_form_v1_market | team_shots | full | 13.5 | 41314 | 0.3729 | 0.20195 | 0.599502 |
| canonical_form_v1_market_nb | team_shots | full | 13.5 | 41314 | 0.3729 | 0.196555 | 0.577574 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 13.5 | 41314 | 0.3729 | 0.197522 | 0.57987 |
| canonical_form_v0 | team_shots | full | 14.5 | 41314 | 0.3026 | 0.187488 | 0.562251 |
| canonical_form_v1_market | team_shots | full | 14.5 | 41314 | 0.3026 | 0.183779 | 0.557381 |
| canonical_form_v1_market_nb | team_shots | full | 14.5 | 41314 | 0.3026 | 0.179003 | 0.535824 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 14.5 | 41314 | 0.3026 | 0.179953 | 0.53808 |
| canonical_form_v0 | team_shots | full | 15.5 | 41314 | 0.2434 | 0.164244 | 0.50952 |
| canonical_form_v1_market | team_shots | full | 15.5 | 41314 | 0.2434 | 0.161067 | 0.503631 |
| canonical_form_v1_market_nb | team_shots | full | 15.5 | 41314 | 0.2434 | 0.157647 | 0.483919 |
| canonical_form_v1_market_nb_t12 | team_shots | full | 15.5 | 41314 | 0.2434 | 0.15854 | 0.485987 |
| canonical_form_v0 | team_shots | last_90_common | 9.5 | 1140 | 0.7062 | 0.196791 | 0.587315 |
| canonical_form_v1_market | team_shots | last_90_common | 9.5 | 1140 | 0.7062 | 0.191776 | 0.576092 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 9.5 | 1140 | 0.7062 | 0.186361 | 0.549775 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 9.5 | 1140 | 0.7062 | 0.186942 | 0.55157 |
| current | team_shots | last_90_common | 9.5 | 1140 | 0.7062 | 0.191206 | 0.570979 |
| canonical_form_v0 | team_shots | last_90_common | 10.5 | 1140 | 0.6184 | 0.22393 | 0.643951 |
| canonical_form_v1_market | team_shots | last_90_common | 10.5 | 1140 | 0.6184 | 0.219483 | 0.638697 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 10.5 | 1140 | 0.6184 | 0.210538 | 0.605817 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 10.5 | 1140 | 0.6184 | 0.211858 | 0.609167 |
| current | team_shots | last_90_common | 10.5 | 1140 | 0.6184 | 0.221205 | 0.642077 |
| canonical_form_v0 | team_shots | last_90_common | 11.5 | 1140 | 0.5395 | 0.230959 | 0.6571 |
| canonical_form_v1_market | team_shots | last_90_common | 11.5 | 1140 | 0.5395 | 0.224935 | 0.65174 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 11.5 | 1140 | 0.5395 | 0.21653 | 0.621401 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 11.5 | 1140 | 0.5395 | 0.218092 | 0.624852 |
| current | team_shots | last_90_common | 11.5 | 1140 | 0.5395 | 0.224392 | 0.651691 |
| canonical_form_v0 | team_shots | last_90_common | 12.5 | 1140 | 0.457 | 0.228181 | 0.651294 |
| canonical_form_v1_market | team_shots | last_90_common | 12.5 | 1140 | 0.457 | 0.22409 | 0.650601 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 12.5 | 1140 | 0.457 | 0.215388 | 0.620389 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 12.5 | 1140 | 0.457 | 0.216792 | 0.623125 |
| current | team_shots | last_90_common | 12.5 | 1140 | 0.457 | 0.224599 | 0.654523 |
| canonical_form_v0 | team_shots | last_90_common | 13.5 | 1140 | 0.3824 | 0.217385 | 0.629215 |
| canonical_form_v1_market | team_shots | last_90_common | 13.5 | 1140 | 0.3824 | 0.213137 | 0.626801 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 13.5 | 1140 | 0.3824 | 0.20518 | 0.598801 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 13.5 | 1140 | 0.3824 | 0.206678 | 0.601829 |
| current | team_shots | last_90_common | 13.5 | 1140 | 0.3824 | 0.210324 | 0.625461 |
| canonical_form_v0 | team_shots | last_90_common | 14.5 | 1140 | 0.307 | 0.193236 | 0.577815 |
| canonical_form_v1_market | team_shots | last_90_common | 14.5 | 1140 | 0.307 | 0.190107 | 0.576038 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 14.5 | 1140 | 0.307 | 0.184619 | 0.552472 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 14.5 | 1140 | 0.307 | 0.185827 | 0.554745 |
| current | team_shots | last_90_common | 14.5 | 1140 | 0.307 | 0.189393 | 0.580746 |
| canonical_form_v0 | team_shots | last_90_common | 15.5 | 1140 | 0.2439 | 0.170271 | 0.522568 |
| canonical_form_v1_market | team_shots | last_90_common | 15.5 | 1140 | 0.2439 | 0.169368 | 0.524093 |
| canonical_form_v1_market_nb | team_shots | last_90_common | 15.5 | 1140 | 0.2439 | 0.16438 | 0.502552 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_common | 15.5 | 1140 | 0.2439 | 0.165485 | 0.504981 |
| current | team_shots | last_90_common | 15.5 | 1140 | 0.2439 | 0.166206 | 0.524896 |
| canonical_form_v0 | team_shots | last_90_full | 9.5 | 1140 | 0.7062 | 0.196791 | 0.587315 |
| canonical_form_v1_market | team_shots | last_90_full | 9.5 | 1140 | 0.7062 | 0.191776 | 0.576092 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 9.5 | 1140 | 0.7062 | 0.186361 | 0.549775 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 9.5 | 1140 | 0.7062 | 0.186942 | 0.55157 |
| canonical_form_v0 | team_shots | last_90_full | 10.5 | 1140 | 0.6184 | 0.22393 | 0.643951 |
| canonical_form_v1_market | team_shots | last_90_full | 10.5 | 1140 | 0.6184 | 0.219483 | 0.638697 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 10.5 | 1140 | 0.6184 | 0.210538 | 0.605817 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 10.5 | 1140 | 0.6184 | 0.211858 | 0.609167 |
| canonical_form_v0 | team_shots | last_90_full | 11.5 | 1140 | 0.5395 | 0.230959 | 0.6571 |
| canonical_form_v1_market | team_shots | last_90_full | 11.5 | 1140 | 0.5395 | 0.224935 | 0.65174 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 11.5 | 1140 | 0.5395 | 0.21653 | 0.621401 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 11.5 | 1140 | 0.5395 | 0.218092 | 0.624852 |
| canonical_form_v0 | team_shots | last_90_full | 12.5 | 1140 | 0.457 | 0.228181 | 0.651294 |
| canonical_form_v1_market | team_shots | last_90_full | 12.5 | 1140 | 0.457 | 0.22409 | 0.650601 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 12.5 | 1140 | 0.457 | 0.215388 | 0.620389 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 12.5 | 1140 | 0.457 | 0.216792 | 0.623125 |
| canonical_form_v0 | team_shots | last_90_full | 13.5 | 1140 | 0.3824 | 0.217385 | 0.629215 |
| canonical_form_v1_market | team_shots | last_90_full | 13.5 | 1140 | 0.3824 | 0.213137 | 0.626801 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 13.5 | 1140 | 0.3824 | 0.20518 | 0.598801 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 13.5 | 1140 | 0.3824 | 0.206678 | 0.601829 |
| canonical_form_v0 | team_shots | last_90_full | 14.5 | 1140 | 0.307 | 0.193236 | 0.577815 |
| canonical_form_v1_market | team_shots | last_90_full | 14.5 | 1140 | 0.307 | 0.190107 | 0.576038 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 14.5 | 1140 | 0.307 | 0.184619 | 0.552472 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 14.5 | 1140 | 0.307 | 0.185827 | 0.554745 |
| canonical_form_v0 | team_shots | last_90_full | 15.5 | 1140 | 0.2439 | 0.170271 | 0.522568 |
| canonical_form_v1_market | team_shots | last_90_full | 15.5 | 1140 | 0.2439 | 0.169368 | 0.524093 |
| canonical_form_v1_market_nb | team_shots | last_90_full | 15.5 | 1140 | 0.2439 | 0.16438 | 0.502552 |
| canonical_form_v1_market_nb_t12 | team_shots | last_90_full | 15.5 | 1140 | 0.2439 | 0.165485 | 0.504981 |

## Read This Properly

- `common` means both current and canonical produced a prediction for that row.
- `canonical_only` means canonical produced a prediction where current generated output was silent.
- `full` is common + canonical_only for canonical models. Current has no full row because it is the baseline CSV itself.
- `last_90_*` samples use the final 90 days of the canonical form table.
- `canonical_form_v1_market` adds a capped pre-match 1X2 win-probability adjustment for expected game state.
- `canonical_form_v1_market_nb` keeps the same lambda but converts O/U probabilities with a causal prior-data league negative-binomial dispersion estimate.
- `*_t12` rows are diagnostic trailing-12-month league-level normalization replays, not live policy candidates yet.
- Promotion should require full-window and last-90-day Brier/log-loss to match or beat current on the common sample, then odds/CLV checks.
