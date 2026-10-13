# Weekly Research Lane Report

- Generated: 2026-10-13T18:28:25Z
- Overall read: observe live sample

## Football Counts vNext

- Team Shots v4: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Team Shots v4 evidence: 3 signals, 3 settled, -3.00u, ROI -100.0%, true-close CLV +0.0%.
- Team Shots v4 warm-up tracking (not bets): 14 signals, 14 settled / 0 pending, +0.32u, ROI +2.3%.
- Team Shots v4 latest scan: NO_EDGE_AFTER_UNLOCK; 24 rows / 6 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'edge_below_3pct': 24}.
- Corners v3: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Corners v3 evidence: 80 signals, 62 settled, -4.86u, ROI -7.8%, true-close CLV +0.4%.
- Corners v3 warm-up tracking (not bets): 36 signals, 36 settled / 0 pending, -2.50u, ROI -7.0%.
- Corners v3 latest scan: ELIGIBLE_CANDIDATES_PRESENT; 124 rows / 25 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'edge_below_3pct': 84, 'price_older_than_3h': 2}.
- Corners v4 G0 research: FAIL; 6901/10889 enriched; latest holdout MAE delta -0.0074; real-market Brier delta +0.0090 on n=431; line gates 0/5 passed; failed 7.5, 8.5, 9.5, 10.5, 11.5, 12.5.
- Neither experiment changes live routing or stakes.
- API-Football count archive: 0 fixtures; latest -; last run 15/30 requests.
- Cross-provider agreement: 0/0 API fixtures matched; status no_overlap.
- Team Fouls: F1 COUNT_GATE_FAIL_MARKET_BLOCKED; F2 COUNT_GATE_FAIL_EXTERNAL_GATES_BLOCKED; M2 WAIT_OR_FAIL; market prices BLOCKED; signals disabled.
- Goalkeeper Saves v1: count PASS on 42,958 observations; discovery OVER_ONLY_GOALKEEPER_SAVE_PRICES_RETURNED (10 probe Over lines); latest capture NO_GOALKEEPER_SAVE_LINES (0 events selected / 0 rows / 0 with 1X2); prospective SIGNALS_COLLECTING with 0 priced lines, 0 eligible, 0 predicted-XI research rows, 63 signals and 60 settled; blockers {}; ROI +53.2%, CLV +2.7% n=16; promotion BLOCKED.
- New provider fields remain diagnostic-only until source definitions and coverage are accepted.

## Team Shots V3 EMA20 Research

- Model: `canonical_form_v3_ema20_nb`
- Allowed leagues: Bundesliga, EPL, La Liga, Ligue 1, Serie A
- Blocked leagues: -
- Canonical-only fixtures: blocked
- Last-90 segment gate: 1140 rows, current MAE 3.7320, V3 MAE 3.6413, improvement +2.4%
- Live CLV sample: 76 published, 76 settled
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
- Real-price CLV coverage: 0/88 (0.0%) | true closes 0.
- Settled ledger: 87/88 settled, 21W/63L, -14.72u, ROI -16.9%.
- Extreme-gap quarantine: 0/0 settled, +0.00u at 1u evaluation stakes, ROI -.
- Extreme-gap by league: no rows registered yet.
- Evidence freshness: FRESH (2026-10-11T15:04:37Z).
- Decision: KEEP_RESEARCH | blockers: fifth fold pending, probability gate fail, market ROI gate unavailable, no matched closing prices, no settled extreme-gap rows.

## Assist Value V1 Research Gate

- Lane: FROZEN_RESEARCH | decision KEEP_FROZEN_MARKET_EVIDENCE | reactivation ready NO.
- Historical gate: PASS on 44,739 test rows; calibrated Brier 0.05556.
- Settlement gate: FAIL | player-assist agreement 0.00%.
- Market gate: FAIL | 1305 matched player prices across 8 calendar days.
- Prospective ledger: 0/0 settled (target 100), +0.00u, ROI -.
- Evidence freshness: FRESH (2026-10-13T18:28:14Z).
- Automation budget: Friday-Sunday 07:10 UTC, August-May; <= 10 Odds-API calls/run and <= 30 calls/week; zero database reads/writes.
- No public output, staking, database writes or automatic promotion are authorised.

