# Weekly Research Lane Report

- Generated: 2026-09-15T15:41:23Z
- Overall read: observe live sample

## Football Counts vNext

- Team Shots v4: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Team Shots v4 evidence: 1 signals, 1 settled, -1.00u, ROI -100.0%, true-close CLV -.
- Team Shots v4 warm-up tracking (not bets): 14 signals, 14 settled / 0 pending, +0.32u, ROI +2.3%.
- Team Shots v4 latest scan: EARLY_RULE_COMBINATION_BLOCKS_PRICED_LINES; 80 rows / 18 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'early_market_gap_cap': 32, 'edge_below_3pct': 75, 'price_older_than_3h': 8}.
- Corners v3: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Corners v3 evidence: 25 signals, 18 settled, -1.50u, ROI -8.3%, true-close CLV -1.6%.
- Corners v3 warm-up tracking (not bets): 36 signals, 36 settled / 0 pending, -2.50u, ROI -7.0%.
- Corners v3 latest scan: NO_EDGE_AFTER_UNLOCK; 40 rows / 8 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'edge_below_3pct': 26, 'price_older_than_3h': 40}.
- Corners v4 G0 research: FAIL; 6901/10889 enriched; latest holdout MAE delta -0.0074; real-market Brier delta +0.0090 on n=431; line gates 0/5 passed; failed 7.5, 8.5, 9.5, 10.5, 11.5, 12.5.
- Neither experiment changes live routing or stakes.
- API-Football count archive: 0 fixtures; latest -; last run 15/30 requests.
- Cross-provider agreement: 0/0 API fixtures matched; status no_overlap.
- Team Fouls: F1 COUNT_GATE_FAIL_MARKET_BLOCKED; F2 COUNT_GATE_FAIL_EXTERNAL_GATES_BLOCKED; M2 WAIT_OR_FAIL; market prices BLOCKED; signals disabled.
- Goalkeeper Saves v1: count PASS on 42,958 observations; discovery OVER_ONLY_GOALKEEPER_SAVE_PRICES_RETURNED (10 probe Over lines); latest capture NO_GOALKEEPER_SAVE_LINES (0 events selected / 0 rows / 0 with 1X2); prospective SIGNALS_COLLECTING with 57 priced lines, 3 eligible, 0 predicted-XI research rows, 40 signals and 37 settled; blockers {'goalkeeper_not_matched_to_lineup': 26, 'goalkeeper_team_unresolved': 26, 'history_lt_6': 15, 'missing_priced_edge': 47, 'missing_registered_feature': 21}; ROI +67.1%, CLV +1.0% n=9; promotion BLOCKED.
- New provider fields remain diagnostic-only until source definitions and coverage are accepted.

## Team Shots V3 EMA20 Research

- Model: `canonical_form_v3_ema20_nb`
- Allowed leagues: Bundesliga, EPL, La Liga, Ligue 1, Serie A
- Blocked leagues: -
- Canonical-only fixtures: blocked
- Last-90 segment gate: 1140 rows, current MAE 3.7320, V3 MAE 3.6413, improvement +2.4%
- Live CLV sample: 86 published, 86 settled
- Avg published-to-close CLV: +0.3%
- P/L sample: +10.93u
- Action: continue

## Corners V0 Research Partial

- Model: `canonical_form_v0`
- Allowed leagues: -
- Blocked leagues: Bundesliga, EPL, La Liga, Ligue 1, Serie A
- Canonical-only fixtures: blocked
- Live CLV sample: 48 published, 48 settled
- Avg published-to-close CLV: +0.4%
- P/L sample: -1.12u
- Action: keep partial; Bundesliga/La Liga remain blocked

## Blocked Corners Diagnostic

- Bundesliga: current MAE 2.587, V0 MAE 2.6594, delta +0.0724
- EPL: current MAE 2.6609, V0 MAE 2.5618, delta -0.0991
- La Liga: current MAE 2.7026, V0 MAE 2.7749, delta +0.0723
- Ligue 1: current MAE 2.6322, V0 MAE 2.4323, delta -0.1999
- Serie A: current MAE 2.7384, V0 MAE 2.6993, delta -0.0390

## Goalscorer V2 Research Gate

