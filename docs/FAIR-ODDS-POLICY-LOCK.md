# FAIR Odds Policy Lock

Do not change the baseline model or strict policy without explicit approval.
This file is the source of truth for the locked setup.

## Model lock

- Version: Iteration 4 baseline.
- Core scripts:
  - `scripts/backtest-fair-odds.py`
  - `scripts/oncourt-compute-fair-odds.py`
- Current behavior includes:
  - Tier-aware calibration and damping.
  - ATP250 favorite guard.
  - ATP500 hard calibration blend reduced (conservative in hard ATP500 path).
  - Series and confidence-specific delta multipliers.
  - Crisis downweight on rank in lower tiers.

## Strict live policy lock

- API strict mode is ON.
- Segment allowed: `Hard|Masters 1000`.
- Confidence allowed: `high`.
- Minimum value threshold: `10%` (public). Internal tracking at 5% for confirmation.
- This is the POLICY signal shown on fair-odds page and used for strict reporting.

## Additional policy exclusion (wired)

- Rule: exclude ATP500 hard short favorites when:
  - series = `ATP500`
  - surface = `Hard`
  - confidence in configured set
  - model favorite odds < configured threshold
- Current default config:
  - confidence set = `high`
  - threshold = `1.8`
- Wiring status:
  - Backtest CLI: enabled with `--policy-exclude-atp500-hard-short-favs`
  - Strict policy report: same exclusion logic
  - API metadata: exposes exclusion rules and excluded count
- Note: current strict live segment is Masters 1000 only, so this ATP500 exclusion is mainly for backtest/policy analytics unless strict segments are expanded.

## Tournament side-policy overlay (optional, off by default)

- **Production mode:** API and strict report support `base` (strict policy only) or `overlay` (strict + tournament-segment filter). **Default is `base`** — overlay is opt-in.
- **How to enable overlay in UI/API:** Set `STRICT_POLICY_PRODUCTION_MODE=overlay` (and optionally the overlay env vars below). Leave unset or set to `base` to keep current live behavior.
- **Recommended rollout:** Run the strict report with overlay first for a few weeks and compare settled outcomes for passed vs skipped; then enable overlay in the API if evidence is good.
- **Overlay env vars (optional overrides):**
  - `STRICT_OVERLAY_POLICY_FILE` — path to segment ROI CSV (default: `data/backtest/tournament-segment-roi.csv`)
  - `STRICT_OVERLAY_WINDOW` — e.g. `prior_editions` (default)
  - `STRICT_OVERLAY_FAMILY` — `seed` or `entry` (default: `seed`)
  - `STRICT_OVERLAY_MIN_N` — min sample size (default: 50)
  - `STRICT_OVERLAY_MIN_ROI_PCT` — min shrunk ROI % (default: -5)
  - `STRICT_OVERLAY_MISSING_MODE` — `skip` or `allow` (default: `skip`)
- **Deployment:** The overlay CSV must be readable at runtime. If using the default path, ensure `data/backtest/tournament-segment-roi.csv` is in the repo (and thus deployed); or set `STRICT_OVERLAY_POLICY_FILE` to an absolute path or URL the server can read. Rebuild tournament stats periodically (e.g. after new backtest years) and commit or upload the updated CSV.

## Injury overlay (optional, off by default)

- Data source: `data/injured-players-tennisexplorer.csv` refreshed by `scripts/scrape-tennisexplorer-injured.py`.
- Strict/API behavior:
  - Always compute injury flags per match (`recent_injured_p1/p2/any`) using TennisExplorer `source=injured`.
  - Optional filter overlay excludes strict candidates when either player is flagged.
  - Gate: `STRICT_INJURY_OVERLAY_ENABLED` (default `false`).
  - Lookback: `STRICT_INJURY_LOOKBACK_DAYS` (default `14`).
  - CSV path override: `INJURED_PLAYERS_CSV` (default `data/injured-players-tennisexplorer.csv`).
- Model behavior (`scripts/oncourt-compute-fair-odds.py`):
  - Optional probability downweight for recently injured players.
  - Gates:
    - `FAIR_ODDS_INJURY_DOWNWEIGHT_ENABLED` (default `false`)
    - `FAIR_ODDS_INJURY_LOOKBACK_DAYS` (default `14`)
    - `FAIR_ODDS_INJURY_DELTA` (default `0.02`, capped)
  - Risk control: downweight cannot flip the pre-adjustment favorite.
- Promotion rule: keep both overlays off in production until validation confirms improvement (backtest or settled side-by-side reporting).

## CPI overlay (optional, off by default)

- Data source: Tennis Abstract ATP surface-speed/CPI report by year.
- Storage table: `tournament_surface_speed` (create with `docs/supabase-tournament-surface-speed.sql`).
- Refresh script: `scripts/scrape-tennisabstract-surface-speed.py` (wired into daily/weekly jobs).
  - Scheduled default refresh: current + previous season.
  - One-time historical backfill: `--start-year 1991`.