## Automation Budget

- Registry status: PASS; every scheduled GitHub workflow must be registered.
- Odds-API.io worst registered hour: 62 / 100 requests.
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

- Snapshot: 2026-10-13T09:20:08Z
- ATP aces gate: PASS on Clay, Hard
- Holdout MAE improvement: +3.33%
- Prospective sample: 50 settled, 0 pending, 49 events
- P/L: -7.44u; ROI -14.88%
- CLV: +4.43% across 25 rows
- Sellability: BLOCKED - settled 50/300; events 49/100; CLV coverage 25/300; ROI -14.88%/+0.00%
- Scope remains ATP aces on verified Hard/Clay only; shadow-only until every real-price gate passes.

## Venue Ace Factor v1

- Status: PROSPECTIVE_SHADOW / NOT_SELLABLE
- Venue coverage: 70/210 eligible.
- Prospective evidence: 582/600 settled across 296/150 events; P/L -170.56u; ROI -29.3%; CLV -0.07% n=286.
- Shadow only. This block never changes routing, stakes or public recommendations.

## Tennis Aces/DF Prospective Decision

Tennis Aces/DF Weekly Decision Report
Generated UTC: 2026-10-13T09:21:30Z
Status: COLLECTING_EVIDENCE (never auto-promoted)

Sample: 183/214 settled; 11 pending (2 due, 9 future, 0 unknown); 20 void
Record: 85W/98L/0P
P/L: -16.39u | ROI: -9.0%
CLV: +2.65% mean; 26.7% positive; n=105
Calibration: Brier 0.239583; predicted 59.0%; actual 46.5%; gap 12.5pp; n=183
Feed: MILESTONE_SHADOW_READY; matched 332/365; two-way 0; over-only 365; public bettable 0

By market:
- aces: 52/62 settled, -12.29u, ROI -23.6%
- double_faults: 131/152 settled, -4.10u, ROI -3.1%

Blockers: settled sample 183/300; Slam coverage 1/2; CLV sample 105/300; one-sided price feed (0 two-way rows)
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


Astra models SHADOW ONLY | Astra Aces [oncourt-current-history-20261007-v1]: 32 settled fixtures; 317 pending quotes; baseline ROI -72.5% (25 selected lines), Astra ROI -71.4% (24 selected lines) | Astra DF [oncourt-current-history-20261007-v1]: 31 settled fixtures; 407 pending quotes; baseline ROI -9.9% (55 selected lines), Astra ROI -24.0% (84 selected lines) | data FRESH; multiple lines per match are correlated. Review floors: 200 fixtures, 8 weeks, 4 tournaments within each input version. Manual review before promotion.


Astra Volume PAPER ONLY: 0W/2L, ROI -100.00%, 1 pending (0 overdue). Paired fixtures settled 38; review at 50 and 100. Capture WAITING_FOR_FRESH_ELIGIBLE_FORECAST at 2026-10-13T09:11:17.627224+00:00. No verified closing-price coverage.

MODEL REVIEW WATCHLIST
Calibrated Shots [ZERO-STAKE]: forward ROI +0.8%, settled 9, pending 0 | COLLECTING
EMA20 v3 / v4 / Opponent paired comparison [RESEARCH]: historical replay ROI unknown, n=? | prospective capture DAILY_EXISTING_FOOTBALL_COUNTS_WORKFLOW | review weekly; historical bets are not forward evidence.
Astra Volume [RESEARCH]: historical replay ROI +7.25%, n=69 | prospective capture CONNECTED_FIRST_CAPTURE_VERIFIED | review weekly; historical bets are not forward evidence.
Opponent Shots [SHADOW]: forward 23W/33L, ROI -24.4%, pending 0 | COLLECTING_FIXED_POLICY | scan 2026-10-13T18:24:17Z
Astrissimo [RESEARCH]: historical replay ROI unknown, n=? | prospective capture UNKNOWN | review weekly; historical bets are not forward evidence.