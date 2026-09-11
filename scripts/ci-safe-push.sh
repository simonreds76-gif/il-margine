#!/usr/bin/env bash
# Publish committed workflow evidence without checking out or normalizing data.
# Merge Git objects directly so CRLF archives and dirty runner leftovers cannot
# break publication. Conflicts fail closed; pushes are always fast-forward.
set -euo pipefail

branch="${1:-golden-with-speed-insights}"
remote="${2:-origin}"
max_attempts="${CI_SAFE_PUSH_ATTEMPTS:-8}"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

if ! git diff --cached --quiet; then
  echo "::error::ci-safe-push was called with staged changes after the workflow commit."
  exit 1
fi

for attempt in $(seq 1 "${max_attempts}"); do
  echo "Safe push attempt ${attempt}/${max_attempts} to ${remote}/${branch}"
  git fetch "${remote}" "${branch}"
  remote_head="$(git rev-parse "${remote}/${branch}")"
  if git merge-base --is-ancestor HEAD "${remote_head}"; then
    echo "Safe push completed. Workflow commit is already on the remote."
    exit 0
  fi
  publish_head="$(git rev-parse HEAD)"
  if ! git merge-base --is-ancestor "${remote_head}" HEAD; then
    # No checkout, index mutation, stash or line-ending conversion. A three-way
    # object merge retains both writers, and refuses overlapping conflicts.
    if ! merge_result="$(git merge-tree --write-tree "${remote_head}" HEAD)"; then
      printf '%s\n' "${merge_result}"
      echo "::error::Safe push found conflicting committed changes; remote and runner files were left untouched."
      exit 1
    fi
    merge_tree="${merge_result%%$'\n'*}"
    publish_head="$(git log -1 --format=%B | git commit-tree "${merge_tree}" -p "${remote_head}")"
  fi
  if git push "${remote}" "${publish_head}:${branch}"; then
    echo "Safe push completed."
    exit 0
  fi
  if [ "${attempt}" -lt "${max_attempts}" ]; then
    sleep_seconds=$((attempt * attempt * 10))
    if [ "${sleep_seconds}" -gt 60 ]; then sleep_seconds=60; fi
    echo "::warning::Push failed; re-fetching and merging again after ${sleep_seconds}s."
    sleep "${sleep_seconds}"
  fi
done

echo "::error::Safe push failed after ${max_attempts} attempts."
exit 1
