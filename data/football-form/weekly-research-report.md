# Weekly Research Lane Report

- Generated: 2026-11-03T19:11:10Z
- Overall read: observe live sample

## Football Counts vNext

- Team Shots v4: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Team Shots v4 evidence: 15 signals, 15 settled, -7.50u, ROI -50.0%, true-close CLV +0.9%.
- Team Shots v4 warm-up tracking (not bets): 14 signals, 14 settled / 0 pending, +0.32u, ROI +2.3%.
- Team Shots v4 latest scan: EXPECTED_EMPTY_CAPTURE_WINDOW; 0 rows / 0 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers -.
- Corners v3: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Corners v3 evidence: 173 signals, 150 settled, -13.90u, ROI -9.3%, true-close CLV +0.9%.
- Corners v3 warm-up tracking (not bets): 36 signals, 36 settled / 0 pending, -2.50u, ROI -7.0%.
- Corners v3 latest scan: NO_EDGE_AFTER_UNLOCK; 506 rows / 34 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'edge_below_3pct': 413, 'price_not_fresh_10m': 506, 'price_older_than_3h': 56}.
- Corners v4 G0 research: FAIL; 6901/10889 enriched; latest holdout MAE delta -0.0074; real-market Brier delta +0.0090 on n=431; line gates 0/5 passed; failed 7.5, 8.5, 9.5, 10.5, 11.5, 12.5.
- Neither experiment changes live routing or stakes.
- API-Football count archive: 0 fixtures; latest -; last run 15/30 requests.
- Cross-provider agreement: 0/0 API fixtures matched; status no_overlap.
- Team Fouls: F1 COUNT_GATE_FAIL_MARKET_BLOCKED; F2 COUNT_GATE_FAIL_EXTERNAL_GATES_BLOCKED; M2 WAIT_OR_FAIL; market prices BLOCKED; signals disabled.
- Goalkeeper Saves v1: count PASS on 42,958 observations; discovery OVER_ONLY_GOALKEEPER_SAVE_PRICES_RETURNED (10 probe Over lines); latest capture NO_GOALKEEPER_SAVE_LINES (0 events selected / 0 rows / 0 with 1X2); prospective SIGNALS_COLLECTING with 0 priced lines, 0 eligible, 0 predicted-XI research rows, 104 signals and 96 settled; blockers {}; ROI +25.3%, CLV +5.0% n=34; promotion BLOCKED.
Calibrated Shots [ZERO-STAKE, retained prospective cohorts]: hypothetical ROI +18.8%, settled 28, pending 0 | COLLECTING | 127 paired fixtures | version paired-market-offset-20261028-identity-v4
Opponent Shots [SHADOW]: forward 50W/57L, ROI -12.1%, pending 0 | COLLECTING_FIXED_POLICY | scan 2026-11-03T19:06:33Z
GK paper comparison | TRACKING | Keeper Watch: 1W/3L, -0.50u, ROI -25.0%, pending 0, review 2, overdue 2 | paired current: 12W/16L, -0.94u, ROI -6.7%, pending 0, review 4, overdue 4 | paired fixtures 122; review 100 | no automatic promotion
- New provider fields remain diagnostic-only until source definitions and coverage are accepted.

## Team Shots V3 EMA20 Research

- Model: `canonical_form_v3_ema20_nb`
- Allowed leagues: Bundesliga, EPL, La Liga, Ligue 1, Serie A
- Blocked leagues: -
- Canonical-only fixtures: blocked
- Last-90 segment gate: 1140 rows, current MAE 3.7320, V3 MAE 3.6413, improvement +2.4%
- Live CLV sample: 72 published, 72 settled
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
- Real-price CLV coverage: 0/103 (0.0%) | true closes 0.
- Settled ledger: 98/103 settled, 23W/72L, -17.98u, ROI -18.3%.
- Extreme-gap quarantine: 0/0 settled, +0.00u at 1u evaluation stakes, ROI -.
- Extreme-gap by league: no rows registered yet.
- Evidence freshness: FRESH (2026-11-02T18:50:29Z).
- Decision: KEEP_RESEARCH | blockers: fifth fold pending, probability gate fail, market ROI gate unavailable, no matched closing prices, no settled extreme-gap rows.