- Public Fair Odds Lab remains on the incumbent model.
- Live/backtest parity: PASS | max drift +0.005%.
- Held-out calibration (n=63,545): raw -> beta Brier 0.08554 -> 0.08528 (delta -0.00026); log loss 0.30413 -> 0.29885 (delta -0.00528); ECE +2.02% -> +0.81% (delta -1.20%).
- Mean probability: raw +8.38% | beta +10.43% | actual +10.30%.
- Beta calibration: 4/4 fold wins | probability gate FAIL | market gate UNAVAILABLE.
- Real-price CLV coverage: 0/85 (0.0%) | true closes 0.
- Settled ledger: 85/85 settled, 20W/62L, -15.22u, ROI -17.9%.
- Extreme-gap quarantine: 0/0 settled, +0.00u at 1u evaluation stakes, ROI -.
- Extreme-gap by league: no rows registered yet.
- Evidence freshness: FRESH (2026-09-13T13:28:31Z).
- Decision: KEEP_RESEARCH | blockers: fifth fold pending, probability gate fail, market ROI gate unavailable, no matched closing prices, no settled extreme-gap rows.

## Assist Value V1 Research Gate

- Lane: FROZEN_RESEARCH | decision KEEP_FROZEN_MARKET_EVIDENCE | reactivation ready NO.
- Historical gate: PASS on 44,739 test rows; calibrated Brier 0.05556.
- Settlement gate: FAIL | player-assist agreement 0.00%.
- Market gate: FAIL | 1305 matched player prices across 8 calendar days.
- Prospective ledger: 0/0 settled (target 100), +0.00u, ROI -.
- Evidence freshness: FRESH (2026-09-15T15:41:12Z).
- Automation budget: Friday-Sunday 07:10 UTC, August-May; <= 10 Odds-API calls/run and <= 30 calls/week; zero database reads/writes.
- No public output, staking, database writes or automatic promotion are authorised.

## Automation Budget

- Registry status: PASS; every scheduled GitHub workflow must be registered.
- Odds-API.io worst registered hour: 58 / 100 requests.
- Registered database envelope: 356 reads/week and 1841 writes/week maximum.

## Tennis ML Gap-Guard Quiet Audit

- This is not a live picks lane. Official ML value remains blocked when the model/market favourite gap is too wide.
- Guard trigger: model/market favourite gap > 10.0pp and model edge >= 10.0%.
- All guarded ML candidates: n=1927 753W/1174L pnl=+71.00u ROI=+3.7% avg edge=60.2% avg gap=14.3pp
- Clay high-confidence guarded: n=311 127W/184L pnl=+68.68u ROI=+22.1% avg edge=53.0% avg gap=13.5pp
- Clay high-confidence market dogs: n=231 73W/158L pnl=+60.11u ROI=+26.0% avg edge=64.5% avg gap=13.5pp
- Etcheverry/Fils-type candidates: n=78 19W/59L pnl=+33.65u ROI=+43.1% avg edge=80.4% avg gap=12.7pp
- Closest band to Etcheverry/Fils: n=7 2W/5L pnl=+0.38u ROI=+5.4% avg edge=42.9% avg gap=13.3pp
- Recent Etcheverry/Fils-type sample (2024-2026): n=42 10W/32L pnl=+1.93u ROI=+4.6% avg edge=83.3% avg gap=12.7pp
- Action: interesting, but keep shadow-only until live sample exists

### Etcheverry/Fils-Type Year Split

- 2022: n=13 2W/11L pnl=-2.57u ROI=-19.8% avg edge=68.1% avg gap=13.9pp
- 2023: n=23 7W/16L pnl=+34.29u ROI=+149.1% avg edge=82.2% avg gap=12.1pp
- 2024: n=16 4W/12L pnl=+4.31u ROI=+26.9% avg edge=84.9% avg gap=12.1pp
- 2025: n=26 6W/20L pnl=-2.38u ROI=-9.2% avg edge=82.3% avg gap=13.0pp
- 2026: n=0

## Tennis Props v3 Prospective Evidence

- Snapshot: 2026-07-29T11:37:47Z
- ATP aces gate: PASS on Clay, Hard
- Holdout MAE improvement: +3.33%
- Prospective sample: 0 settled, 1 pending, 0 events
- P/L: +0.00u; ROI +0.00%
- CLV: +0.00% across 0 rows
- Sellability: BLOCKED - settled 0/300; events 0/100; CLV coverage 0/300; mean CLV +0.00%/+1.00%
- Scope remains ATP aces on verified Hard/Clay only; shadow-only until every real-price gate passes.

