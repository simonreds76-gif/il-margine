#!/usr/bin/env bash
# Safely push a GitHub Actions commit back to the hosted branch.
#
# Why this exists:
# Multiple scheduled jobs commit generated data to golden-with-speed-insights.
# A plain `git rebase origin/branch` fails when the job has leftover generated
# tracked changes, and a plain push fails when another job pushed first. This
# helper rebases the committed work in a clean temporary worktree and retries
# branch-write failures without force-pushing or touching runner leftovers.

set -euo pipefail

branch="${1:-golden-with-speed-insights}"
remote="${2:-origin}"
max_attempts="${CI_SAFE_PUSH_ATTEMPTS:-8}"
temp_root=""
temp_worktree=""

cleanup_temp_worktree() {
  if [ -n "${temp_worktree}" ]; then
    git worktree remove --force "${temp_worktree}" >/dev/null 2>&1 || true
  fi
  if [ -n "${temp_root}" ]; then
    rm -rf "${temp_root}"
  fi
  temp_root=""
  temp_worktree=""
}

trap cleanup_temp_worktree EXIT

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

  # Hosted data jobs can leave generated files outside the committed scope or
  # appear dirty again after line-ending normalization. Never stash or mutate
  # that checkout: rebase the committed evidence in a separate clean worktree.
  if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "Preserving leftover generated files in the runner checkout:"
    git status --short
  fi

  temp_root="$(mktemp -d)"
  temp_worktree="${temp_root}/worktree"
  git worktree add --detach "${temp_worktree}" HEAD >/dev/null

  if ! git -C "${temp_worktree}" rebase "${remote}/${branch}"; then
    echo "::error::Safe push could not rebase the workflow commit onto ${remote}/${branch}."
    git -C "${temp_worktree}" rebase --abort >/dev/null 2>&1 || true
    exit 1
  fi

  push_log="$(mktemp)"
  if git -C "${temp_worktree}" push "${remote}" "HEAD:${branch}" 2>&1 | tee "${push_log}"; then
    rm -f "${push_log}"
    cleanup_temp_worktree
    echo "Safe push completed."
    exit 0
  fi

  cleanup_temp_worktree

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
