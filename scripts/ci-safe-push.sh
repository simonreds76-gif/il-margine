#!/usr/bin/env bash
# Safely push a GitHub Actions commit back to the hosted branch.
#
# Why this exists:
# Multiple scheduled jobs commit generated data to golden-with-speed-insights.
# A plain `git rebase origin/branch` fails when the job has leftover generated
# tracked changes, and a plain push fails when another job pushed first. This
# helper rebases with autostash and retries branch-write failures without ever
# force-pushing.

set -euo pipefail

branch="${1:-golden-with-speed-insights}"
remote="${2:-origin}"
max_attempts="${CI_SAFE_PUSH_ATTEMPTS:-8}"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

for attempt in $(seq 1 "${max_attempts}"); do
  echo "Safe push attempt ${attempt}/${max_attempts} to ${remote}/${branch}"
  git fetch "${remote}" "${branch}"

  remote_head="$(git rev-parse "${remote}/${branch}")"
  commit_parent="$(git rev-parse HEAD^)"
  if [ "${remote_head}" = "${commit_parent}" ]; then
    # No competing writer landed after this workflow started. Push before
    # inspecting the huge generated tree, where line-ending normalization can
    # create unrelated dirty files that are irrelevant to this commit.
    if git push "${remote}" "HEAD:${branch}"; then
      echo "Safe push completed without rebase; remote still matched commit parent."
      exit 0
    fi
    if [ "${attempt}" -lt "${max_attempts}" ]; then
      sleep_seconds=$((attempt * attempt * 10))
      if [ "${sleep_seconds}" -gt 120 ]; then
        sleep_seconds=120
      fi
      echo "Direct push failed; retrying after ${sleep_seconds}s."
      sleep "${sleep_seconds}"
      continue
    fi
  fi

  if ! git diff --cached --quiet; then
    echo "::error::ci-safe-push was called with staged changes after the workflow commit."
    git status --short
    exit 1
  fi

  # Hosted data jobs often leave generated files outside the committed scope
  # (for example status files, locks, or secondary snapshots). Rebase requires a
  # clean tree, so park those leftovers instead of letting the push step fail
  # after the useful commit has already been created.
  if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "Stashing leftover generated files before rebase:"
    git status --short
    git stash push --include-untracked -m "ci-safe-push leftovers before rebase"
  fi

  # A large generated-data checkout can become dirty again while Git refreshes
  # line-ending-normalized files. Let rebase park that second wave as well.
  git rebase --autostash "${remote}/${branch}"

  push_log="$(mktemp)"
  if git push "${remote}" "HEAD:${branch}" 2>&1 | tee "${push_log}"; then
    rm -f "${push_log}"
    echo "Safe push completed."
    exit 0
  fi

  if [ "${attempt}" -lt "${max_attempts}" ]; then
    if grep -Eiq 'fatal error in commit_refs|remote rejected.*failure|RPC failed|expected flush|Connection was reset|HTTP 5[0-9]{2}' "${push_log}"; then
      echo "::warning::GitHub rejected the ref write with a transient/internal error; retrying after a longer backoff."
    else
      echo "::warning::Push failed; retrying after re-fetch/rebase."
    fi
    rm -f "${push_log}"
    sleep_seconds=$((attempt * attempt * 10))
    if [ "${sleep_seconds}" -gt 120 ]; then
      sleep_seconds=120
    fi
    echo "Retrying after ${sleep_seconds}s."
    sleep "${sleep_seconds}"
  else
    rm -f "${push_log}"
  fi
done

echo "::error::Safe push failed after ${max_attempts} attempts."
git status --short
exit 1
