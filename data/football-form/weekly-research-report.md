# Weekly Research Lane Report

- Generated: 2026-10-27T16:50:18Z
- Overall read: observe live sample

## Football Counts vNext

- Team Shots v4: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Team Shots v4 evidence: 7 signals, 7 settled, -3.17u, ROI -45.2%, true-close CLV +0.9%.
- Team Shots v4 warm-up tracking (not bets): 14 signals, 14 settled / 0 pending, +0.32u, ROI +2.3%.
- Team Shots v4 latest scan: NO_EDGE_AFTER_UNLOCK; 116 rows / 8 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'edge_below_3pct': 116, 'price_older_than_3h': 24}.
- Corners v3: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Corners v3 evidence: 126 signals, 107 settled, -4.91u, ROI -4.6%, true-close CLV +1.0%.
- Corners v3 warm-up tracking (not bets): 36 signals, 36 settled / 0 pending, -2.50u, ROI -7.0%.
- Corners v3 latest scan: ELIGIBLE_CANDIDATES_PRESENT; 154 rows / 31 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'edge_below_3pct': 116, 'price_older_than_3h': 6}.
- Corners v4 G0 research: FAIL; 6901/10889 enriched; latest holdout MAE delta -0.0074; real-market Brier delta +0.0090 on n=431; line gates 0/5 passed; failed 7.5, 8.5, 9.5, 10.5, 11.5, 12.5.
- Neither experiment changes live routing or stakes.
- API-Football count archive: 0 fixtures; latest -; last run 15/30 requests.
- Cross-provider agreement: 0/0 API fixtures matched; status no_overlap.
- Team Fouls: F1 COUNT_GATE_FAIL_MARKET_BLOCKED; F2 COUNT_GATE_FAIL_EXTERNAL_GATES_BLOCKED; M2 WAIT_OR_FAIL; market prices BLOCKED; signals disabled.
- Goalkeeper Saves v1: count PASS on 42,958 observations; discovery OVER_ONLY_GOALKEEPER_SAVE_PRICES_RETURNED (10 probe Over lines); latest capture CAPTURED (3 events selected / 14 rows / 3 with 1X2); prospective SIGNALS_COLLECTING with 33 priced lines, 2 eligible, 0 predicted-XI research rows, 92 signals and 83 settled; blockers {'missing_priced_edge': 4, 'missing_registered_feature': 4}; ROI +36.3%, CLV +5.3% n=30; promotion BLOCKED.
Calibrated Shots [ZERO-STAKE, retained prospective cohorts]: hypothetical ROI +11.0%, settled 23, pending 0 | COLLECTING | 90 paired fixtures | version paired-market-offset-20261019-club-alias-v3
Opponent Shots [SHADOW]: forward 43W/51L, ROI -13.9%, pending 2 | COLLECTING_FIXED_POLICY | scan 2026-10-27T16:45:45Z
GK paper comparison | TRACKING | Keeper Watch: 1W/3L, -0.50u, ROI -25.0%, pending 0, review 0, overdue 0 | paired current: 10W/10L, +1.27u, ROI +12.7%, pending 0, review 0, overdue 0 | paired fixtures 77; review 50 | no automatic promotion
- New provider fields remain diagnostic-only until source definitions and coverage are accepted.

## Team Shots V3 EMA20 Research

- Model: `canonical_form_v3_ema20_nb`
- Allowed leagues: Bundesliga, EPL, La Liga, Ligue 1, Serie A
- Blocked leagues: -
- Canonical-only fixtures: blocked
- Last-90 segment gate: 1140 rows, current MAE 3.7320, V3 MAE 3.6413, improvement +2.4%
- Live CLV sample: 79 published, 79 settled
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
- Real-price CLV coverage: 0/99 (0.0%) | true closes 0.
- Settled ledger: 94/99 settled, 21W/70L, -21.73u, ROI -23.1%.
- Extreme-gap quarantine: 0/0 settled, +0.00u at 1u evaluation stakes, ROI -.
- Extreme-gap by league: no rows registered yet.
- Evidence freshness: FRESH (2026-10-26T15:29:15Z).
- Decision: KEEP_RESEARCH | blockers: fifth fold pending, probability gate fail, market ROI gate unavailable, no matched closing prices, no settled extreme-gap rows.

## Assist Value V1 Research Gate

- Lane: FROZEN_RESEARCH | decision KEEP_FROZEN_MARKET_EVIDENCE | reactivation ready NO.
- Historical gate: PASS on 44,739 test rows; calibrated Brier 0.05556.
- Settlement gate: FAIL | player-assist agreement 0.00%.
- Market gate: FAIL | 1305 matched player prices across 8 calendar days.
- Prospective ledger: 0/0 settled (target 100), +0.00u, ROI -.
- Evidence freshness: FRESH (2026-10-27T16:50:05Z).
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

