# Weekly Research Lane Report

- Generated: 2026-11-17T20:01:04Z
- Overall read: observe live sample

## Football Counts vNext

- Team Shots v4: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Team Shots v4 evidence: 29 signals, 29 settled, -13.94u, ROI -48.1%, true-close CLV +2.2%.
- Team Shots v4 input cohorts: Before 30 October 2026: 9 settled, -3.33u, ROI -37.0% | 30 October 2026 to input repair: 20 settled, -10.61u, ROI -53.0% | Prospective repaired inputs: 0 settled, +0.00u, ROI awaiting results. Promotion evidence: repaired inputs only.
- Team Shots v4 warm-up tracking (not bets): 14 signals, 14 settled / 0 pending, +0.32u, ROI +2.3%.
- Team Shots v4 latest scan: EXPECTED_EMPTY_CAPTURE_WINDOW; 0 rows / 0 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers -.
- Corners v3: count PASS; prospective AUTHORIZED_SHADOW; promotion BLOCKED.
- Corners v3 evidence: 213 signals, 190 settled, -8.52u, ROI -4.5%, true-close CLV +0.9%.
- Corners v3 warm-up tracking (not bets): 36 signals, 36 settled / 0 pending, -2.50u, ROI -7.0%.
- Corners v3 latest scan: NO_EDGE_AFTER_UNLOCK; 630 rows / 39 fixtures scored; 0 fixtures passed edge but were warm-up blocked; blockers {'edge_below_3pct': 546, 'price_not_fresh_10m': 630, 'price_older_than_3h': 128}.
- Corners v4 G0 research: FAIL; 6901/10889 enriched; latest holdout MAE delta -0.0074; real-market Brier delta +0.0090 on n=431; line gates 0/5 passed; failed 7.5, 8.5, 9.5, 10.5, 11.5, 12.5.
- Neither experiment changes live routing or stakes.
- API-Football count archive: 0 fixtures; latest -; last run 15/30 requests.
- Cross-provider agreement: 0/0 API fixtures matched; status no_overlap.
- Team Fouls: F1 COUNT_GATE_FAIL_MARKET_BLOCKED; F2 COUNT_GATE_FAIL_EXTERNAL_GATES_BLOCKED; M2 WAIT_OR_FAIL; market prices BLOCKED; signals disabled.
- Goalkeeper Saves v1: count PASS on 42,958 observations; discovery OVER_ONLY_GOALKEEPER_SAVE_PRICES_RETURNED (10 probe Over lines); latest capture PARTIAL_CAPTURE_FAILURE (0 events selected / 0 rows / 0 with 1X2); prospective SIGNALS_COLLECTING with 0 priced lines, 0 eligible, 0 predicted-XI research rows, 114 signals and 104 settled; blockers {}; ROI +25.6%, CLV +4.8% n=36; promotion BLOCKED.
Calibrated Shots [ZERO-STAKE, retained prospective cohorts]: hypothetical ROI +3.2%, settled 34, pending 0 | WAITING_FOR_FRESH_PAIRED_MARKETS | 174 paired fixtures | version paired-market-offset-20261113-input-v6
Opponent Shots [SHADOW]: forward 56W/68L, ROI -15.2%, pending 0 | COLLECTING_FIXED_POLICY | scan 2026-11-17T19:56:42Z
Opponent Shots + frozen strength [RESEARCH]: historical replay ROI unknown, n=? | prospective capture UNKNOWN | review weekly; historical bets are not forward evidence.
GK paper comparison | TRACKING | Keeper Watch: 1W/3L, -0.50u, ROI -25.0%, pending 0, review 3, overdue 3 | paired current: 17W/19L, +0.19u, ROI +1.0%, pending 0, review 9, overdue 9 | paired fixtures 161; review 100 | no automatic promotion
GK half adjustment · AWAITING_FIRST_VERIFIED_BOARD · 0/0 paired fixtures settled · Current 0W/0L, +0.00u on 0.0u, ROI pending, Brier —, log loss — | Half adjustment 0W/0L, +0.00u on 0.0u, ROI pending, Brier —, log loss —
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
- Real-price CLV coverage: 0/104 (0.0%) | true closes 0.
- Settled ledger: 99/104 settled, 24W/72L, -16.52u, ROI -16.7%.
- Extreme-gap quarantine: 0/0 settled, +0.00u at 1u evaluation stakes, ROI -.
- Extreme-gap by league: no rows registered yet.
- Evidence freshness: STALE (2026-11-08T15:36:15Z).
- Decision: KEEP_RESEARCH | blockers: fifth fold pending, probability gate fail, market ROI gate unavailable, no matched closing prices, no settled extreme-gap rows.

