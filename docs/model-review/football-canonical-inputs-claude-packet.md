# Claude Review Packet: Football Canonical Input Layer

We are improving Il Margine football derivative models without adding distracting products.
Please audit the plan and challenge any weak assumptions before we wire it into production.

## Current Goal

Build a canonical football team/player form layer that can feed team shots, corners, and goalscorer models.
Do not build steam tracking, public xG tables, or a Dixon-Coles product yet.

## Audit Artifacts

- Markdown audit: `data/football-form/input-audit.md`
- JSON audit: `data/football-form/input-audit.json`

## Implemented Artifacts So Far

- Team-match base table: `data/football-form/team-match-base.csv`
- Causal rolling team-form table: `data/football-form/team-rolling-form.csv`
- Team-form generation report: `data/football-form/team-form-report.md`
- Team-form table now preserves raw values plus causal league-relative normalized fields.
- These artifacts are not wired into live model selection yet.
- Version manifest: `data/football-form/team-form-manifest.json`
- Schema/freshness validation report: `data/football-form/team-form-validation.md` / `data/football-form/team-form-validation.json`
- Player-log freshness health: `data/football-form/player-log-health.json`
- Goalscorer model smoke test: `data/football-form/goalscorer-player-log-smoke.md`
- Research backtest summary: `data/football-form/canonical-backtest-summary.csv`
- Research backtest report: `data/football-form/canonical-backtest-report.md`
- Corners canonical v0 beats current on aggregate common-sample and last-90 common-sample count MAE and Brier/log-loss.
- Team-shots canonical v1_market_nb adds capped 1X2 win-probability/game-state adjustment plus causal prior-data league negative-binomial O/U conversion. It improves Brier/log-loss, but recent count MAE is not yet better than current.
- Diagnostic `*_t12` variants now replay trailing-12-month league-level normalization. The replay does not improve aggregate last-90 corners or team-shots enough to promote.
- No live policy or published pick logic has been changed yet; this remains research-only pending odds/CLV and recent-window validation.
- Corners v0 segment promotion check: `data/football-form/corners-v0-promotion-check.md` / `data/football-form/corners-v0-promotion-check.json`
- Segment gate read: partial research lane only. Passing leagues `epl, ligue-1, serie-a`; blocked leagues `bundesliga, la-liga`.
- Corners v0 publication config: `data/football-form/corners-v0-allowed-leagues.json`. The publisher/monitor reads this config instead of relying on a stale one-off report.
- Corners v0 CLV monitor schema/report: `data/football-form/corners-v0-clv-monitor.csv` / `data/football-form/corners-v0-clv-monitor.md`
- League YoY variance report: `data/football-form/league-yoy-variance.md` / `data/football-form/league-yoy-variance.json`
- EPL and Serie A show material shots/corners regime variance, so trailing-12-month normalization should be implemented before any football-form promotion.
- Lower-threshold YoY variance sensitivity: `data/football-form/league-yoy-variance-7pct.md` / `data/football-form/league-yoy-variance-7pct.json`
- At 7%, primary trailing-12-month candidates expand to `epl, la-liga, ligue-1, serie-a`; guarded/sparse candidates `bundesliga`.
- Team-shots last-90 diagnostic: `data/football-form/team-shots-last90-diagnostic.md` / `data/football-form/team-shots-last90-diagnostic.json`
- Cap-disabled team-shots lambda does not beat capped lambda in the recent window, so the cap is not the first suspect.
- Team-shots v1 promotion gate: `data/football-form/team-shots-v1-promotion-check.md` / `data/football-form/team-shots-v1-promotion-check.json`
- Team-shots v1 allowed-league config: `data/football-form/team-shots-v1-allowed-leagues.json`
- Team-shots current-vs-canonical feature gap diagnostic: `data/football-form/team-shots-feature-gap-diagnostic.md` / `data/football-form/team-shots-feature-gap-diagnostic.json`
- Team-shots v2 pooled-opponent promotion gate: `data/football-form/team-shots-v2-promotion-check.md` / `data/football-form/team-shots-v2-promotion-check.json`
- Team-shots v2 allowed-league config: `data/football-form/team-shots-v2-allowed-leagues.json`
- Team-shots v3 EMA20 promotion gate: `data/football-form/team-shots-v3-ema20-promotion-check.md` / `data/football-form/team-shots-v3-ema20-promotion-check.json`
- Team-shots v3 EMA20 allowed-league config: `data/football-form/team-shots-v3-ema20-allowed-leagues.json`
- Team-shots v1 CLV monitor schema/report: `data/football-form/team-shots-v1-clv-monitor.csv` / `data/football-form/team-shots-v1-clv-monitor.md`
- Team-shots v2 CLV monitor schema/report: `data/football-form/team-shots-v2-clv-monitor.csv` / `data/football-form/team-shots-v2-clv-monitor.md`
- Team-shots v3 EMA20 CLV monitor schema/report: `data/football-form/team-shots-v3-ema20-clv-monitor.csv` / `data/football-form/team-shots-v3-ema20-clv-monitor.md`
- Team-shots active research config pointer: `data/football-form/team-shots-active-allowed-leagues.json`
- Team-shots v2 EMA diagnostic: `data/football-form/team-shots-v2-ema-diagnostic.md` / `data/football-form/team-shots-v2-ema-diagnostic.json`
- Corners v0 venue/component diagnostic: `data/football-form/corners-v0-venue-diagnostic.md` / `data/football-form/corners-v0-venue-diagnostic.json`
- Corners home-correction diagnostic: `data/football-form/corners-home-correction-diagnostic.md` / `data/football-form/corners-home-correction-diagnostic.json`
- Corners total diagnostic: `data/football-form/corners-total-diagnostic.md` / `data/football-form/corners-total-diagnostic.json`
- Research-lane state log: `data/football-form/research-lane-state.md` / `data/football-form/research-lane-state.json`

