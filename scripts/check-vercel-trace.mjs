import fs from "node:fs";
import path from "node:path";

const tracePath = path.join(
  process.cwd(),
  ".next",
  "server",
  "app",
  "api",
  "fair-odds",
  "route.js.nft.json",
);

const forbiddenPrefixes = [
  "data/goalscorer/",
  "data/corners-ou/",
  "data/team-shots/",
  "data/shortlist/",
  "data/exports/",
  "data/results-snapshot/",
  "data/sackmann/",
];

const forbiddenFiles = [
  "data/oncourt/games_atp.csv",
  "data/oncourt/stat_atp.csv",
  "data/oncourt/categories_atp.csv",
  "data/oncourt/players_atp.csv",
  "data/oncourt/tours_atp.csv",
];

const maxFairOddsTraceFiles = Number.parseInt(
  process.env.MAX_FAIR_ODDS_TRACE_FILES || "1500",
  10,
);

function normalizeTraceFile(file) {
  let normalized = String(file || "").replaceAll("\\", "/");
  normalized = normalized.replace(/^(\.\.\/)+/, "");
  normalized = normalized.replace(/^\.\/+/, "");
  return normalized;
}

function isForbidden(file) {
  return (
    forbiddenPrefixes.some((prefix) => file.startsWith(prefix)) ||
    forbiddenFiles.includes(file)
  );
}

if (!fs.existsSync(tracePath)) {
  console.error(
    `[vercel-trace] Missing fair odds trace at ${path.relative(process.cwd(), tracePath)}. Run npm run build first.`,
  );
  process.exit(1);
}

const trace = JSON.parse(fs.readFileSync(tracePath, "utf8"));
const files = Array.isArray(trace.files) ? trace.files.map(normalizeTraceFile) : [];
const forbiddenMatches = files.filter(isForbidden).sort();

if (forbiddenMatches.length > 0) {
  console.error("[vercel-trace] /api/fair-odds is tracing forbidden large data files:");
  for (const file of forbiddenMatches.slice(0, 40)) {
    console.error(`  - ${file}`);
  }
  if (forbiddenMatches.length > 40) {
    console.error(`  ... plus ${forbiddenMatches.length - 40} more`);
  }
  console.error("[vercel-trace] Fix next.config.ts outputFileTracingExcludes or remove the broad filesystem read.");
  process.exit(1);
}

if (Number.isFinite(maxFairOddsTraceFiles) && files.length > maxFairOddsTraceFiles) {
  console.error(
    `[vercel-trace] /api/fair-odds trace has ${files.length} files, above limit ${maxFairOddsTraceFiles}.`,
  );
  console.error("[vercel-trace] This usually means a broad data/ scan slipped back in.");
  process.exit(1);
}

console.log(`[vercel-trace] /api/fair-odds trace OK (${files.length} files).`);

const tennisTracePath = path.join(
  process.cwd(),
  ".next",
  "server",
  "app",
  "model-monitor",
  "tennis",
  "page.js.nft.json",
);
const tennisForbiddenPrefixes = [
  "data/assist-value/",
  "data/corners-ou/",
  "data/exports/",
  "data/football-form/",
  "data/goalkeeper-saves/",
  "data/goalscorer/",
  "data/oncourt/",
  "data/results-snapshot/",
  "data/sackmann/",
  "data/shortlist/",
  "data/team-shots/",
  "data/tennis-props/",
  "scripts/",
  "tml-data/",
];
const tennisAllowedFiles = new Set(["data/goalscorer/team-logo-map.json"]);
const maxTennisMonitorTraceFiles = Number.parseInt(
  process.env.MAX_TENNIS_MONITOR_TRACE_FILES || "200",
  10,
);

if (!fs.existsSync(tennisTracePath)) {
  console.error(
    `[vercel-trace] Missing tennis monitor trace at ${path.relative(process.cwd(), tennisTracePath)}. Run npm run build first.`,
  );
  process.exit(1);
}

const tennisTrace = JSON.parse(fs.readFileSync(tennisTracePath, "utf8"));
const tennisFiles = Array.isArray(tennisTrace.files)
  ? tennisTrace.files.map(normalizeTraceFile)
  : [];
const tennisForbiddenMatches = tennisFiles
  .filter((file) => !tennisAllowedFiles.has(file))
  .filter((file) => tennisForbiddenPrefixes.some((prefix) => file.startsWith(prefix)))
  .sort();

if (tennisForbiddenMatches.length > 0) {
  console.error("[vercel-trace] /model-monitor/tennis is tracing unrelated model data:");
  for (const file of tennisForbiddenMatches.slice(0, 40)) console.error(`  - ${file}`);
  process.exit(1);
}

if (
  Number.isFinite(maxTennisMonitorTraceFiles) &&
  tennisFiles.length > maxTennisMonitorTraceFiles
) {
  console.error(
    `[vercel-trace] /model-monitor/tennis trace has ${tennisFiles.length} files, above limit ${maxTennisMonitorTraceFiles}.`,
  );
  process.exit(1);
}

console.log(
  `[vercel-trace] /model-monitor/tennis trace OK (${tennisFiles.length} files).`,
);