## Assist Value V1 Research Gate

- Lane: FROZEN_RESEARCH | decision KEEP_FROZEN_MARKET_EVIDENCE | reactivation ready NO.
- Historical gate: PASS on 44,739 test rows; calibrated Brier 0.05556.
- Settlement gate: FAIL | player-assist agreement 0.00%.
- Market gate: FAIL | 1305 matched player prices across 8 calendar days.
- Prospective ledger: 0/0 settled (target 100), +0.00u, ROI -.
- Evidence freshness: FRESH (2026-11-17T20:00:55Z).
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

- Snapshot: 2026-11-17T10:31:19Z
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
Generated UTC: 2026-11-17T19:12:19Z
Status: COLLECTING_EVIDENCE (never auto-promoted)

Sample: 270/305 settled; 4 pending (4 due, 0 future, 0 unknown); 31 void
Record: 132W/138L/0P
P/L: -7.12u | ROI: -2.6%
CLV: +1.85% mean; 28.8% positive; n=163
Calibration: Brier 0.24703; predicted 59.1%; actual 48.9%; gap 10.3pp; n=270
Feed: HEALTHY_NO_QUALIFYING_EDGE; matched 9/9; two-way 9; over-only 0; public bettable 0

By market:
- aces: 80/90 settled, -2.63u, ROI -3.3%
- double_faults: 190/215 settled, -4.48u, ROI -2.4%

Blockers: settled sample 270/300; Slam coverage 1/2; CLV sample 163/300
Promotion gate: Human review only after 300 settled lines across at least two Slams, non-negative ROI, mean CLV >= +1%, positive CLV >= 55%, at least 100 calibrated win/loss rows with Brier <= 0.25 and absolute calibration gap <= 5pp, plus approved price integrity and a healthy pipeline.

Service Breaks v1 [INTERNAL]: OUTCOME_PASS | player ATP/WTA PASS | match ATP/WTA PASS | real price evidence NO_CAPTURE_OR_LEDGER_EVIDENCE | prospective 0 | strict 0 rows/0 settled/+0.00u/ROI - | Bet365-only 0 rows/0 settled/+0.00u/ROI - | count calibration 0/0 settled | NOT SELLABLE

## Tennis Props Model vs Bet365

- Status: EVIDENCE_BUILDING
- Clean main lines: 71 observed, 64 settled, 4 pending.
- Count MAE: model 2.716; observed Bet365-implied mean 2.794.
- Brier: model 0.2234; Bet365 0.2299; delta +0.0065 (positive favours the model).
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
11W/22L | -4.51u on 33u | ROI -13.66% | 5 pending, 0 void, 3 overdue.
Predicted ace total bias -10.4% across 118 player matches (negative = underprediction). Capture: NO_NEW_ELIGIBLE_QUOTES. Historical +10.79%/19 bets stays separate. Manual review milestone reached.

Indoor Scout | indoor Masters, including qualifying | PAPER ONLY
2W/3L | +1.55u on 5u | +31.00% ROI
0 pending (0 overdue), 0 void, 0 quarantined. 66 captured fixtures; Brier 0.2448, log loss 0.6861. Core Strict gates; optional overlays not simulated. 1u paper, zero real stake. Capture WAITING_FOR_FRESH_PRICED_FIXTURES at 2026-11-16T22:53:26.226592+00:00. 
Indoor Scout ATP250/500 | qualifying included | PAPER ONLY
0W/0L | +0.00u on 0u | ROI awaits settled selections
0 pending (0 overdue), 0 void, 0 quarantined. 12 captured fixtures; Brier 0.2340, log loss 0.6585 vs market 0.2484/0.6975. Core Strict gates; optional overlays not simulated. 1u paper, zero real stake. Capture WAITING_FOR_FRESH_PRICED_FIXTURES at 2026-11-17T10:15:23.630598+00:00. 

ELO REBUILD | retired 6 November; no new captures. Evidence retained; 8 existing fixtures pending exact settlement. Live unchanged.
PUBLISHED ELO | separate comparison paused with shared collector; dependency review still required.

