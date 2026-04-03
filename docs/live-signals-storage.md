# Live Signals Storage

The tennis signal pipeline now writes two CSV layers for each signal family:

- `*-live.csv`
  - current live snapshot only
  - one active row per match / market lane
  - used by the fair-odds route and the live queue parts of the monitor
- `*-archive.csv`
  - append-only historical log
  - keeps version history for settlement, CLV, performance, and export jobs

Current families:

- `data/backtest/strict-signals-live.csv`
- `data/backtest/strict-signals-archive.csv`
- `data/backtest/strict-signals-volume200-live.csv`
- `data/backtest/strict-signals-volume200-archive.csv`
- `data/backtest/strict-signals-spreadshadow-live.csv`
- `data/backtest/strict-signals-spreadshadow-archive.csv`
- `data/backtest/strict-signals-claycal-live.csv`
- `data/backtest/strict-signals-claycal-archive.csv`

Compatibility note:

- legacy paths like `strict-signals.csv` are still mirrored from the live snapshot
- this keeps older local tools working while the read paths are migrated
- settlement and reporting should prefer the explicit `*-archive.csv` files

## Public artifact

Each `strict-policy-report.py --append` run also refreshes:

- `data/backtest/signals-current.json`

This JSON is not wired into production yet. It exists as the next-step artifact if we want
to publish current signal overlays to the public site without making Supabase the critical
path for live signals.

Recommended public flow when we are ready:

1. local pipeline writes `*-live.csv` and `*-archive.csv`
2. local pipeline refreshes `signals-current.json`
3. we decide whether to:
   - commit/push the JSON artifact for Vercel deploy freshness
   - or publish it through a separate storage layer later

For now:

- localhost and local ops pages should keep reading local live/archive files
- public routes should avoid adding new network dependencies for signals until we have a stable reason to do so