- Model behavior (`scripts/oncourt-compute-fair-odds.py`):
  - Optional CPI tournament-speed adjustment in two places:
    - Match probability delta (small style-speed interaction, capped).
    - Expected-total-games center SPW (CPI ratio, blended with venue SPW when available).
  - Gates and defaults:
    - `FAIR_ODDS_CPI_ENABLED=false` (default)
    - `FAIR_ODDS_CPI_FALLBACK_YEARS=3`
    - `FAIR_ODDS_CPI_MATCH_WEIGHT=0.025`
    - `FAIR_ODDS_CPI_MATCH_CAP=0.012`
    - `FAIR_ODDS_CPI_Z_CAP=2.0`
    - `FAIR_ODDS_CPI_TOTAL_RATIO_WEIGHT=0.020`
    - `FAIR_ODDS_CPI_TOTAL_RATIO_MIN=0.95`
    - `FAIR_ODDS_CPI_TOTAL_RATIO_MAX=1.05`
    - `FAIR_ODDS_CPI_WITH_VENUE_BLEND=0.20`
- Promotion rule: keep CPI overlay disabled in production until backtest + settled validation confirms improvement.

## Current reference metrics

- 2022-2025 pooled baseline (value > 5%): ROI about `-4.371%`.
- 2022-2025 pooled with policy exclusion enabled (`high`, `<1.8`): ROI about `-3.601%`.
- 2026 file currently has limited usable rows and does not validate ATP500 exclusion yet.

## Change control

Any model or policy change requires:

1. Explicit approval before implementation.
2. Backtest comparison vs locked baseline (same files, same thresholds).
3. Rolling check across year slices, not pooled only.
4. Short note in this file with date and reason for change.

## Testing horizon and decision gates

Expected timeline is months, not days, if the goal is trustworthy profitability evidence.

- Phase 1 (1-2 weeks): pipeline stability and settlement correctness.
- Phase 2 (6-8 weeks): early directional read from CLV and settled outcomes.
- Phase 3 (4-6 months): medium confidence ROI read (target roughly 250 to 400 settled bets).
- Phase 4 (9-12 months): high-confidence performance read (target 500+ settled bets).

Use CLV earlier as a faster signal; use settled ROI over longer windows to avoid noise.

## Reference commands

- Baseline backtest:
  - `python scripts/backtest-fair-odds.py --files data/backtest/atp-2022.xlsx data/backtest/atp-2023.xlsx data/backtest/atp-2024.xlsx data/backtest/atp-2025.xlsx --thresholds 2,5,10 --dry-run`
- Policy-on backtest:
  - `python scripts/backtest-fair-odds.py --files data/backtest/atp-2022.xlsx data/backtest/atp-2023.xlsx data/backtest/atp-2024.xlsx data/backtest/atp-2025.xlsx --thresholds 2,5,10 --policy-exclude-atp500-hard-short-favs --policy-short-fav-confidence high --policy-short-fav-max-odds 1.8 --dry-run`
- Walk-forward with tournament side-policy overlay (validation only):
  - `python scripts/backtest-walkforward-tune.py --train data/backtest/backtest-results-2024.csv --test data/backtest/backtest-results-2025.csv --threshold 5 --min-bets 80 --enable-tournament-side-policy --segment-policy-file data/backtest/tournament-segment-roi.csv --segment-policy-window prior_editions --segment-policy-family seed --segment-policy-min-n 50 --segment-policy-min-roi-pct -5 --segment-policy-missing-mode skip`
- Live fair-odds compute:
  - `python scripts/oncourt-compute-fair-odds.py`
- Strict report:
  - `python scripts/strict-policy-report.py --append`
- Injury scraper:
  - `python scripts/scrape-tennisexplorer-injured.py --max-pages 2`
- CPI scraper:
  - `python scripts/scrape-tennisabstract-surface-speed.py --start-year 1991`
- Settled performance (base vs overlay):
  - `python scripts/strict-policy-performance.py --days 7`

## Validation tools

- `scripts/build-tournament-historical-stats.py`
  - Builds tournament historical artifacts (key map, favorite/dog ROI, seed-entry stats, QA report) from backtest + Sackmann inputs.
  - Phase 3 trust modes supported via `--phase3-join-trust-mode all|high_medium|high` for sensitivity checks.
- `scripts/backtest-walkforward-tune.py`
  - Walk-forward calibration and exposure tuning tool (default train: 2024, test: 2025) for policy validation without re-fitting on the same test slice.
- `scripts/strict-policy-performance.py`
  - Weekly settled base-vs-overlay ROI/win-rate/PnL report from strict signal files (uses overlay-compare if present, with settlement backfill).
