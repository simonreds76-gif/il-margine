#!/usr/bin/env bash
# Safely push a GitHub Actions commit back to the hosted branch.
#
# Why this exists:
# Multiple scheduled jobs commit generated data to golden-with-speed-insights.
# A plain `git rebase origin/branch` fails when the job has leftover generated
# tracked changes, and a plain push fails when another job pushed first. This
# helper rebases with autostash and retries the non-fast-forward race without
# ever force-pushing.

set -euo pipefail

branch="${1:-golden-with-speed-insights}"
remote="${2:-origin}"
max_attempts="${CI_SAFE_PUSH_ATTEMPTS:-4}"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

for attempt in $(seq 1 "${max_attempts}"); do
  echo "Safe push attempt ${attempt}/${max_attempts} to ${remote}/${branch}"
  git fetch "${remote}" "${branch}"
  git rebase --autostash "${remote}/${branch}"

  if git push "${remote}" "HEAD:${branch}"; then
    echo "Safe push completed."
    exit 0
  fi

  if [ "${attempt}" -lt "${max_attempts}" ]; then
    sleep_seconds=$((attempt * 5))
    echo "Push raced another writer; retrying after ${sleep_seconds}s."
    sleep "${sleep_seconds}"
  fi
done

echo "::error::Safe push failed after ${max_attempts} attempts."
git status --short
exit 1
