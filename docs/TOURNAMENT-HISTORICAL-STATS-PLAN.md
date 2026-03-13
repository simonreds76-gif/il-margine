# Tournament historical stats - plan for robustness features (v2)

Use 2022-2026 data (odds, Pinnacle CLV, results, Sackmann seed/entry) to build tournament-level historical aggregates so we can make the model more robust with facts like:

- "At this tournament over the past 4 years, favorites had +8% ROI level-stake, dogs -15%."
- "Qualifiers at this tournament: 12-18 in R1 (2022-2025); ex-qualifiers often lose R1."
- "Seeds 1-2 at this event have never made the final" / "always won the tournament."

Pre-2022 is out of scope (tournaments/conditions change); focus on every tournament played since 2022.

---

## Data we have

| Source | What it has | Use for |
|--------|-------------|--------|
| Backtest results `data/backtest/backtest-results-20XX.csv` | date, tournament, surface, round, series, player1, player2, our_prob, pinnacle_odds, actual_winner, model_favorite, bet_result, confidence | Tournament-level favorite vs dog ROI (level-stake), by tournament_key and year or rolling window. |
| Tennis-data xlsx `atp-20XX.xlsx` | Tournament, Round, Winner, Loser, PSW, PSL, optional WRank/LRank | Same as above via backtest; xlsx has no seed/entry. |
| Sackmann `data/sackmann/atp_matches_20XX.csv` | tourney_name, tourney_date (tournament start date, not match date), round, winner_seed, loser_seed, winner_entry, loser_entry (Q, WC, LL, MD, etc.), winner_id, loser_id | Seed and entry stats per tournament. No odds -> rates/counts from Sackmann alone. |
| Pinnacle snapshots | Odds by date | CLV and live use; historical aggregates here are from backtest CSVs. |

Gap: Backtest has no seed/entry. Phase 3 join backtest <-> Sackmann requires a robust key: tournament_key + season_year + winner/loser + round (or equivalent). Do not join on exact match date because Sackmann `tourney_date` is tournament start, not match date.

**Data availability (Sackmann vs other sources):** Sackmann ATP match files (`atp_matches_20XX.csv`) are published with a lag; **2025 does not exist yet** and may not appear until well into or after that season. Missing `atp_matches_2022.csv` or `atp_matches_2025.csv` in the repo is therefore expected, not a pipeline bug. For coverage we have **TML** (`tml-data/`) and **OnCourt** (Supabase / `data/oncourt/`) for matches; seed/entry stats from Sackmann are only available for years where the Sackmann file is present. The script’s “Missing Sackmann years detected” in the QA report is informational—no need to “fix” by creating or waiting for those files.

---

## Scope and guardrails

- Lock: Model/policy changes go through `FAIR-ODDS-POLICY-LOCK.md`. This work is data preparation; use in model only after walk-forward validation.
- Descriptive vs decision: Phase 1/2 outputs are reporting/descriptive immediately. Promote to model or policy only after walk-forward validation against the locked baseline.
- Anti-leakage (`as_of_date`): Any feature used for a match must be computed only from data known before that match. For tournament-history priors, the safest rule is previous editions only (exclude the current edition results when computing stats for a match in that edition).
- Season year convention (explicit): use `season_year` from source file names (for example `backtest-results-2025.csv`, `atp_matches_2025.csv`), not calendar year from match dates. This avoids misclassifying year-end events that belong to the next season.

---

## Implementation order

1. Phase 0: Build canonical tournament map/alias table (tennis-data + Sackmann -> shared `tournament_key`).
2. Phase 1 and Phase 2 with a QA report (coverage, sample rows).
3. Phase 3 only if join quality gates pass (see below); otherwise do not use segment-ROI features.
4. Walk-forward policy validation using these artifacts before any model change.

---

## Phase 0 - Canonical tournament map (do this first)

- Goal: one canonical mapping from (tennis-data tournament name, Sackmann tourney_name) -> `tournament_key` so all phases use the same keys.
- Input: all tournament names seen in backtest-results-*.csv and Sackmann atp_matches_*.csv.
- Logic: apply `_tour_key` (normalize, strip year/challenger/qualifiers, tokenize). Where the same event has different names (for example "Brisbane" vs "Brisbane International"), maintain a small alias table (for example `data/backtest/tournament-aliases.csv`: `source`, `name`, `tournament_key`).
- Output: `data/backtest/tournament-key-map.csv` (or equivalent) and alias table.
- Quality gate: tournament-key mapping coverage >= 98% for both backtest and Sackmann tournament names. If coverage fails, fix aliases before proceeding; do not run Phase 3 until this passes.

