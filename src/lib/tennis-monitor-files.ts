export type TennisResearchLaneId =
  | "hard_bo3"
  | "clay_bo3"
  | "slam_bo5"
  | "challenger_ml"
  | "indoor_bo3"
  | "grass_bo3"
  | "cpi_speed_shadow"
  | "challenger_hc";

export type TennisMonitorFilePath = string | string[];

export type TennisMonitorFileGroup = {
  label: string;
  calibration?: TennisMonitorFilePath;
  live?: TennisMonitorFilePath;
  archive?: TennisMonitorFilePath;
  nearMiss?: TennisMonitorFilePath;
  performance?: TennisMonitorFilePath;
  clvAuditCsv?: TennisMonitorFilePath;
  clvAuditTxt?: TennisMonitorFilePath;
  clvAuditSpreadCsv?: TennisMonitorFilePath;
  clvAuditSpreadTxt?: TennisMonitorFilePath;
};

export const TENNIS_RESEARCH_LANES: TennisResearchLaneId[] = [
  "hard_bo3",
  "clay_bo3",
  "slam_bo5",
  "challenger_ml",
  "indoor_bo3",
  "grass_bo3",
  "cpi_speed_shadow",
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
    clvAuditCsv: "data/backtest/strict-clv-audit-2026.csv",
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
    label: "Slam BO5 handicap evidence",
    live: "data/backtest/strict-signals-slam-bo5-live.csv",
    archive: "data/backtest/strict-signals-slam-bo5-archive.csv",
    performance: "data/backtest/strict-policy-performance-slam-bo5-weekly.csv",
    clvAuditCsv: "data/backtest/strict-clv-audit-slam-bo5-2026.csv",
    clvAuditTxt: "data/backtest/strict-clv-audit-slam-bo5-2026.txt",
  },
  challenger_ml: {
    label: "Challenger ML v2 tracker",
    calibration: "data/backtest/calibration/challenger-ml-calibration.json",
    live: "data/backtest/strict-signals-challenger-ml-v2-live.csv",
    archive: "data/backtest/strict-signals-challenger-ml-v2-archive.csv",
    nearMiss: "data/backtest/challenger-ml-v2-nearmiss.csv",
    performance: "data/backtest/strict-policy-performance-challenger-ml-v2-weekly.csv",
    clvAuditCsv: "data/backtest/strict-clv-audit-challenger-ml-v2-2026.csv",
    clvAuditTxt: "data/backtest/strict-clv-audit-challenger-ml-v2-2026.txt",
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
  cpi_speed_shadow: {
    label: "CPI speed shadow",
    live: [
      "data/backtest/strict-signals-cpi_speed-live.csv",
      "data/backtest/strict-signals-cpi_speed.csv",
    ],
    archive: [
      "data/backtest/strict-signals-cpi_speed-archive.csv",
      "data/backtest/strict-signals-cpi_speed.csv",
    ],
    nearMiss: "data/backtest/cpi_speed-shadow-nearmiss.csv",
    performance: "data/backtest/strict-policy-performance-cpi_speed-weekly.csv",
    clvAuditCsv: "data/backtest/strict-clv-audit-cpi_speed-2026.csv",
    clvAuditTxt: "data/backtest/strict-clv-audit-cpi_speed-2026.txt",
  },
  challenger_hc: {
    label: "Challenger HC",
  },
};