## Changes Since Previous Review

- The 15-day stale player-log issue is fixed. Hosted goalscorer refresh now checks freshness, refreshes stale leagues, writes health output only to temp, and hardens rebase/dirty-worktree handling.
- Added schema/freshness validation for canonical team-form outputs: row counts, required fields, critical coverage, duplicate keys, freshness, market coverage, and xG coverage warnings.
- Added date-versioned canonical CSV outputs and a manifest so model reports can record exactly which canonical data version they used.
- Added causal league-relative normalized fields for shots, corners, and xG. They now include both all-prior and trailing-12-month baselines, both excluding the current matchday.
- Added common/canonical-only/full and last-90 sample splits to the canonical backtest report.
- Added a team-shots `canonical_form_v1_market_nb` research variant using the market-implied win probability gap as a capped game-state proxy and causal prior-data negative-binomial O/U calibration.
- Added diagnostic `canonical_form_v1_market_nb_t12` and `canonical_form_v0_t12` replay variants. They test whether trailing-12-month league-level normalization fixes recent regression; it does not on aggregate.
- Added a league year-over-year variance check to decide whether all-prior normalization is safe or trailing-12-month baselines are required.
- Added a corners v0 per-league promotion gate. Aggregate corners passed, but Bundesliga and La Liga fail the recent segment gate, so all-league promotion is blocked.
- Operationalised the corners v0 gate as an allowed-league config. Initial research publication is allowed only for EPL, Ligue 1, and Serie A; Bundesliga and La Liga stay blocked.
- Added a corners v0 CLV monitor schema with publication, 3h, 1h, close, CLV, time-to-kickoff, allowed-league blocking, and hard canonical-only guard fields.
- Ran the lower-threshold YoY variance sensitivity Claude requested. At 7%, La Liga and Ligue 1 also become primary trailing-12-month candidates; Bundesliga remains guarded/sparse because its primary shots/corners are just below threshold while xG is sparse/volatile.
- Ran the team-shots last-90 diagnostic plus largest-error input spot checks. Cap-disabled and T12 replay are both worse than capped canonical on aggregate, so cap tuning and simple league-level normalization are not the first fix.
- Hardened generated-CSV workflows: backtest/diagnostic/promotion scripts rebuild ignored canonical CSVs when missing instead of writing zero-row reports.
- Hardened corners CLV allowed-league config to fail closed if the config is missing or malformed.
- Added a team-shots v1 per-league promotion gate. Result: partial research gate only. `la-liga` passes; `bundesliga`, `epl`, `ligue-1`, and `serie-a` remain blocked.
- Added a team-shots current-vs-canonical feature gap diagnostic. It compares current lambda columns with canonical lambda decomposition and dumps the 25 worst last-90 rows where canonical loses to current.
- Added a diagnostic `canonical_form_v2_current_shape_nb` replay to test whether the current model's multiplicative league-relative formula shape fixes the issue when fed canonical inputs. It worsens count MAE, so formula shape alone is not the fix.
- Added `canonical_form_v2_pooled_opp_nb`, a targeted replay that keeps canonical v1's additive/market/NB shape but uses pooled opponent shots concession instead of the opponent venue split.
- Added a team-shots v2 segment gate. Result: partial research gate only. `bundesliga`, `la-liga`, and `ligue-1` pass; `epl` and `serie-a` stay blocked.
- Added the team-shots v1 CLV monitor schema. It is empty-safe and currently reports zero published picks, but the guard/CLV columns are in place for La Liga research publication.
- Added the corners venue/component diagnostic. It confirms corners v0 does not show the same home-team overshoot shape as team-shots; blocked Bundesliga/La Liga corners need a corners-specific fix, not the team-shots pooled-opponent patch.
- Promoted team-shots v2 from candidate to active research config in the state log. v1 is now deprecated/reference only.
- Added a team-shots active config pointer so operators can see that v2 is the active research model and v1 is historical reference.
- Added a v2 CLV monitor report pointed at the v2 allowed-league config. It is empty-safe and currently has zero published picks.
- Added a v2+EMA diagnostic sweep. The 20-match venue-EMA blend helps aggregate and Serie A, but EPL remains blocked under the +0.5% count-improvement gate.
- Added a corners home-correction diagnostic. Symmetric home/away correction cannot move total-corners O/U; one-sided home premium worsens Bundesliga and La Liga.
- Added clean causal EMA20 fields to the canonical team-form table using decay `0.93`.
- Added `canonical_form_v3_ema20_nb`: v2 pooled-opponent defence plus canonical EMA20 history fields.
- Ran the v3 promotion gate. Result: all five leagues pass common and last-90 count/Brier/log-loss gates; canonical-only remains blocked.
- Promoted v3 to the active team-shots research config; v1 and v2 are now reference variants.
- Added a v3 CLV monitor schema/report. It is empty-safe and currently has zero published picks.
- Added a corners total-level diagnostic for Bundesliga and La Liga. It confirms the remaining corners issue is total-level calibration/pressure, not home/away redistribution.