## Assist Value V1 Research Gate

- Lane: FROZEN_RESEARCH | decision KEEP_FROZEN_MARKET_EVIDENCE | reactivation ready NO.
- Historical gate: PASS on 44,739 test rows; calibrated Brier 0.05556.
- Settlement gate: FAIL | player-assist agreement 0.00%.
- Market gate: FAIL | 1305 matched player prices across 8 calendar days.
- Prospective ledger: 0/0 settled (target 100), +0.00u, ROI -.
- Evidence freshness: FRESH (2026-11-03T19:10:59Z).
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

- Snapshot: 2026-11-03T10:28:38Z
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
Generated UTC: 2026-11-03T16:23:29Z
Status: COLLECTING_EVIDENCE (never auto-promoted)

Sample: 250/284 settled; 6 pending (3 due, 3 future, 0 unknown); 28 void
Record: 122W/128L/0P
P/L: -6.63u | ROI: -2.6%
CLV: +1.71% mean; 28.4% positive; n=148
Calibration: Brier 0.245666; predicted 59.1%; actual 48.8%; gap 10.3pp; n=250
Feed: SHADOW_EVIDENCE_READY; matched 57/73; two-way 12; over-only 61; public bettable 0

By market:
- aces: 74/84 settled, -4.35u, ROI -5.9%
- double_faults: 176/200 settled, -2.28u, ROI -1.3%

Blockers: settled sample 250/300; Slam coverage 1/2; CLV sample 148/300
Promotion gate: Human review only after 300 settled lines across at least two Slams, non-negative ROI, mean CLV >= +1%, positive CLV >= 55%, at least 100 calibrated win/loss rows with Brier <= 0.25 and absolute calibration gap <= 5pp, plus approved price integrity and a healthy pipeline.

Service Breaks v1 [INTERNAL]: OUTCOME_PASS | player ATP/WTA PASS | match ATP/WTA PASS | real price evidence NO_CAPTURE_OR_LEDGER_EVIDENCE | prospective 0 | strict 0 rows/0 settled/+0.00u/ROI - | Bet365-only 0 rows/0 settled/+0.00u/ROI - | count calibration 0/0 settled | NOT SELLABLE

## Tennis Props Model vs Bet365

- Status: EVIDENCE_BUILDING
- Clean main lines: 44 observed, 38 settled, 3 pending.
- Count MAE: model 2.494; observed Bet365-implied mean 2.571.
- Brier: model 0.2127; Bet365 0.2189; delta +0.0062 (positive favours the model).
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
4W/3L | +3.33u on 7u | ROI +47.62% | 5 pending, 0 void, 0 overdue.
Predicted ace total bias -13.3% across 26 player matches (negative = underprediction). Capture: CAPTURED. Historical +10.79%/19 bets stays separate.

Indoor Scout | indoor Masters, including qualifying | PAPER ONLY
0W/1L | -1.00u on 1u | -100.00% ROI
2 pending (0 overdue), 0 void, 0 quarantined. 44 captured fixtures; Brier 0.2232, log loss 0.6382. Core Strict gates; optional overlays not simulated. 1u paper, zero real stake. Capture WAITING_FOR_FRESH_PRICED_FIXTURES at 2026-11-03T10:30:09.060006+00:00. 