- Snapshot: 2026-10-27T10:27:01Z
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
Generated UTC: 2026-10-27T13:08:03Z
Status: COLLECTING_EVIDENCE (never auto-promoted)

Sample: 220/261 settled; 16 pending (11 due, 5 future, 0 unknown); 25 void
Record: 103W/117L/0P
P/L: -14.66u | ROI: -6.7%
CLV: +2.11% mean; 28.1% positive; n=139
Calibration: Brier 0.244128; predicted 58.9%; actual 46.8%; gap 12.1pp; n=220
Feed: SHADOW_EVIDENCE_READY; matched 28/28; two-way 28; over-only 0; public bettable 0

By market:
- aces: 64/73 settled, -4.05u, ROI -6.3%
- double_faults: 156/188 settled, -10.61u, ROI -6.8%

Blockers: settled sample 220/300; Slam coverage 1/2; CLV sample 139/300
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
- Assist V1: count gate PASS; settlement gate FAIL. Remains frozen until all registered evidence gates pass.
- Tennis ML gap-guard remains a safety brake. The backtest is not stable enough to unblock those big market-disagreement ML dogs.
- Tennis props v3 remains prospective shadow evidence; historical accuracy alone does not authorise tips.
- The next real evidence is CLV and settled live sample. Until 50 settled picks, do not overreact to wins/losses.


Ace Compass v1 [PAPER ONLY]
0W/0L | +0.00u on 0u | No settled bets yet | 0 pending, 0 void, 0 overdue.
Prediction bias awaits completed matches. Capture: NO_NEW_ELIGIBLE_QUOTES. Historical +10.79%/19 bets stays separate.

Astra models FULL-BOARD PAPER, including lines blocked by normal signal filters; 1u per selected line | Astra Aces [oncourt-current-history-20261007-v1]: 135 settled fixtures; 64 unresolved quote records (0 older than 48h); baseline ROI -36.6% (78 selected lines), Astra ROI -38.0% (70 selected lines), Astra odds >=5.00: 2W/47L, -27.00u | Astra DF [oncourt-current-history-20261007-v1]: 151 settled fixtures; 97 unresolved quote records (0 older than 48h); baseline ROI -25.5% (172 selected lines), Astra ROI -31.3% (243 selected lines), Astra odds >=5.00: 6W/90L, -39.50u | data FRESH; multiple lines per match are correlated. Review floors: 200 fixtures, 8 weeks, 4 tournaments within each input version. Manual review before promotion.


Astra Volume PAPER ONLY: 2W/2L, ROI +18.40%, 0 pending (0 overdue). Paired fixtures settled 58; review at 50 and 100. Capture WAITING_FOR_FRESH_ELIGIBLE_FORECAST at 2026-10-27T10:16:30.780642+00:00. No verified closing-price coverage.
Hardcourt Scout | Challenger outdoor hard | PAPER ONLY
0W / 0L | ROI awaits first settled selection | +0.00u on 0u
1 pending (0 overdue), 0 void, 0 quarantined. 1u hypothetical stakes; zero real stake. Review at 50 and 100 settled selections. Capture WAITING_FOR_ELIGIBLE_FIXTURES at 2026-10-27T10:27:41.712339+00:00. Report 2026-10-27T10:27:48.503231+00:00. Historical +22.65% replay excluded; closing prices unverified.

MODEL REVIEW WATCHLIST
Calibrated Shots [ZERO-STAKE, retained prospective cohorts]: hypothetical ROI +11.0%, settled 23, pending 0 | COLLECTING | 90 paired fixtures | version paired-market-offset-20261019-club-alias-v3
EMA20 v3 / v4 / Opponent paired comparison [RESEARCH]: historical replay ROI unknown, n=? | prospective capture DAILY_EXISTING_FOOTBALL_COUNTS_WORKFLOW | review weekly; historical bets are not forward evidence.
Astra Volume [RESEARCH]: historical replay ROI +7.25%, n=69 | prospective capture CONNECTED_FIRST_CAPTURE_VERIFIED | review weekly; historical bets are not forward evidence.
Opponent Shots [SHADOW]: forward 43W/51L, ROI -13.9%, pending 2 | COLLECTING_FIXED_POLICY | scan 2026-10-27T16:45:45Z
Astrissimo [PAPER ONLY]: -100.00% ROI; capture WAITING_FOR_FRESH_ELIGIBLE_FORECAST