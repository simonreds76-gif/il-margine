import path from "node:path";

const KNOWN_PROJECT_FILE_PATHS = {
  "data/backtest/clay-prob-calibration.json": path.join(process.cwd(), "data/backtest/clay-prob-calibration.json"),
  "data/backtest/policy-profile-backtest-2022-2025.txt": path.join(process.cwd(), "data/backtest/policy-profile-backtest-2022-2025.txt"),
  "data/backtest/shadow-profile-comparison.txt": path.join(process.cwd(), "data/backtest/shadow-profile-comparison.txt"),
  "data/backtest/strict-clv-audit-2026.txt": path.join(process.cwd(), "data/backtest/strict-clv-audit-2026.txt"),
  "data/backtest/strict-clv-audit-volume200-2026.txt": path.join(process.cwd(), "data/backtest/strict-clv-audit-volume200-2026.txt"),
  "data/backtest/strict-policy-performance-clay2026-weekly.csv": path.join(process.cwd(), "data/backtest/strict-policy-performance-clay2026-weekly.csv"),
  "data/backtest/strict-policy-performance-spreadshadow-weekly.csv": path.join(process.cwd(), "data/backtest/strict-policy-performance-spreadshadow-weekly.csv"),
  "data/backtest/strict-policy-performance-volume200-weekly.csv": path.join(process.cwd(), "data/backtest/strict-policy-performance-volume200-weekly.csv"),
  "data/backtest/strict-policy-performance-weekly.csv": path.join(process.cwd(), "data/backtest/strict-policy-performance-weekly.csv"),
  "data/backtest/strict-signals-claycal.csv": path.join(process.cwd(), "data/backtest/strict-signals-claycal.csv"),
  "data/backtest/strict-signals-spreadshadow.csv": path.join(process.cwd(), "data/backtest/strict-signals-spreadshadow.csv"),
  "data/backtest/strict-signals-volume200.csv": path.join(process.cwd(), "data/backtest/strict-signals-volume200.csv"),
  "data/backtest/strict-signals.csv": path.join(process.cwd(), "data/backtest/strict-signals.csv"),
  "data/backtest/tournament-segment-roi.csv": path.join(process.cwd(), "data/backtest/tournament-segment-roi.csv"),
  "data/goalscorer/bundesliga-penalty-duty-review.json": path.join(process.cwd(), "data/goalscorer/bundesliga-penalty-duty-review.json"),
  "data/goalscorer/bundesliga-penalty-duty-live-review.json": path.join(process.cwd(), "data/goalscorer/bundesliga-penalty-duty-live-review.json"),
  "data/goalscorer/bundesliga-confirmed-lineups.json": path.join(process.cwd(), "data/goalscorer/bundesliga-confirmed-lineups.json"),
  "data/goalscorer/bundesliga-public-signals.csv": path.join(process.cwd(), "data/goalscorer/bundesliga-public-signals.csv"),
  "data/goalscorer/bundesliga-shadow-signals.csv": path.join(process.cwd(), "data/goalscorer/bundesliga-shadow-signals.csv"),
  "data/goalscorer/bundesliga-penalty-takers.json": path.join(process.cwd(), "data/goalscorer/bundesliga-penalty-takers.json"),
  "data/goalscorer/bundesliga/goalscorer-live-comparison.csv": path.join(process.cwd(), "data/goalscorer/bundesliga/goalscorer-live-comparison.csv"),
  "data/goalscorer/bundesliga/goalscorer-live-comparison.txt": path.join(process.cwd(), "data/goalscorer/bundesliga/goalscorer-live-comparison.txt"),
  "data/goalscorer/bundesliga/live-board.json": path.join(process.cwd(), "data/goalscorer/bundesliga/live-board.json"),
  "data/goalscorer/confirmed-lineups.json": path.join(process.cwd(), "data/goalscorer/confirmed-lineups.json"),
  "data/goalscorer/epl-penalty-duty-review.json": path.join(process.cwd(), "data/goalscorer/epl-penalty-duty-review.json"),
  "data/goalscorer/epl-penalty-duty-live-review.json": path.join(process.cwd(), "data/goalscorer/epl-penalty-duty-live-review.json"),
  "data/goalscorer/epl-confirmed-lineups.json": path.join(process.cwd(), "data/goalscorer/epl-confirmed-lineups.json"),
  "data/goalscorer/epl-public-signals.csv": path.join(process.cwd(), "data/goalscorer/epl-public-signals.csv"),
  "data/goalscorer/epl-shadow-signals.csv": path.join(process.cwd(), "data/goalscorer/epl-shadow-signals.csv"),
  "data/goalscorer/epl-penalty-takers.json": path.join(process.cwd(), "data/goalscorer/epl-penalty-takers.json"),
  "data/goalscorer/epl/goalscorer-live-comparison.csv": path.join(process.cwd(), "data/goalscorer/epl/goalscorer-live-comparison.csv"),
  "data/goalscorer/epl/goalscorer-live-comparison.txt": path.join(process.cwd(), "data/goalscorer/epl/goalscorer-live-comparison.txt"),
  "data/goalscorer/epl/live-board.json": path.join(process.cwd(), "data/goalscorer/epl/live-board.json"),
  "data/goalscorer/goalscorer-live-comparison.csv": path.join(process.cwd(), "data/goalscorer/goalscorer-live-comparison.csv"),
  "data/goalscorer/goalscorer-live-comparison.txt": path.join(process.cwd(), "data/goalscorer/goalscorer-live-comparison.txt"),
  "data/goalscorer/goalscorer-public-signals.csv": path.join(process.cwd(), "data/goalscorer/goalscorer-public-signals.csv"),
  "data/goalscorer/goalscorer-shadow-signals.csv": path.join(process.cwd(), "data/goalscorer/goalscorer-shadow-signals.csv"),
  "data/goalscorer/la-liga-penalty-duty-live-review.json": path.join(process.cwd(), "data/goalscorer/la-liga-penalty-duty-live-review.json"),
  "data/goalscorer/la-liga-confirmed-lineups.json": path.join(process.cwd(), "data/goalscorer/la-liga-confirmed-lineups.json"),
  "data/goalscorer/la-liga-public-signals.csv": path.join(process.cwd(), "data/goalscorer/la-liga-public-signals.csv"),
  "data/goalscorer/la-liga-shadow-signals.csv": path.join(process.cwd(), "data/goalscorer/la-liga-shadow-signals.csv"),
  "data/goalscorer/la-liga-penalty-takers.json": path.join(process.cwd(), "data/goalscorer/la-liga-penalty-takers.json"),
  "data/goalscorer/la-liga/goalscorer-live-comparison.csv": path.join(process.cwd(), "data/goalscorer/la-liga/goalscorer-live-comparison.csv"),
  "data/goalscorer/la-liga/goalscorer-live-comparison.txt": path.join(process.cwd(), "data/goalscorer/la-liga/goalscorer-live-comparison.txt"),
  "data/goalscorer/la-liga/live-board.json": path.join(process.cwd(), "data/goalscorer/la-liga/live-board.json"),
  "data/goalscorer/ligue-1-penalty-duty-review.json": path.join(process.cwd(), "data/goalscorer/ligue-1-penalty-duty-review.json"),
  "data/goalscorer/ligue-1-penalty-duty-live-review.json": path.join(process.cwd(), "data/goalscorer/ligue-1-penalty-duty-live-review.json"),
  "data/goalscorer/ligue-1-confirmed-lineups.json": path.join(process.cwd(), "data/goalscorer/ligue-1-confirmed-lineups.json"),
  "data/goalscorer/ligue-1-public-signals.csv": path.join(process.cwd(), "data/goalscorer/ligue-1-public-signals.csv"),
  "data/goalscorer/ligue-1-shadow-signals.csv": path.join(process.cwd(), "data/goalscorer/ligue-1-shadow-signals.csv"),
  "data/goalscorer/ligue-1-penalty-takers.json": path.join(process.cwd(), "data/goalscorer/ligue-1-penalty-takers.json"),
  "data/goalscorer/ligue-1/goalscorer-live-comparison.csv": path.join(process.cwd(), "data/goalscorer/ligue-1/goalscorer-live-comparison.csv"),
  "data/goalscorer/ligue-1/goalscorer-live-comparison.txt": path.join(process.cwd(), "data/goalscorer/ligue-1/goalscorer-live-comparison.txt"),
  "data/goalscorer/ligue-1/live-board.json": path.join(process.cwd(), "data/goalscorer/ligue-1/live-board.json"),
  "data/goalscorer/live-board.json": path.join(process.cwd(), "data/goalscorer/live-board.json"),
  "data/goalscorer/penalty-duty-review.json": path.join(process.cwd(), "data/goalscorer/penalty-duty-review.json"),
  "data/goalscorer/penalty-duty-live-review.json": path.join(process.cwd(), "data/goalscorer/penalty-duty-live-review.json"),
  "data/goalscorer/serie-a-penalty-takers.json": path.join(process.cwd(), "data/goalscorer/serie-a-penalty-takers.json"),
  "data/goalscorer/team-logo-map.json": path.join(process.cwd(), "data/goalscorer/team-logo-map.json"),
  "data/injured-players-tennisexplorer.csv": path.join(process.cwd(), "data/injured-players-tennisexplorer.csv"),
  "scripts/build-penalty-baseline-evidence.py": path.join(process.cwd(), "scripts/build-penalty-baseline-evidence.py"),
  "scripts/class_gap.py": path.join(process.cwd(), "scripts/class_gap.py"),
  "scripts/compute-handicap-values.py": path.join(process.cwd(), "scripts/compute-handicap-values.py"),
  "scripts/fotmob-fetch-lineups.py": path.join(process.cwd(), "scripts/fotmob-fetch-lineups.py"),
  "scripts/goalscorer-live-compare.py": path.join(process.cwd(), "scripts/goalscorer-live-compare.py"),
  "scripts/goalscorer-live-penalty-review.py": path.join(process.cwd(), "scripts/goalscorer-live-penalty-review.py"),
  "scripts/goalscorer-model.py": path.join(process.cwd(), "scripts/goalscorer-model.py"),
  "scripts/goalscorer-penalty-review.py": path.join(process.cwd(), "scripts/goalscorer-penalty-review.py"),
  "scripts/goalscorer_penalty_utils.py": path.join(process.cwd(), "scripts/goalscorer_penalty_utils.py"),
  "scripts/goalscorer-shadow-tracker.py": path.join(process.cwd(), "scripts/goalscorer-shadow-tracker.py"),
  "scripts/oncourt-compute-fair-odds.py": path.join(process.cwd(), "scripts/oncourt-compute-fair-odds.py"),
  "scripts/run-goalscorer-pipeline.py": path.join(process.cwd(), "scripts/run-goalscorer-pipeline.py"),
  "scripts/shrinkage_v2.py": path.join(process.cwd(), "scripts/shrinkage_v2.py"),
  "src/app/model-monitor/goalscorer/page.tsx": path.join(process.cwd(), "src/app/model-monitor/goalscorer/page.tsx"),
  "src/lib/goalscorer-live-files.ts": path.join(process.cwd(), "src/lib/goalscorer-live-files.ts"),
  "src/lib/tennis_prob.py": path.join(process.cwd(), "src/lib/tennis_prob.py"),
} as const;

export type KnownProjectFile = keyof typeof KNOWN_PROJECT_FILE_PATHS;

function isKnownProjectFile(relativePath: string): relativePath is KnownProjectFile {
  return relativePath in KNOWN_PROJECT_FILE_PATHS;
}

export function tryGetKnownProjectFilePath(relativePath: string): string | null {
  if (!isKnownProjectFile(relativePath)) return null;
  return KNOWN_PROJECT_FILE_PATHS[relativePath];
}

export function getKnownProjectFilePath(relativePath: KnownProjectFile): string {
  return KNOWN_PROJECT_FILE_PATHS[relativePath];
}

export function resolveConfiguredProjectFilePath(
  configuredPath: string | undefined,
  fallbackPath: KnownProjectFile,
): string {
  const trimmed = configuredPath?.trim();
  if (trimmed) {
    const knownPath = tryGetKnownProjectFilePath(trimmed);
    if (knownPath) return knownPath;
    if (path.isAbsolute(trimmed)) return trimmed;
  }
  return getKnownProjectFilePath(fallbackPath);
}
