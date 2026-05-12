#!/usr/bin/env node
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

if (!previousSha) {
  build("VERCEL_GIT_PREVIOUS_SHA missing; building defensively");
}

let changedFiles = [];
try {
  changedFiles = execFileSync("git", ["diff", "--name-only", previousSha, currentSha], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  })
    .split(/\r?\n/)
    .map((file) => file.trim().replaceAll("\\", "/"))
    .filter(Boolean);
} catch (error) {
  build(`git diff failed; building defensively: ${error.message}`);
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
  /^data\/goalscorer\/goalscorer-monitor-snapshot\.json$/,
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

  // Corners, team-shots and hosted monitor artifacts.
  /^data\/corners-ou\//,
  /^data\/football-form\//,
  /^data\/team-shots\/team-shots-live-snapshot\.json$/,
  /^data\/team-shots\/shadow\/settlement-audit.*\.json$/,
  /^data\/team-shots\/shadow\/team-shots-shadow-(signals.*\.csv|performance.*\.txt)$/,
  /^data\/shortlist\//,

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
  skip(`all ${changedFiles.length} changed path(s) are live-data artifacts; skipping build`);
}

log("building due to:", buildRelevantFiles.slice(0, 12).join(", "));
if (buildRelevantFiles.length > 12) {
  log(`and ${buildRelevantFiles.length - 12} more build-relevant path(s)`);
}
process.exit(1);