Sisal 50/50 [PAPER ONLY; 1u hypothetical / 0 real stake]
9W/3L | +4.90u / 12u | ROI +40.83% | 0 pending, 0 void, 0 overdue; 0 retirement-determined bets.
38 frozen paired prices; 38 completed player contracts / 20 independent fixtures.
Ace-count bias +0.56 per player-match (negative = underprediction).
Model: Brier 0.2402; log loss 0.6734 on identical completed contracts.
Market: Brier 0.2518; log loss 0.6967 on identical completed contracts.
50/50: Brier 0.2404; log loss 0.6738 on identical completed contracts.
BO3: 12 settled, +4.90u, ROI +40.83%.
Capture: NO_NEW_ELIGIBLE_QUOTES. No individual alerts; live models unchanged. Historical replay excluded.
Event correction comparison: 21 identical forward contracts; 0 without earlier main-draw evidence.
Original 50/50: 5W/0L | +4.25u/5u | ROI +85.00% | 0 pending, 0 void, 0 overdue.
Event-adjusted 50/50: 4W/0L | +3.50u/4u | ROI +87.50% | 0 pending, 0 void, 0 overdue.
Comparison uses the same prices and fixed rules. Earlier full record remains separate; no new alerts or live changes.
Comparison exclusions: incomplete_event_evidence: 17
Ledger checkpoint: 380f4f67816c3f99

BREAK POINT C | 29 settled fixtures | 2W/1L | 3u paper | +0.76u | ROI +25.33% | 0 pending bets | LL C 0.7070 / market 0.6956. No alerts; completed-result research, bookmaker grading unverified.

Match Shape | ATP BO3 incl. qualifying/indoor | PAPER ONLY | no alerts
55 fixtures / 110 contracts; 50 independently settled fixtures.
Total games Current: 1W/3L/0P; -2.15u/4u; -53.75% ROI; 0 pending (0 overdue), 2 excluded, 0 quarantined. Brier 0.2589, log loss 0.7110.
Total games Frozen T1: 3W/10L/0P; -7.52u/13u; -57.85% ROI; 0 pending (0 overdue), 3 excluded, 0 quarantined. Brier 0.2670, log loss 0.7278.
Handicaps Current: 11W/10L/0P; +4.86u/21u; +23.14% ROI; 0 pending (0 overdue), 0 excluded, 0 quarantined. Brier 0.2487, log loss 0.6905.
Handicaps Frozen T1: 10W/7L/0P; +3.86u/17u; +22.71% ROI; 0 pending (0 overdue), 3 excluded, 0 quarantined. Brier 0.2628, log loss 0.7191.
Capture NO_NEW_ELIGIBLE_CONTRACTS; 1u paper, zero real stake. Reviews at 50/100 settled fixtures. ML unchanged; raw/C0 controls in Monitor.

ATP J1 score correction | frozen forward comparison | zero real stake, no alerts
Started 2026-11-10; 7 fixtures / 14 contracts; 7 settled fixtures.
Market-anchored J1: 3W/3L/0P; -0.04u/6u; ROI -0.67%; 0 pending, 0 overdue. Brier 0.2213, log loss 0.6337 (7 fixtures).
Frozen J1 score correction: 2W/0L/0P; +2.00u/2u; ROI +100.00%; 0 pending, 0 overdue. Brier 0.2124, log loss 0.6163 (7 fixtures).
Current pricing reference copy: 0W/1L/0P; -1.00u/1u; ROI -100.00%; 0 pending, 0 overdue. Brier 0.2235, log loss 0.6380 (7 fixtures).
Capture: NO_NEW_ELIGIBLE_CONTRACTS. Exploratory; no automatic promotion.
Original research INCONCLUSIVE; original A/B gates failed and remain unchanged. New prospective exploratory registration.