## Backtest Highlights

| Area | Sample | N | Current MAE | Canonical MAE | Probability gate | Read |
| --- | --- | ---: | ---: | ---: | --- | --- |
| corners v0 | common | 20655 | 2.7876 | 2.7492 | Brier ok, log-loss ok | aggregate pass only; segment gate decides publication |
| corners v0 | last_90_common | 570 | 2.6663 | 2.6309 | Brier ok, log-loss ok | recent window also passes |
| corners v0_t12 | last_90_common | 570 | 2.6663 | 2.6520 | diagnostic | T12 replay is worse than base v0 aggregate; do not promote |
| corners v0 | canonical_only | 2 | - | 9.8308 | no baseline | sample is tiny; add confidence guard, do not infer coverage safety |
| team-shots v1_market_nb | common | 2464 | 3.7425 | 3.7262 | Brier ok, log-loss ok | NB helps O/U calibration |
| team-shots v1_market_nb | last_90_common | 1140 | 3.7320 | 3.7699 | Brier ok, log-loss ok | probability passes, count MAE does not; keep research-only |
| team-shots v1_market_nb_t12 | last_90_common | 1140 | 3.7320 | 3.8024 | diagnostic | T12 replay worsens aggregate count MAE; do not promote |
| team-shots v2_current_shape_nb | last_90_common | 1140 | 3.7320 | 4.0120 | diagnostic | current-style multiplicative replay is worse; formula shape alone is not enough |
| team-shots v2_pooled_opp_nb | last_90_common | 1140 | 3.7320 | 3.7270 | Brier ok, log-loss mixed by league | pooled opponent defence fixes aggregate recent MAE but still fails EPL and Serie A segment gates |
| team-shots v3_ema20_nb | last_90_common | 1140 | 3.7320 | 3.6413 | Brier ok, log-loss ok | clean EMA20 canonical fields pass all five league segment gates |
| team-shots v1_market_nb | canonical_only | 38850 | - | 3.5336 | no baseline | coverage looks usable, still needs segment gates |