ELO REBUILD | ATP paper comparison; live unchanged
History through 2026-11-01 | 27 ATP pairs | 19 pending fixtures.
baseline: 0W/0L, 0u, +0.00u; ROI not available; 0 pending bets.
candidate: 0W/0L, 0u, +0.00u; ROI not available; 0 pending bets.
Review at 300 settled priced ATP fixtures; no automatic promotion.
PUBLISHED ELO | same formulas; 31 verified pairs; 32 results. No live change.
ATP current_paired: gates 0W/0L, +0.00u/0u, ROI unavailable; 0 pending. EV5 diagnostic 11 settled/ROI +3.71%. All paired fixtures: LL 0.6363/Brier 0.2236.
ATP published_paired: gates 0W/0L, +0.00u/0u, ROI unavailable; 0 pending. EV5 diagnostic 12 settled/ROI -12.17%. All paired fixtures: LL 0.6603/Brier 0.2344.
Challenger current_paired: gates 0W/0L, +0.00u/0u, ROI unavailable; 0 pending. EV5 diagnostic 0 settled/ROI unavailable. paired accuracy awaiting results.
Challenger published_paired: gates 0W/0L, +0.00u/0u, ROI unavailable; 0 pending. EV5 diagnostic 0 settled/ROI unavailable. paired accuracy awaiting results.
Challenger published-rating coverage is limited; its independent review may take months.

Sisal 50/50 [PAPER ONLY; 1u hypothetical / 0 real stake]
3W/3L | -0.25u / 6u | ROI -4.17% | 0 pending, 0 void, 0 overdue; 0 retirement-determined bets.
18 frozen paired prices; 18 completed player contracts / 9 independent fixtures.
Ace-count bias -0.05 per player-match (negative = underprediction).
Model: Brier 0.2675; log loss 0.7340 on identical completed contracts.
Market: Brier 0.2499; log loss 0.6931 on identical completed contracts.
50/50: Brier 0.2521; log loss 0.6978 on identical completed contracts.
BO3: 6 settled, -0.25u, ROI -4.17%.
Capture: NO_NEW_ELIGIBLE_QUOTES. No individual alerts; live models unchanged. Historical replay excluded.
Event correction comparison: 8 identical forward contracts; 0 without earlier main-draw evidence.
Original 50/50: 1W/0L | +0.85u/1u | ROI +85.00% | 0 pending, 0 void, 0 overdue.
Event-adjusted 50/50: 2W/0L | +1.80u/2u | ROI +90.00% | 0 pending, 0 void, 0 overdue.
Comparison uses the same prices and fixed rules. Earlier full record remains separate; no new alerts or live changes.
Comparison exclusions: incomplete_event_evidence: 10
Ledger checkpoint: e6ee40b517551a41

BREAK POINT C | 7 settled fixtures | 0W/1L | 1u paper | -1.00u | ROI -100.00% | 1 pending bets | LL C 0.7933 / market 0.6822. No alerts; completed-result research, bookmaker grading unverified.

Match Shape | ATP BO3 incl. qualifying/indoor | PAPER ONLY | no alerts
13 fixtures / 26 contracts; 7 independently settled fixtures.
Total games Current: 0W/0L/0P; +0.00u/0u; ROI pending; 1 pending (0 overdue), 0 excluded, 0 quarantined. Brier 0.2692, log loss 0.7318.
Total games Frozen T1: 0W/1L/0P; -1.00u/1u; -100.00% ROI; 2 pending (0 overdue), 0 excluded, 0 quarantined. Brier 0.2599, log loss 0.7135.
Handicaps Current: 3W/3L/0P; +0.64u/6u; +10.67% ROI; 2 pending (0 overdue), 0 excluded, 0 quarantined. Brier 0.2396, log loss 0.6720.
Handicaps Frozen T1: 3W/2L/0P; +1.64u/5u; +32.80% ROI; 3 pending (0 overdue), 0 excluded, 0 quarantined. Brier 0.2375, log loss 0.6670.
Capture INPUT_REFRESH_REQUIRED; 1u paper, zero real stake. Reviews at 50/100 settled fixtures. ML unchanged; raw/C0 controls in Monitor.

Most DF | PAPER OBSERVATION ONLY | 0W/5L | -5.00u on 5u | ROI -100.00% | 0 pending (0 overdue). 6/150 independent settled fixtures. Capture: NO_NEW_ELIGIBLE_QUOTES. No betting alerts; unvalidated independent-count benchmark.