Team Shots strength correction | frozen forward comparison | zero real stake, no alerts
Started 2026-11-10; 0 fixtures / 0 contracts; 0 settled fixtures.
Opponent, paired cohort: 0W/0L/0P; +0.00u/0u; ROI pending; 0 pending, 0 overdue. calibration pending.
Opponent + frozen strength: 0W/0L/0P; +0.00u/0u; ROI pending; 0 pending, 0 overdue. calibration pending.
Capture: NO_NEW_ELIGIBLE_CONTRACTS. Exploratory; no automatic promotion.
Leakage-safe historical test did not establish improvement. Exploratory future test only; no historical rows counted as forward evidence.
Most Aces fixed-reference comparison | >=2-book forward paper, no extra alerts
Direct baseline: 0W/3L | 3u | -3.00u | ROI -100.00% | pending 0, overdue 0
Direct fixed_reference: 0W/3L | 3u | -3.00u | ROI -100.00% | pending 0, overdue 0
3 paired fixtures; model Brier/LL 0.0923/0.2634, reference 0.0475/0.1903; unchanged probabilities. Added 0, removed 0; paired P/L difference +0.00u.
Secondary: difference per paired fixture 0.0000u; 0 changed, 1 editions. Descriptive only until at least 30 changed / 10 editions and precision review. Pending fixtures 1, overdue 0.
Count baseline: 0W/2L | 2u | -2.00u | ROI -100.00% | pending 1, overdue 0
Count fixed_reference: 0W/2L | 2u | -2.00u | ROI -100.00% | pending 1, overdue 0
3 paired fixtures; model Brier/LL 0.0642/0.2163, reference 0.0475/0.1903; unchanged probabilities. Added 0, removed 0; paired P/L difference +0.00u.
Primary: difference per paired fixture 0.0000u; 0 changed, 1 editions. Descriptive only until at least 30 changed / 10 editions and precision review. Pending fixtures 1, overdue 0.
Capture: CHECKED_NO_NEW_COMPARISONS; {'fewer_than_two_valid_books': 4, 'no_current_price_candidates': 12}. Zero real stake; no promotion.
Bookmaker checks: Bet365: SOURCE_FAILED; Sisal IT: QUOTES_CAPTURED; Grosvenor: QUOTES_CAPTURED
Most Aces single-book evidence | current gate, separate from paired comparison
Direct: 5 captured, 2 selected, 3 no-bets | 0W/1L | 1u | -1.00u | ROI -100.00% | pending bets 1, overdue 0.
2 settled fixtures, 1 editions; model Brier/LL 0.0611/0.2107, book 0.0740/0.2318. Pending outcomes 3; overdue 0. 3 also in paired view; never add totals. Books {'Bet365': 3, 'Grosvenor': 2}; coverage {'single_quote': 5}.
Count: 5 captured, 2 selected, 3 no-bets | 0W/0L | 0u | +0.00u | ROI n/a | pending bets 2, overdue 0.
2 settled fixtures, 1 editions; model Brier/LL 0.0554/0.1973, book 0.0740/0.2318. Pending outcomes 3; overdue 0. 3 also in paired view; never add totals. Books {'Bet365': 3, 'Grosvenor': 2}; coverage {'single_quote': 5}.
Capture: CAPTURED; {'no_current_price_candidates': 12}. Gate comparison not applicable to single-book rows. Descriptive only; zero real stake, no alerts.

Most DF | PAPER OBSERVATION ONLY | 0W/10L | -10.00u on 10u | ROI -100.00% | 0 pending (0 overdue). 15/150 independent settled fixtures. Capture: NO_NEW_ELIGIBLE_QUOTES. No betting alerts; unvalidated independent-count benchmark.

Astra models FULL-BOARD PAPER, including lines blocked by normal signal filters; 1u per selected line | Astra Aces [oncourt-current-history-20261007-v1]: 147 settled fixtures; 0 unresolved quote records (0 older than 48h); baseline ROI -37.4% (79 selected lines), Astra ROI -38.9% (71 selected lines), Astra odds >=5.00: 2W/48L, -28.00u | Astra DF [oncourt-current-history-20261007-v1]: 160 settled fixtures; 10 unresolved quote records (10 older than 48h); baseline ROI -16.6% (184 selected lines), Astra ROI -23.2% (259 selected lines), Astra odds >=5.00: 7W/93L, -30.50u | Astra Aces [oncourt-current-history-20261030-v2]: 10 settled fixtures; 12 unresolved quote records (12 older than 48h); baseline ROI -54.2% (12 selected lines), Astra ROI -50.0% (11 selected lines), Astra odds >=5.00: 0W/5L, -5.00u | Astra DF [oncourt-current-history-20261030-v2]: 4 settled fixtures; 0 unresolved quote records (0 older than 48h); baseline ROI -64.0% (5 selected lines), Astra ROI -70.0% (6 selected lines), Astra odds >=5.00: 0W/1L, -1.00u | Astra Aces [oncourt-current-history-20261104-v3]: 14 settled fixtures; 16 unresolved quote records (0 older than 48h); baseline ROI -70.7% (13 selected lines), Astra ROI -70.7% (13 selected lines), Astra odds >=5.00: 0W/9L, -9.00u | Astra DF [oncourt-current-history-20261104-v3]: 14 settled fixtures; 12 unresolved quote records (0 older than 48h); baseline ROI -100.0% (9 selected lines), Astra ROI -79.0% (11 selected lines), Astra odds >=5.00: 0W/3L, -3.00u | data FRESH; multiple lines per match are correlated. Review floors: 200 fixtures, 8 weeks, 4 tournaments within each input version. Manual review before promotion.