## Normalization Read

- 10% material threshold: primary trailing-12-month candidates `epl, serie-a`; guarded/sparse candidates `bundesliga`.
- 7% sensitivity threshold: primary trailing-12-month candidates `epl, la-liga, ligue-1, serie-a`; guarded/sparse candidates `bundesliga`.
- T12 replay has now been tested as a diagnostic. It does not fix aggregate last-90 team-shots or corners.
- Keep Bundesliga guarded first: shots/corners are just below the 7% line, while xG variance is sparse and should not be blindly promoted into the model.

## Team-Shots Last-90 Diagnostic

- Full common MAE: current `3.7425`, canonical capped `3.7262`.
- Last-90 common MAE: current `3.7321`, canonical capped `3.7699`, cap disabled `3.7948`, T12 replay `3.8024`.
- Cap-disabled recent MAE beats capped recent MAE: `no`.
- Recent canonical capped lags current in: `bundesliga, epl, ligue-1, serie-a`.
- Cap hurts by league only in: `serie-a`.
- T12 replay helps by league only in: `epl, serie-a`.
- Read: do not tune the cap first and do not promote simple T12 scaling. The recent count issue now points to current-model feature comparison / deeper lambda structure.

## Team-Shots V1 Segment Gate

- All-league research promotion: fail.
- Passing leagues for partial research lane: `la-liga`.
- Blocked leagues: `bundesliga, epl, ligue-1, serie-a`.
- Canonical-only hard block: on; even though canonical-only N is large (`38850`), it has not passed segment calibration.
- La Liga last-90 common: current MAE `3.8294`, v1 MAE `3.7148`, improvement `2.99%`; Brier/log-loss gates pass.
- EPL/Ligue 1/Serie A fail count gates; Bundesliga is near parity on count but fails the last-90 improvement threshold and log-loss.

## Team-Shots Feature Gap Diagnostic

- Full common: current MAE `3.7425`, canonical v1 MAE `3.7262`.
- Last-90 common: current MAE `3.7321`, canonical v1 MAE `3.7699`.
- Last-90 mean canonical-current lambda gap: `+0.3262`; canonical is higher than current on about 60% of rows.
- Venue split is important: away teams slightly improve under canonical (`3.5693` vs current `3.5861`), but home teams regress (`3.9706` vs current `3.8780`).
- Current model differences now identified:
  - current uses 20-match EMA with decay `0.93`; canonical currently has r5/r10 simple windows only;
  - current uses venue-specific team attack but pooled opponent defence;
  - current uses a multiplicative league-relative formula;
  - current blends xG lambda at 25% where xG history is available.
- Diagnostic replay `canonical_form_v2_current_shape_nb` copied the current-style multiplicative formula shape using canonical inputs. It worsened last-90 MAE to `4.0120`, so the next test should not be "just make canonical multiplicative". The missing value is more likely 20-match EMA/history smoothing and/or the exact current xG/venue treatment.

## Team-Shots V2 Pooled-Opponent Result

