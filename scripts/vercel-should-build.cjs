#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Vercel Ignored Build Step.
 *
 * Vercel convention:
 *   exit 0 = skip this deployment build
 *   exit 1 = proceed with the build
 *
 * Only reviewed live-data artifacts and offline model maintenance are skipped.
 * Unknown paths, website inputs and mixed changes build by default. Compare the
 * complete change range, including the first preview of a multi-commit branch.
 */

const { execFileSync } = require("node:child_process");

const previousSha = process.env.VERCEL_GIT_PREVIOUS_SHA || "";
const currentSha = process.env.VERCEL_GIT_COMMIT_SHA || "HEAD";
const commitMessage = process.env.VERCEL_GIT_COMMIT_MESSAGE || "";
const commitRef = process.env.VERCEL_GIT_COMMIT_REF || process.env.VERCEL_GIT_COMMIT_REF_NAME || "";

function log(...args) {
  console.log("[vercel-should-build]", ...args);
}

function build(reason) {
  log(reason);
  process.exit(1);
}

function skip(reason) {
  log(reason);
  process.exit(0);
}

if (commitMessage.includes("[force build]")) {
  build("force build flag found in commit message");
}

function parseFileList(output) {
  return output.split("\0").filter(Boolean);
}

function git(...args) {
  return execFileSync("git", args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 15000,
  });
}

function changedSince(base) {
  git("merge-base", "--is-ancestor", base, currentSha);
  // Include both ends of renames: moving website code to an offline path builds.
  return parseFileList(git("diff", "--no-renames", "--name-only", "-z", base, currentSha));
}

let changedFiles;
if (previousSha) {
  try {
    changedFiles = changedSince(previousSha);
  } catch (error) {
    log(`previous deployment comparison unavailable: ${error.message.split(/\r?\n/)[0]}`);
    if (process.env.VERCEL === "1" && commitRef) {
      try {
        git("fetch", "--no-tags", "--deepen=200", "origin", commitRef);
        changedFiles = changedSince(previousSha);
      } catch {
        log("previous deployment still unavailable after bounded history fetch");
      }
    }
    // A missing/rewritten previous deployment must not hide website changes.
    if (!changedFiles) build("cannot verify the previous deployment range; building defensively");
  }
}

if (!previousSha) {
  const baseBranches = ["golden-with-speed-insights", "codex/fair-odds-daily-pitch-20260908"];
  // New feature branches have no previous successful preview. Fetch their two
  // maintained bases rather than assuming the last commit represents the PR.
  if (process.env.VERCEL === "1") {
    try {
      git("fetch", "--no-tags", "--depth=200", "origin", ...baseBranches.map(
        (branch) => `+refs/heads/${branch}:refs/remotes/origin/${branch}`,
      ));
    } catch {
      build("cannot refresh first-preview bases; building defensively");
    }
  }
  const bases = [];
  for (const branch of baseBranches) {
    try {
      bases.push(git("merge-base", currentSha, `refs/remotes/origin/${branch}`).trim());
    } catch { /* Unknown bases are never replaced with a last-commit guess. */ }
  }
  if (bases.length === 0) build("no verified first-preview base; building defensively");
  let base = bases[0];
  for (const candidate of bases.slice(1)) {
    try {
      git("merge-base", "--is-ancestor", base, candidate);
      base = candidate;
    } catch {
      try { git("merge-base", "--is-ancestor", candidate, base); }
      catch { build("ambiguous first-preview bases; building defensively"); }
    }
  }
  try {
    changedFiles = changedSince(base);
    log(`first preview: checking all changes since ${base.slice(0, 12)}`);
  } catch {
    build("cannot verify first-preview change range; building defensively");
  }
}

if (changedFiles.length === 0) {
  build("no changed files detected; building defensively");
}

