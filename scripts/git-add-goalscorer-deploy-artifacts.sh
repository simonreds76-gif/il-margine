#!/usr/bin/env bash
set -euo pipefail

# Keep GitHub Actions from re-adding bulky live-history / inbox snapshots.
# This allowlist is deliberately limited to files consumed by the site,
# monitor snapshots, or the next hosted goalscorer run.
shopt -s nullglob

blocked_artifacts=(
  data/goalscorer/live-history
  data/goalscorer/*/live-history
  data/goalscorer/inbox
  data/goalscorer/match-results
  data/goalscorer/test-run
  data/goalscorer/*/fotmob-*.json
  data/goalscorer/all-leagues-live-board.json
  data/goalscorer/goalscorer-odds-history.csv
)

artifacts=(
  data/goalscorer/team-logo-map.json
  data/goalscorer/team-kit-colors.json
  data/goalscorer/world-cup-2026-penalty-takers.json
  data/goalscorer/world-cup-2026-penalty-duty-review.json
  data/goalscorer/world-cup-2026-penalty-duty-live-review.json

  data/goalscorer/.understat-progress-*.json
  data/goalscorer/*-player-match-logs-*.csv
  data/goalscorer/*-penalty-takers.json
  data/goalscorer/*-penalty-baseline-evidence.json
  data/goalscorer/*-penalty-baseline-overrides.json

  data/goalscorer/confirmed-lineups.json
  data/goalscorer/*-confirmed-lineups.json

  data/goalscorer/goalscorer-live-snapshot.json
  data/goalscorer/goalscorer-monitor-snapshot.json
  data/goalscorer/goalscorer-live-status.json
  data/goalscorer/club-penalty-alert-state.json
  data/goalscorer/goalscorer-live-schedule-state.json
  data/goalscorer/goalscorer-match-status.json
  data/goalscorer/goalscorer-health-status.json
  data/goalscorer/goalscorer-live.log

  data/goalscorer/live-board.json
  data/goalscorer/goalscorer-live-comparison.csv
  data/goalscorer/goalscorer-live-comparison.txt
  data/goalscorer/*/live-board.json
  data/goalscorer/*/goalscorer-live-comparison.csv
  data/goalscorer/*/goalscorer-live-comparison.txt

  data/goalscorer/goalscorer-public-signals.csv
  data/goalscorer/goalscorer-shadow-signals.csv
  data/goalscorer/goalscorer-public-performance.txt
  data/goalscorer/goalscorer-shadow-performance.txt
  data/goalscorer/*-public-signals.csv
  data/goalscorer/*-shadow-signals.csv
  data/goalscorer/*-public-performance.txt
  data/goalscorer/*-shadow-performance.txt

  data/goalscorer/fair-odds-lab-*-signals.csv
  data/goalscorer/fair-odds-lab-*-quarantine.csv
  data/goalscorer/fair-odds-lab-*-performance.txt
  data/goalscorer/fair-odds-lab-clv.csv
  data/goalscorer/fair-odds-lab-clv-weekly.txt
  data/goalscorer/backtest/walkforward-metrics.csv
  data/goalscorer/backtest/walkforward-report.txt
  data/goalscorer/backtest/walkforward-calibrators.json

  data/goalscorer/penalty-duty-context.json
  data/goalscorer/penalty-duty-review.csv
  data/goalscorer/penalty-duty-review.json
  data/goalscorer/penalty-duty-live-review.json
  data/goalscorer/*/penalty-duty-context.json
  data/goalscorer/*-penalty-duty-review.csv
  data/goalscorer/*-penalty-duty-review.json
  data/goalscorer/*-penalty-duty-live-review.json

  public/fair-odds-lab/*
)

# If an older workflow run reintroduced generated bulk files, remove them from
# the index again before staging the deployment allowlist.
if ((${#blocked_artifacts[@]} > 0)); then
  git rm -r --cached --ignore-unmatch -- "${blocked_artifacts[@]}" 2>/dev/null || true
fi

git add -u data/goalscorer public/fair-odds-lab || true

# This file starts untracked on the first final-status-aware run. Stage it
# independently so an unrelated missing optional artifact cannot abort the
# broad allowlist command below before the lifecycle evidence is retained.
if [[ -f data/goalscorer/goalscorer-match-status.json ]]; then
  git add -f -- data/goalscorer/goalscorer-match-status.json
fi

if ((${#artifacts[@]} > 0)); then
  git add -f -- "${artifacts[@]}" 2>/dev/null || true
fi
