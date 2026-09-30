# Fixed shots comparison and corners review

EMA20 v3: the April 26 to May 24 record has 68 eligible bets, 41 wins,
27 losses and +7.40 units (+10.88%). Exact quoted odds and probabilities
were found in pre-kickoff Git commits for all 68. Four blocked rows are
excluded. This corroborates publication but does not establish complete
raw feature vintage or future profitability.

## New comparison

`team-shots-paired-reference.py` saves the first fresh paired quote for each
fixture, team, bookmaker and half-line. Both sides and all three models
are stored, including unavailable forecasts and no-bet decisions. Only
the first scan of a fixture can choose one hypothetical selection per
model. Later lines cannot change that decision. Real stakes remain zero.

The v3 inference and feature functions are copied verbatim from commit
5b6fc5331, with source hashes in config/team-shots-ema20-reference.json.
Its historical live path used neutral 1X2 context, league NB dispersion,
a 5% edge threshold and at most one selection per fixture. New ingestion
uses current verified aliases and duplicate safeguards. All three models
receive results strictly before the earlier paired quote date, a more
conservative safety cutoff than the old kickoff-date implementation.
The current v4 1X2 context remains timestamp checked. This is a registered
new comparison, not a recreation of the old prospective ledger.

No model is fitted or promoted. The existing daily count job runs the
collector; the scheduler change retains hourly evidence on the existing
cadence. There are no additional API calls or Vercel operations.

The JSONL forecast ledger is append-only. The separate status report
recomputes outcomes from the existing team-match base and refuses conflicting
counts. Proper scores and count errors use the exact common cohort and
average within fixture before averaging across fixtures. ROI is secondary;
selected subsets differ. No final winner should be declared from a few bets.
Review first at 50 settled independent fixtures, and again at 150; use
fixture-level uncertainty before any promotion proposal. Multiple lines
and both teams do not count as independent fixtures.

StatsHub is explicitly NOT_CONNECTED until contemporaneous matching
forecasts are recorded. Close-price measurement is NOT_YET_MEASURED;
existing first odds are not described as closing odds. The old historical
record and all reconstructed backtests remain separate.

## Corners

The old official_v3 +34.4% report used a synthetic B365 corners market
derived from 1X2 odds. It is not evidence of returns at executable odds.
The separate v2 captured-Pinnacle historical holdout lost 6.91 units on
130 selections (about -5.32% on all staked units; its report's -6.06% uses
114 non-push bets as denominator).

The v0 published ledger has 48 settled bets, 23 wins and 25 losses,
-1.12 units (-2.33%). All 48 originally had no publication blocker;
today's monitor marks them league_not_allowed under a later configuration.
Do not rewrite their historical eligibility using today's switch.

Current corners v3 has 41 eligible recorded selections, 20 wins and
21 losses, +0.394 units (+0.96%). Its separate 36 warm-up selections
lost 2.503 units. Settlement arithmetic matched recorded prices in both
ledgers. These are different periods and selected samples, not a paired
contest and not a full feature-vintage clearance. No old corners model
is restored to live staking on this evidence.
