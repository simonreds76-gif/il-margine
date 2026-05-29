export type TennisResearchLaneId =
  | "hard_bo3"
  | "clay_bo3"
  | "slam_bo5"
  | "challenger_ml"
  | "indoor_bo3"
  | "grass_bo3"
  | "challenger_hc";

export type TennisMonitorFileGroup = {
  label: string;
  calibration?: string;
  live?: string;
  archive?: string;
  nearMiss?: string;
  performance?: string;
  clvAuditCsv?: string;
  clvAuditTxt?: string;
  clvAuditSpreadCsv?: string;
  clvAuditSpreadTxt?: string;
};

export const TENNIS_RESEARCH_LANES: TennisResearchLaneId[] = [
  "hard_bo3",
  "clay_bo3",
  "slam_bo5",
  "challenger_ml",
  "indoor_bo3",
  "grass_bo3",
  "challenger_hc",
];

export const TENNIS_LEGACY_DISABLED_LANES: TennisResearchLaneId[] = [];

export const TENNIS_MONITOR_FILES: Record<TennisResearchLaneId, TennisMonitorFileGroup> = {
  hard_bo3: {
    label: "Hard bo3",
    calibration: "data/backtest/calibration/_fallback.json",
    live: "data/backtest/strict-signals-live.csv",
    archive: "data/backtest/strict-signals-archive.csv",
    performance: "data/backtest/strict-policy-performance-weekly.csv",
    clvAuditTxt: "data/backtest/strict-clv-audit-2026.txt",
  },
  clay_bo3: {
    label: "Clay bo3",
    calibration: "data/backtest/calibration/clay-bo3-calibration.json",
    live: "data/backtest/strict-signals-clay_bo3-live.csv",
    archive: "data/backtest/strict-signals-clay_bo3-archive.csv",
    nearMiss: "data/backtest/clay_bo3-shadow-nearmiss.csv",
    performance: "data/backtest/strict-policy-performance-clay_bo3-weekly.csv",
    clvAuditCsv: "data/backtest/strict-clv-audit-clay_bo3-2026.csv",
    clvAuditTxt: "data/backtest/strict-clv-audit-clay_bo3-2026.txt",
    clvAuditSpreadCsv: "data/backtest/strict-clv-audit-clay_bo3-spread-2026.csv",
    clvAuditSpreadTxt: "data/backtest/strict-clv-audit-clay_bo3-spread-2026.txt",
  },
  slam_bo5: {
    label: "Slam bo5",
    calibration: "data/backtest/calibration/slam-bo5-calibration.json",
    live: "data/backtest/strict-signals-slam_bo5-live.csv",
    archive: "data/backtest/strict-signals-slam_bo5-archive.csv",
    nearMiss: "data/backtest/slam_bo5-shadow-nearmiss.csv",
    performance: "data/backtest/strict-policy-performance-slam_bo5-weekly.csv",
    clvAuditCsv: "data/backtest/strict-clv-audit-slam_bo5-2026.csv",
    clvAuditTxt: "data/backtest/strict-clv-audit-slam_bo5-2026.txt",
  },
  challenger_ml: {
    label: "Challenger ML tracker",
    calibration: "data/backtest/calibration/challenger-ml-calibration.json",
    live: "data/backtest/strict-signals-challenger-ml-live.csv",
    archive: "data/backtest/strict-signals-challenger-ml-archive.csv",
    nearMiss: "data/backtest/challenger-ml-shadow-nearmiss.csv",
    performance: "data/backtest/strict-policy-performance-challenger-ml-weekly.csv",
    clvAuditCsv: "data/backtest/strict-clv-audit-challenger-ml-2026.csv",
    clvAuditTxt: "data/backtest/strict-clv-audit-challenger-ml-2026.txt",
  },
  indoor_bo3: {
    label: "Indoor bo3",
    calibration: "data/backtest/calibration/indoor-bo3-calibration.json",
    live: "data/backtest/strict-signals-indoor_bo3-live.csv",
    archive: "data/backtest/strict-signals-indoor_bo3-archive.csv",
    nearMiss: "data/backtest/indoor_bo3-shadow-nearmiss.csv",
    performance: "data/backtest/strict-policy-performance-indoor_bo3-weekly.csv",
  },
  grass_bo3: {
    label: "Grass bo3",
    calibration: "data/backtest/calibration/grass-bo3-calibration.json",
    live: "data/backtest/strict-signals-grass_bo3-live.csv",
    archive: "data/backtest/strict-signals-grass_bo3-archive.csv",
    nearMiss: "data/backtest/grass_bo3-shadow-nearmiss.csv",
    performance: "data/backtest/strict-policy-performance-grass_bo3-weekly.csv",
  },
  challenger_hc: {
    label: "Challenger HC",
  },
};