- V2 test: keep canonical additive/market/NB shape, but replace venue-specific opponent shots concession with pooled opponent shots concession.
- Aggregate last-90 common improves from v1 `3.7699` to v2 `3.7270`, narrowly beating current `3.7320`.
- Passing v2 research leagues: `bundesliga`, `la-liga`, `ligue-1`.
- Blocked v2 leagues: `epl`, `serie-a`.
- EPL fails last-90 count and probability gates: current `3.4593`, v2 `3.5543`, improvement `-2.75%`.
- Serie A almost ties count but does not clear the required improvement: current `3.9397`, v2 `3.9463`, improvement `-0.17%`.
- Read: Claude's pooled-opponent hypothesis is directionally correct and materially improves the model, but it is not enough for all-league team-shots publication. Use segment-gated research only.
- Operational state: v2 is now the active research candidate. v1 remains as a reference because it only offers a stronger La Liga backtest, while v2 is simpler and passes La Liga by the configured threshold.

## Team-Shots V2 EMA Diagnostic

- Diagnostic only: blends v2 with current model smoothing outputs to decide whether it is worth porting EMA into the canonical layer.
- Best `venue20` blend weight: `0.5`. Last-90 ALL current MAE `3.7321`; candidate MAE `3.6965`; improvement `0.95%`.
- Passing leagues at best `venue20` weight: `bundesliga`, `la-liga`, `ligue-1`, `serie-a`.
- Blocked league at best `venue20` weight: `epl`.
- Best `recent6` weight: `0.0`, which means short recent-form smoothing is worse than v2 and should not be promoted.
- Read: 20-match venue EMA is promising for Serie A, but it does not fix EPL. Do not blindly ship v3; either implement clean canonical EMA fields and rerun gates or run an EPL-specific diagnostic.

## Team-Shots V3 EMA20 Result

- V3 implementation: keep v2's pooled opponent defence, capped market/game-state adjustment, and NB O/U calibration; replace r5/r10 simple history with causal EMA20 fields generated inside `team-rolling-form.csv`.
- EMA20 decay: `0.93`; newest prior match receives weight `1.0`.
- All-league last-90 common: current MAE `3.7320`, v3 MAE `3.6413`, improvement `2.43%`.
- Passing v3 research leagues: `bundesliga`, `epl`, `la-liga`, `ligue-1`, `serie-a`.
- Blocked v3 leagues: `-`.
- League last-90 count improvements:
  - Bundesliga: current `3.8478`, v3 `3.7622`, improvement `2.22%`.
  - EPL: current `3.4593`, v3 `3.3498`, improvement `3.17%`.
  - La Liga: current `3.8294`, v3 `3.7293`, improvement `2.61%`.
  - Ligue 1: current `3.5528`, v3 `3.4854`, improvement `1.90%`.
  - Serie A: current `3.9397`, v3 `3.8507`, improvement `2.26%`.
- Common and last-90 Brier/log-loss gates pass for every league and every standard team-shots line.
- Operational state: v3 is now the active research candidate. v1 and v2 remain reference variants only. Canonical-only fixtures remain blocked.

## Corners V0 Segment Gate

- All-league research promotion: fail.
- Passing leagues for partial research lane: epl, ligue-1, serie-a.
- Active allowed-league config: `epl, ligue-1, serie-a`.
- Blocked leagues until recent segment calibration is fixed: bundesliga, la-liga.
- Canonical-only hard block: on; sample N=2.
- Do not publish canonical-only picks. Do not publish Bundesliga or La Liga corners v0 picks yet.

## Corners V0 Venue Diagnostic

- Corners v0 already uses pooled opponent corner concession, so the team-shots venue-specific concession bug is not directly present.
- Last-90 all-league current total MAE `2.6663`; corners v0 total MAE `2.6309`.
- Bundesliga remains blocked: current `2.5871`, v0 `2.6594`.
- La Liga remains blocked: current `2.7026`, v0 `2.7749`.
- Home component does not show the team-shots pattern. In Bundesliga and La Liga, home lambda gaps are negative (`-0.2155`, `-0.3106`), not the big positive home overshoot seen in team-shots.
- Away component is consistently higher under v0. The next corners fix should be corners-specific: away pressure/concession or league-specific corner calibration, not the team-shots pooled-opponent patch.