---

## Phase 1 - Tournament favorite/dog ROI (from backtest results only)

- Input: `data/backtest/backtest-results-2022.csv` through `backtest-results-2025.csv` (and 2026 when available). Use Phase 0 map for `tournament_key`.
- ROI formula (level-stake, stake = 1 per bet):
  - Per bet: win -> P/L = (odds - 1); loss -> P/L = -1.
  - ROI = total_pl / n_bets (not sum(1/odds)).
- Aggregation: by `tournament_key`, then by year and rolling windows (for example last 3, last 4 years).
- Anti-leakage: for use in model features, compute from previous editions only (exclude the same season as the target match). If current season is included, mark output as reporting-only.
- Output: `data/backtest/tournament-fav-dog-roi.csv` with raw + shrunk + n.

---

## Phase 2 - Seed and entry stats (from Sackmann)

- Input: `data/sackmann/atp_matches_2022.csv` through `atp_matches_2025.csv` (and 2026 if present). Map `tourney_name` -> `tournament_key` via Phase 0.
- Logic by (`tournament_key`, year/window):
  - Seed buckets (1-2, 3-4, 5-8, 9-16, 17-32, unseeded): win rate, matches, max round reached.
  - Entry types (Q, WC, LL, MD, etc.): win rate and round distribution.
  - Narrative aggregates (for reporting): seed 1-2 ever won, max round, qualifier R1 win rate.
- Anti-leakage: same rule as Phase 1 for model use (previous editions only).
- Output: `data/backtest/tournament-seed-entry-stats.csv` with raw + shrunk + n.

---

## Phase 3 - Join backtest + Sackmann for ROI by segment (optional; run only if gates pass)

- Goal: produce segment ROI like "qualifiers at this tournament had -15% ROI when backed level-stake".
- Join key: tournament_key + season_year + winner name + loser name + round (or equivalent robust key). Do not use exact match date.
- Quality gates (all required):
  1. Tournament-key mapping coverage >= 98%.
  2. Match join rate >= 90-95% (and one-to-one join quality).
  3. Manual audit sample of matched and unmatched rows.
- If any gate fails: skip Phase 3 and document the failure.
- Output (if gates pass): `data/backtest/tournament-segment-roi.csv` with raw + shrunk + n.
- Join trust modes:
  - `all` (default): all accepted joins; recommended for reporting coverage.
  - `high_medium`: excludes low-trust date-disambiguated and cross-year joins.
  - `high`: full-name, non-date-disambiguated joins only.
  - For model validation, compare `all` vs `high_medium` and check sign stability on rows with `n >= 30`.

---

## Phase 4 - Script and artifacts

- Script: `scripts/build-tournament-historical-stats.py`
  - Phase 0: map + alias + coverage QA.
  - Phase 1: favorite/dog ROI raw + shrunk + n + QA.
  - Phase 2: seed/entry raw + shrunk + n + QA.
  - Phase 3: run only if gates pass; otherwise skip and report why.
  - Options: `--years 2022 2023 2024 2025`, `--rolling 4`, `--output-dir data/backtest`, `--previous-editions-only`.
- QA report: write `data/backtest/tournament-stats-qa-report.txt` (or .md): coverage, join rate, sample matched/unmatched rows, pass/fail gates.
- Documentation: add a one-line reference in `FAIR-ODDS-POLICY-LOCK.md` once the script exists.

---

## Shrinkage and min-sample (all phases)

- Store both raw and shrunk metrics for each aggregate.
- Always store n.
- Hard usage gate for model/policy:
  - minimum n >= 30
  - preferred n >= 50
- This applies to Phase 1 (fav/dog ROI), Phase 2 (seed/entry), and Phase 3 (segment ROI).

---

## Using the stats later (after lock)

- Reporting: Phase 1/2 outputs can be used immediately in dashboards and narrative reporting.
- Model/policy: only promote after walk-forward validation against the locked baseline.
- Candidate uses (subject to change control):
  - Feature: `tournament_fav_roi_prev_editions`
  - Filter: for example skip value when tournament dog ROI (previous editions, shrunk) < -20% and n >= 30.
- Live model change requires lock-file update and approval.

---

## Who implements

Either Codex or Cursor can implement from this plan. Keep this doc as the spec and link the implemented script from `FAIR-ODDS-POLICY-LOCK.md`.