Astra models FULL-BOARD PAPER, including lines blocked by normal signal filters; 1u per selected line | Astra Aces [oncourt-current-history-20261007-v1]: 147 settled fixtures; 0 unresolved quote records (0 older than 48h); baseline ROI -37.4% (79 selected lines), Astra ROI -38.9% (71 selected lines), Astra odds >=5.00: 2W/48L, -28.00u | Astra DF [oncourt-current-history-20261007-v1]: 160 settled fixtures; 10 unresolved quote records (10 older than 48h); baseline ROI -16.6% (184 selected lines), Astra ROI -23.2% (259 selected lines), Astra odds >=5.00: 7W/93L, -30.50u | Astra Aces [oncourt-current-history-20261030-v2]: 4 settled fixtures; 97 unresolved quote records (0 older than 48h); baseline ROI -100.0% (2 selected lines), Astra ROI -100.0% (2 selected lines), Astra odds >=5.00: 0W/2L, -2.00u | Astra DF [oncourt-current-history-20261030-v2]: 1 settled fixtures; 23 unresolved quote records (0 older than 48h); baseline ROI no settled selections (0 selected lines), Astra ROI no settled selections (0 selected lines) | data FRESH; multiple lines per match are correlated. Review floors: 200 fixtures, 8 weeks, 4 tournaments within each input version. Manual review before promotion.


Astra Volume PAPER ONLY: 2W/2L, ROI +18.40%, 0 pending (0 overdue). Paired fixtures settled 58; review at 50 and 100. Capture WAITING_FOR_FRESH_ELIGIBLE_FORECAST at 2026-11-03T10:17:10.194627+00:00. No verified closing-price coverage.
Hardcourt Scout | Challenger outdoor hard | PAPER ONLY
0W / 2L | ROI -100.00% | -2.00u on 2u
0 pending (0 overdue), 1 void, 0 quarantined. 1u hypothetical stakes; zero real stake. Review at 50 and 100 settled selections. Capture WAITING_FOR_ELIGIBLE_FIXTURES at 2026-11-03T10:29:47.425068+00:00. Report 2026-11-03T10:29:58.712801+00:00. Historical +22.65% replay excluded; closing prices unverified.
Fable correction alongside Scout | same forward cohort | PAPER ONLY
Scout baseline: 0W/1L, -1.00u/1u, ROI -100.00%; 0 pending, 0 void, 0 quarantined. Brier 0.2835; log loss 0.7659; predicted 43.1% / observed 58.3%.
Fable frozen: 0W/1L, -1.00u/1u, ROI -100.00%; 0 pending, 0 void, 0 quarantined. Brier 0.2495; log loss 0.6858; predicted 41.5% / observed 58.3%.
12 paired settled fixtures; 4 history fallbacks, 0 unavailable. Since 2026-10-29T19:45:47.701147+00:00. Capture CAPTURED. Same 50/100 fixture review; no automatic promotion.

MODEL REVIEW WATCHLIST
Calibrated Shots [ZERO-STAKE, retained prospective cohorts]: hypothetical ROI +18.8%, settled 28, pending 0 | COLLECTING | 127 paired fixtures | version paired-market-offset-20261028-identity-v4
EMA20 v3 / v4 / Opponent paired comparison [RESEARCH]: historical replay ROI unknown, n=? | prospective capture DAILY_EXISTING_FOOTBALL_COUNTS_WORKFLOW | review weekly; historical bets are not forward evidence.
Astra Volume [RESEARCH]: historical replay ROI +7.25%, n=69 | prospective capture CONNECTED_FIRST_CAPTURE_VERIFIED | review weekly; historical bets are not forward evidence.
Opponent Shots [SHADOW]: forward 50W/57L, ROI -12.1%, pending 0 | COLLECTING_FIXED_POLICY | scan 2026-11-03T19:06:33Z
Astrissimo [PAPER ONLY]: -100.00% ROI; capture WAITING_FOR_FRESH_ELIGIBLE_FORECAST
Unnamed candidate [RESEARCH]: historical replay ROI unknown, n=? | prospective capture UNKNOWN | review weekly; historical bets are not forward evidence.