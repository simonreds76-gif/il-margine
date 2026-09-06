#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Vercel Ignored Build Step.
 *
 * Vercel convention:
 *   exit 0 = skip this deployment build
 *   exit 1 = proceed with the build
 *
 * The rule is intentionally conservative: only known live-data artifact paths
 * are skipped. Any unknown path, source code, config, static import, or mixed
 * commit builds by default.
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
  return output
    .split(/\r?\n/)
    .map((file) => file.trim().replaceAll("\\", "/"))
    .filter(Boolean);
}

function readChangedFiles(args) {
  return parseFileList(
    execFileSync("git", args, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }),
  );
}

let changedFiles = [];
let usedSingleCommitFallback = false;
if (previousSha) {
  try {
    changedFiles = readChangedFiles(["diff", "--name-only", previousSha, currentSha]);
  } catch (error) {
    log(`initial git diff failed: ${error.message.split(/\r?\n/)[0]}`);

    if (commitRef) {
      try {
        execFileSync("git", ["fetch", "--no-tags", "--deepen=1000", "origin", commitRef], {
          encoding: "utf8",
          stdio: ["ignore", "pipe", "pipe"],
        });
        changedFiles = readChangedFiles(["diff", "--name-only", previousSha, currentSha]);
        log("diff succeeded after deepening Vercel's shallow checkout");
      } catch (fetchError) {
        log(`history deepen fallback failed: ${fetchError.message.split(/\r?\n/)[0]}`);
      }
    }
  }
} else {
  log("VERCEL_GIT_PREVIOUS_SHA missing; inspecting the current commit instead");
}

if (changedFiles.length === 0) {
  try {
    // Last resort for single-commit artifact pushes. This avoids rebuilding
    // known live-data commits just because Vercel did not clone enough history.
    changedFiles = readChangedFiles(["diff-tree", "--no-commit-id", "--name-only", "-r", currentSha]);
    usedSingleCommitFallback = true;
    log("using current-commit diff fallback because previous SHA is unavailable");
  } catch (treeError) {
    build(`git diff failed after fallbacks; building defensively: ${treeError.message}`);
  }
}

if (changedFiles.length === 0) {
  build("no changed files detected; building defensively");
}

const SKIP_PATTERNS = [
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
  if (usedSingleCommitFallback && !commitMessage.toLowerCase().startsWith("chore:")) {
    build("single-commit fallback only skips chore artifact commits; building defensively");
  }
  skip(`all ${changedFiles.length} changed path(s) are live-data artifacts; skipping build`);
}

log("building due to:", buildRelevantFiles.slice(0, 12).join(", "));
if (buildRelevantFiles.length > 12) {
  log(`and ${buildRelevantFiles.length - 12} more build-relevant path(s)`);
}
process.exit(1);
