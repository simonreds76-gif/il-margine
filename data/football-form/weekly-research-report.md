# Weekly Research Lane Report

- Generated: 2026-04-26T00:28:27Z
- Overall read: observe live sample

## Team Shots V3 EMA20 Research

- Model: `canonical_form_v3_ema20_nb`
- Allowed leagues: Bundesliga, EPL, La Liga, Ligue 1, Serie A
- Blocked leagues: -
- Canonical-only fixtures: blocked
- Last-90 segment gate: 1140 rows, current MAE 3.7320, V3 MAE 3.6413, improvement +2.4%
- Live CLV sample: 12 published, 0 settled
- Avg published-to-close CLV: -
- P/L sample: +0.00u
- Action: watch passively; not enough live sample until 50 settled picks

## Corners V0 Research Partial

- Model: `canonical_form_v0`
- Allowed leagues: EPL, Ligue 1, Serie A
- Blocked leagues: Bundesliga, La Liga
- Canonical-only fixtures: blocked
- Live CLV sample: 7 published, 0 settled
- Avg published-to-close CLV: -
- P/L sample: +0.00u
- Action: keep partial; Bundesliga/La Liga remain blocked

## Blocked Corners Diagnostic

- Bundesliga: current MAE 2.587, V0 MAE 2.6594, delta +0.0724
- La Liga: current MAE 2.7026, V0 MAE 2.7749, delta +0.0723

## Plain-English Read

- Team-shots V3 is not proven profitable live yet; it is the first broad research candidate that passed the backtest segment gates.
- Corners V0 is narrower and deliberately blocked in two leagues. That is a discipline feature, not a failure.
- The next real evidence is CLV and settled live sample. Until 50 settled picks, do not overreact to wins/losses.
