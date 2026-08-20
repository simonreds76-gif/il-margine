# Challenger ML evidence verdict

Date: 2026-08-20  
Branch reviewed: `golden-with-speed-insights`

## Commercial verdict

There is no authorised Challenger betting model today. The old 23-row batch is
an audit artifact, not a betting record, and remains frozen.

The absence of evidence was a plumbing failure rather than a lack of data. The
repository has enough outcomes, model probabilities and captured Pinnacle odds
to reject the old context model and to operate a fresh prospective evidence
lane.

## What the historical evidence says

- Legacy batch: 23 settled rows, 8 wins and 15 losses.
- Legacy rows with usable entry odds: 15, returning `-2.601u` and `-17.3% ROI`.
- Archived context data: 48,400 Challenger matches from 2022-01-03 through
  2026-05-18 with a locked 2026 holdout of 5,195 matches.
- Claude independently joined 1,608 holdout matches to real Pinnacle prices.
- Context model: Brier `0.21970`, log loss `0.63018`, AUC `0.7060`.
- Pinnacle no-vig: Brier `0.19642`, log loss `0.57594`, AUC `0.7706`.
- Optimal model/market blend weight: `0%` model, `100%` Pinnacle.
- Flat ROI was negative at every tested model-edge threshold:
  - edge >= 0%: `n=1,420`, ROI `-12.33%`
  - edge >= 10%: `n=1,009`, ROI `-15.50%`
  - edge >= 20%: `n=754`, ROI `-17.84%`
  - edge >= 30%: `n=550`, ROI `-19.08%`
- The 10-15% edge window has no historical justification. It is retained only
  as a locked forward cohort for the different production hybrid, not as a
  profitable rule.

## Canonical real-price data now available

The recovered scorer `scripts/score-tennis-spread-history.py` was extended to
score ML independently of handicap availability. On local history from
2026-03-01 through 2026-08-20 it produced:

- 4,175 settled Challenger ML matches.
- 1,018 matches with a verified close no older than 12 hours before kickoff.
- 52.19% player-one win rate, confirming outcome orientation is balanced.
- Zero publication snapshots at or after known kickoff.
- Zero duplicate match keys.
- Pinnacle market Brier `0.200994` and log loss `0.585814`.

This is a market benchmark and settlement foundation. It does not itself
measure model edge.

## Prospective v2 lifecycle

The daily and AM runners now append only HIGH-coverage, high-confidence
Challenger candidates in the locked 10-15% edge window to fresh files:

- `strict-signals-challenger-ml-v2-live.csv`
- `strict-signals-challenger-ml-v2-archive.csv`

Every row is forced to `0u` with `stake_model=prospective_evidence_no_stake`.
The archive is settled nightly. The weekly run audits verified-close CLV and
regenerates canonical ATP/Challenger market benchmarks. The monitor reads the
v2 files; the legacy 23-row batch is not merged into v2.

## Promotion gates

No Challenger model becomes a betting lane unless all of these pass on fresh
prospective data:

- At least 300 CLV-eligible forecasts.
- Mean CLV at least `+1.0%`.
- At least 52% of forecasts beat the closing price, with a confidence interval
  excluding 50%.
- ECE at most `0.03` on at least 300 forecasts.
- Model log loss no worse than Pinnacle no-vig on the identical matches.
- ROI is confirmatory only: at least 500 settled bets and the lower bound of a
  95% interval above zero.

## Next model experiment

Do not tune another threshold around the rejected context probabilities. The
next registered challenger should compare, walk-forward and out of sample:

1. Pinnacle no-vig baseline.
2. Rank plus surface Elo/Glicko baseline.
3. Causal rolling serve/return strength, opponent adjusted by surface.
4. Recency, workload, inactivity and main-tour/Challenger transition features.
5. A market-residual model trained to predict outcome residuals or closing-line
   movement, not raw winners from scratch.

Any candidate that cannot beat Pinnacle log loss is rejected before ROI is
examined.