## Venue Ace Factor v1

- Status: PROSPECTIVE_SHADOW / NOT_SELLABLE
- Venue coverage: 70/210 eligible.
- Prospective evidence: 432/600 settled across 217/150 events; P/L -112.20u; ROI -26.0%; CLV -0.30% n=185.
- Shadow only. This block never changes routing, stakes or public recommendations.

## Tennis Aces/DF Prospective Decision

Tennis Aces/DF Weekly Decision Report
Generated UTC: 2026-09-15T09:21:04Z
Status: COLLECTING_EVIDENCE (never auto-promoted)

Sample: 104/117 settled; 0 pending (0 due, 0 future, 0 unknown); 13 void
Record: 53W/51L/0P
P/L: +2.19u | ROI: +2.1%
CLV: +3.84% mean; 33.3% positive; n=36
Calibration: Brier 0.236471; predicted 58.6%; actual 51.0%; gap 7.7pp; n=104
Feed: TWO_WAY_PRICES_MISSING; matched 274/403; two-way 0; over-only 334; public bettable 0

By market:
- aces: 37/40 settled, -1.65u, ROI -4.5%
- double_faults: 67/77 settled, +3.84u, ROI +5.7%

Blockers: settled sample 104/300; Slam coverage 1/2; CLV sample 36/300; one-sided price feed (0 two-way rows); pipeline health TWO_WAY_PRICES_MISSING
Promotion gate: Human review only after 300 settled lines across at least two Slams, non-negative ROI, mean CLV >= +1%, positive CLV >= 55%, at least 100 calibrated win/loss rows with Brier <= 0.25 and absolute calibration gap <= 5pp, plus approved price integrity and a healthy pipeline.

Service Breaks v1 [INTERNAL]: OUTCOME_PASS | player ATP/WTA PASS | match ATP/WTA PASS | real price evidence NO_CAPTURE_OR_LEDGER_EVIDENCE | prospective 0 | strict 0 rows/0 settled/+0.00u/ROI - | Bet365-only 0 rows/0 settled/+0.00u/ROI - | count calibration 0/0 settled | NOT SELLABLE

## Tennis Props Model vs Bet365

- Status: EVIDENCE_BUILDING
- Clean main lines: 28 observed, 26 settled, 0 pending.
- Count MAE: model 2.739; observed Bet365-implied mean 2.673.
- Brier: model 0.1998; Bet365 0.1995; delta -0.0004 (positive favours the model).
- No automatic parameter change; 100 settled clean lines triggers a registered challenger review, not promotion.

## Plain-English Read

- Team-shots V3 is not proven profitable live yet; it is the first broad research candidate that passed the backtest segment gates.
- Corners V0 is narrower and deliberately blocked in two leagues. That is a discipline feature, not a failure.
- Goalscorer V2 fixes live/backtest mechanics, but it is not a betting edge until captured prices validate it.
- Assist V1 passed count calibration and settlement integrity, but remains frozen until 90-day market calibration and 100 prospective settled signals pass.
- Tennis ML gap-guard remains a safety brake. The backtest is not stable enough to unblock those big market-disagreement ML dogs.
- Tennis props v3 remains prospective shadow evidence; historical accuracy alone does not authorise tips.
- The next real evidence is CLV and settled live sample. Until 50 settled picks, do not overreact to wins/losses.


Astra models SHADOW ONLY | Astra Aces: 57/83 settled, 24 pending, 28/200 fixtures | Astra DF: 56/80 settled, 22 pending, 28/200 fixtures | Astra Aces: baseline ROI -10.8% (33 contracts), Astra ROI -9.9% (34 contracts) | Astra DF: baseline ROI +13.2% (37 contracts), Astra ROI +24.2% (37 contracts) | data FRESH; 8 weeks/4 tournaments minimum, manual review before promotion.

MODEL REVIEW WATCHLIST
Astra Volume [RESEARCH]: historical replay ROI +7.25%, n=69 | prospective capture NOT_CONNECTED | review weekly; historical bets are not forward evidence.
Opponent Shots [SHADOW]: forward 3W/3L, ROI -7.6%, pending 1 | COLLECTING_FIXED_POLICY | scan 2026-09-15T15:37:54Z