Astra Volume PAPER ONLY: 2W/2L, ROI +18.40%, 0 pending (0 overdue). Paired fixtures settled 58; review at 50 and 100. Capture WAITING_FOR_FRESH_ELIGIBLE_FORECAST at 2026-11-17T10:17:22.450136+00:00. No verified closing-price coverage.
Hardcourt Scout | Challenger outdoor hard | PAPER ONLY
1W / 4L | ROI -49.60% | -2.48u on 5u
0 pending (0 overdue), 1 void, 0 quarantined. 1u hypothetical stakes; zero real stake. Review at 50 and 100 settled selections. Capture WAITING_FOR_ELIGIBLE_FIXTURES at 2026-11-17T10:32:41.763690+00:00. Report 2026-11-17T10:32:54.100231+00:00. Historical +22.65% replay excluded; closing prices unverified.
Fable correction alongside Scout | same forward cohort | PAPER ONLY
Scout baseline: 1W/3L, -1.48u/4u, ROI -37.00%; 0 pending, 0 void, 0 quarantined. Brier 0.2641; log loss 0.7240; predicted 49.8% / observed 54.9%.
Fable frozen: 0W/2L, -2.00u/2u, ROI -100.00%; 0 pending, 0 void, 0 quarantined. Brier 0.2745; log loss 0.7696; predicted 49.5% / observed 54.9%.
122 paired settled fixtures; 4 history fallbacks, 1 unavailable. Since 2026-10-29T19:45:47.701147+00:00. Capture CAPTURED. Same 50/100 fixture review; no automatic promotion.

MODEL REVIEW WATCHLIST
Calibrated Shots [ZERO-STAKE, retained prospective cohorts]: hypothetical ROI +3.2%, settled 34, pending 0 | WAITING_FOR_FRESH_PAIRED_MARKETS | 174 paired fixtures | version paired-market-offset-20261113-input-v6
Input cohorts | pre-30 Oct: 24 settled, ROI +14.3%; xG gap: 10 settled, ROI -23.5%; repaired: 0 settled, ROI awaiting results. Review uses repaired inputs only.
EMA20 v3 / v4 / Opponent paired comparison [RESEARCH]: historical replay ROI unknown, n=? | prospective capture DAILY_EXISTING_FOOTBALL_COUNTS_WORKFLOW | review weekly; historical bets are not forward evidence.
Astra Volume [RESEARCH]: historical replay ROI +7.25%, n=69 | prospective capture CONNECTED_FIRST_CAPTURE_VERIFIED | review weekly; historical bets are not forward evidence.
Opponent Shots [SHADOW]: forward 56W/68L, ROI -15.2%, pending 0 | COLLECTING_FIXED_POLICY | scan 2026-11-17T19:56:42Z
Input cohorts | pre-30 Oct: 98 settled, ROI -13.6%; xG gap: 26 settled, ROI -20.8%; repaired: 0 settled, ROI awaiting results. Review uses repaired inputs only.
Astrissimo [PAPER ONLY]: -100.00% ROI; capture WAITING_FOR_FRESH_ELIGIBLE_FORECAST
Unnamed candidate [RESEARCH]: historical replay ROI unknown, n=? | prospective capture UNKNOWN | review weekly; historical bets are not forward evidence.
ATP J1 score correction [RESEARCH]: historical replay ROI unknown, n=? | prospective capture UNKNOWN | review weekly; historical bets are not forward evidence.
Opponent Shots + frozen strength [RESEARCH]: historical replay ROI unknown, n=? | prospective capture UNKNOWN | review weekly; historical bets are not forward evidence.