const SKIP_PATTERNS = [
  // Aerial state is published to Blob by the existing football worker.
  /^data\/aerial\//,
  /^public\/fair-odds-lab\/aerial\.json$/,
  /^scripts\/(aerial_data|aerial_source|refresh-aerial)\.py$/,
  // Offline Python jobs and their tests run on the model worker/GitHub, not in
  // Next.js. Their generated public assets still build when those assets change.
  // Do not widen this to all scripts: prebuild audits, asset generators and the
  // downloadable goalscorer/tennis review packs are website dependencies.
  /^scripts\/(goalkeeper[-_]|team[-_]shots[-_])[a-z0-9_-]+\.py$/,
  /^scripts\/(football-count(s)?-|football_count)[a-z0-9_-]+\.py$/,
  /^scripts\/(backfill|fit|publish|run)-football-vnext-[a-z0-9-]+\.py$/,
  /^scripts\/(capture-api-football-counts|probe-odds-api-goalkeeper-saves|reconcile-team-shots-sources|weekly-research-report|tennis_ml_research_v1)\.py$/,
  /^scripts\/tests\/test_[a-z0-9_]+\.py$/,
  /^config\/model-review-watchlist\.json$/,
  /^outputs\/model-reviews\//,

  // Goalscorer live polling artifacts. Fair Odds Lab reads Blob first; these
  // committed files are fallback/live-monitor artifacts and should not rebuild
  // the app on every poll.
  /^public\/fair-odds-lab\/(signals|highlights)\.json$/,
  /^data\/goalscorer\/all-leagues-live-board\.json$/,
  /^data\/goalscorer\/goalscorer-live-(snapshot|status|schedule-state)\.json$/,
  /^data\/goalscorer\/goalscorer-match-status\.json$/,
  /^data\/goalscorer\/goalscorer-monitor-snapshot\.json$/,
  /^data\/goalscorer\/confirmed-lineups\.json$/,
  /^data\/goalscorer\/goalscorer-odds-history\.csv$/,
  /^data\/goalscorer\/goalscorer-live-comparison\.(csv|txt)$/,
  /^data\/goalscorer\/penalty-duty-context\.json$/,
  /^data\/goalscorer\/(epl|serie-a|la-liga|bundesliga|ligue-1)-confirmed-lineups\.json$/,
  /^data\/goalscorer\/([a-z0-9-]+-)?(public|shadow)-(signals\.csv|performance\.txt)$/,
  /^data\/goalscorer\/(epl|serie-a|la-liga|bundesliga|ligue-1)\/(live-board\.json|penalty-duty-context\.json|goalscorer-live-comparison\.(csv|txt))$/,
  /^data\/goalscorer\/(epl|serie-a|la-liga|bundesliga|ligue-1)\/live-history\//,
  /^data\/goalscorer\/live-board\.json$/,
  /^data\/goalscorer\/live-history\//,
  /^data\/goalscorer\/inbox\//,
  /^data\/assist-value\/(assist-value-model-report\.txt|assist-value-shadow-signals\.csv)$/,

  // Corners, team-shots and hosted monitor artifacts.
  /^data\/corners-ou\//,
  /^data\/football-form\//,
  /^data\/goalkeeper-saves\//,
  /^data\/team-shots\/inbox\//,
  /^data\/team-shots\/team-shots-live-snapshot\.json$/,
  /^data\/team-shots\/team-shots-odds-history\.csv$/,
  /^data\/team-shots\/shadow\/settlement-audit.*\.json$/,
  /^data\/team-shots\/shadow\/team-shots-shadow-(signals.*\.csv|performance.*\.txt)$/,
  /^data\/shortlist\//,

  /^data\/goalscorer\/fair-odds-lab-(epl|serie-a|la-liga|bundesliga|ligue-1)-(signals\.csv|performance\.txt)$/,

  // Local research captures and review tickets do not change published pages.
  // Public penalty-takers/season/evidence files are deliberately NOT skipped.
  /^data\/tennis-props\/inbox\//,
  /^data\/team-shots\/match-shots-odds-history\.csv$/,
  /^data\/team-shots\/team-shots-scrape-last-run\.json$/,
  /^data\/goalscorer\/((epl|serie-a|la-liga|bundesliga|ligue-1)-)?penalty-(baseline-evidence\.json|duty-(live-)?review\.(json|csv))$/,
  /^data\/assist-value\/assist-market-audit-[a-z-]+\.csv$/,
  /^data\/assist-value\/assist-value-shadow-(board\.csv|performance\.txt|report\.txt)$/,
  /^data\/assist-value\/fpl-setpiece-roles\.csv$/,
  /^data\/assist-value\/research\//,

  // Results snapshots and Fair Odds Lab live highlight archives.
  /^data\/results-snapshot\//,
  /^data\/fair-odds-lab\/highlights\//,

  // Tennis signal/performance logs. Calibration/config JSON is intentionally
  // not skipped because it may become build-relevant through static imports.
  /^data\/backtest\/strict-signals-.*-(live|archive)\.csv$/,
  /^data\/backtest\/strict-clv-audit.*\.(csv|txt)$/,
  /^data\/backtest\/strict-policy-performance-.*\.csv$/,
];

function isSkippable(file) {
  return SKIP_PATTERNS.some((pattern) => pattern.test(file));
}

const buildRelevantFiles = changedFiles.filter((file) => !isSkippable(file));

if (buildRelevantFiles.length === 0) {
  skip(`all ${changedFiles.length} changed path(s) are live-data artifacts or offline model maintenance; skipping build`);
}

log("building due to:", buildRelevantFiles.slice(0, 12).join(", "));
if (buildRelevantFiles.length > 12) {
  log(`and ${buildRelevantFiles.length - 12} more build-relevant path(s)`);
}
process.exit(1);