## Corners Home-Correction Diagnostic

- The home/away bias exists at component level, but the product we gate is total corners.
- Symmetric home/away correction has no effect on total-corners O/U because home addition is cancelled by away subtraction.
- One-sided home premium worsens the blocked leagues:
  - Bundesliga v0 last-90 MAE `2.6594`; with full home premium `2.7364`.
  - La Liga v0 last-90 MAE `2.7749`; with full home premium `2.9278`.
- Read: do not build a corners home-advantage correction for total O/U. The next corners test needs to target total-corners calibration or pressure directly.

## Corners Total Diagnostic

- Diagnostic target: match total-corners expectation directly, not home/away components.
- Last-90 blocked-league summary:
  - Bundesliga: current MAE `2.5870`, v0 MAE `2.6594`, delta `+0.0724`; v0 bias `+0.0861`, lambda gap `+0.3233`.
  - La Liga: current MAE `2.7026`, v0 MAE `2.7749`, delta `+0.0723`; v0 bias `+0.2350`, lambda gap `+0.1245`.
- Bundesliga damage clusters in high-pace/both-high-attack fixtures:
  - High pace: current `2.8750`, v0 `3.2312`, delta `+0.3562`.
  - Both high attack: current `2.6876`, v0 `3.1329`, delta `+0.4453`.
- La Liga damage is less clean:
  - Neutral pace worsens (`+0.1859`), one-sided attack worsens (`+0.2093`), low pace improves (`-0.1467`).
- Read: a blunt scalar may be too crude. Bundesliga points toward pressure/attack-shape over-amplification; La Liga likely needs a separate total-level bucket diagnostic before any publication expansion.

## Findings From Current Repo

- No hard input-audit issues detected by the first pass.

## Proposed Implementation Order

1. Keep the stale-player-log fix in production workflows and monitor the next scheduled run.
2. Keep corners v0 research publication restricted by `corners-v0-allowed-leagues.json`: EPL, Ligue 1, and Serie A only.
3. Keep the corners confidence guard as a hard cutoff: canonical-only fixtures are blocked, not flagged.
4. Keep T12 replay as diagnostic only. It did not fix aggregate team-shots or corners regression.
5. Hold team-shots all-league promotion. La Liga can be allowed in research-only via `team-shots-v1-allowed-leagues.json`, with canonical-only fixtures still blocked.
6. Keep Bundesliga/La Liga corners blocked until a variant passes their recent segment gates.
7. Team-shots v2 pooled-opponent is the active research candidate for `bundesliga`, `la-liga`, and `ligue-1`, with canonical-only still blocked.
8. Use `canonical_form_v3_ema20_nb` as the active team-shots research candidate for all five leagues.
9. Keep team-shots canonical-only fixtures blocked until canonical-only segment validation exists.
10. Watch v3 CLV passively; do not react before the pre-defined sample thresholds.
11. For corners Bundesliga/La Liga, do not apply a home/away redistribution fix. It cannot move total O/U.
12. Next corners work: test total-level pressure/attack-shape calibration, starting with Bundesliga high-pace and both-high-attack buckets; keep La Liga blocked until its failure mode is cleaner.

## Questions For Follow-up Review

1. Team-shots v3 clean EMA20 now passes all five league segment gates. Any objection to making v3 the active research candidate while keeping canonical-only blocked?
2. Should v3 go straight into passive CLV monitoring only, or should we add one more diagnostic split before letting it publish research picks?
3. Corners total diagnostic points to Bundesliga high-pace/both-high-attack over-amplification. Should the next test be a pressure cap, attack-shape cap, or league-specific total scalar?
4. La Liga corners failure is not as clean as Bundesliga. Should we keep La Liga fully blocked until a clearer bucket-level fix appears?
5. Team-form freshness is acceptable by max-age (latest league dates 2-6 days old), but xG coverage is still only 6.5%. Should xG stay guarded/debug-only for all derivative football models until coverage improves?
6. Is the fail-closed allowed-league config plus explicit re-promotion criteria enough operational discipline for corners v0 and team-shots v3 research publication?
