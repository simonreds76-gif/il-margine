# Goalscorer Monitor Architecture Refactor Plan

## Summary
Refactor the goalscorer monitor to a snapshot-first production architecture.

The production goalscorer pages and APIs should read one compact hosted snapshot rather than scanning raw per-league CSV/JSON files, local git refs, or `match-results` directories at request time.

Target outcomes:
- production pages and APIs read one compact hosted snapshot only
- workflows rebuild and publish that snapshot after every goalscorer data update
- local dev can still use local files, but only through a separate dev-first loader path
- penalty watchlist enrichment moves out of page render and into snapshot generation

## Canonical Artifact
The canonical artifact is:

- `data/goalscorer/goalscorer-monitor-snapshot.json`

This snapshot is the production input for:
- `/model-monitor/goalscorer`
- `/model-monitor/goalscorer/lineups`
- `/api/model-monitor/goalscorer/penalty-watchlist`

The snapshot contract includes:
- `schema_version`
- `generated_at`
- `source_status`
- `league_cards`
- `live_bets`
- `fixture_health`
- `fixture_lineups`
- `penalty_watchlist`
- `shadow_summary`
- `public_summary`

## Builder
Build the snapshot with:

- `scripts/build-goalscorer-monitor-snapshot.py`

Responsibilities:
- read the existing raw goalscorer outputs already produced by the pipelines
- normalize team/player aliases once
- build league summary cards
- build live bet rows
- build lineup fixtures
- build fixture health
- build the penalty watchlist with on-pitch-at-penalty labels
- emit a compact JSON payload with only the fields the UI needs

Important rule:
- the builder is the only place that resolves penalty-watchlist match-result joins
- the pages must not scan `data/goalscorer/match-results/**` at request time

## Loader Split
Use two explicit modes:

### Production loader
- reads only `goalscorer-monitor-snapshot.json` from hosted sources
- order:
  1. Supabase snapshot table
  2. GitHub raw fallback
- no `process.cwd()` scans
- no `git show`
- no raw per-league file reads

### Development loader
- reads local snapshot file directly when present
- may fall back to hosted snapshot for comparison

## Page / API Refactor
Refactor:
- `src/app/model-monitor/goalscorer/page.tsx`
- `src/app/model-monitor/goalscorer/lineups/page.tsx`
- `src/app/api/model-monitor/goalscorer/penalty-watchlist/route.ts`

The goalscorer pages should consume snapshot data only.

The penalty-watchlist API should serve the snapshot-backed watchlist directly for reads while preserving the existing resolution POST action.

## Workflow Integration
Update:
- `.github/workflows/goalscorer-hot-live.yml`
- `.github/workflows/goalscorer-expected-refresh.yml`
- `.github/workflows/goalscorer-settlement.yml`

Required sequence after raw data generation:
1. run `build-goalscorer-monitor-snapshot.py`
2. write `data/goalscorer/goalscorer-monitor-snapshot.json`
3. upload hosted snapshot to Supabase
4. commit and push the snapshot file with the rest of goalscorer output

## Acceptance Targets
- local `npm run build` passes
- Vercel preview for goalscorer no longer exceeds the serverless bundle size limit
- the goalscorer page no longer emits broad `process.cwd()` file-tracing warnings from production code paths
- penalty watchlist rows are resolved from snapshot data, not runtime match-result scans
- production loader works even if local raw files are absent

