import type { NextConfig } from "next";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fs.realpathSync(path.dirname(fileURLToPath(import.meta.url)));
const require = createRequire(import.meta.url);
const nextInstallRoot = fs.realpathSync(path.dirname(path.dirname(path.dirname(require.resolve("next/package.json")))));
const relativeProjectRoot = path.relative(nextInstallRoot, projectRoot);
const projectInsideNextInstallRoot =
  relativeProjectRoot === "" || (!relativeProjectRoot.startsWith("..") && !path.isAbsolute(relativeProjectRoot));

const nextConfig: NextConfig = {
  turbopack: {
    root: projectInsideNextInstallRoot ? nextInstallRoot : projectRoot,
  },
  // Keep unrelated tennis-model datasets out of the football monitor functions.
  // The goalscorer monitor now reads a compact snapshot payload instead of raw league trees.
  outputFileTracingExcludes: {
    "/api/fair-odds": [
      "./data/**",
      "./public/**",
      "./data/goalscorer/**",
      "./data/corners-ou/**",
      "./data/team-shots/**",
      "./data/shortlist/**",
      "./data/exports/**",
      "./data/results-snapshot/**",
      "./data/sackmann/**",
      "./data/oncourt/games_atp.csv",
      "./data/oncourt/stat_atp.csv",
      "./data/oncourt/categories_atp.csv",
      "./data/oncourt/players_atp.csv",
      "./data/oncourt/tours_atp.csv",
    ],
    "/model-monitor/tennis": [
      "./data/assist-value/**",
      "./data/corners-ou/**",
      "./data/exports/**",
      "./data/football-form/**",
      "./data/goalkeeper-saves/**",
      "./data/goalscorer/**",
      "./data/oncourt/**",
      "./data/results-snapshot/**",
      "./data/sackmann/**",
      "./data/shortlist/**",
      "./data/team-shots/**",
      "./data/tennis-props/**",
      "./public/**",
      "./scripts/**",
      "./tml-data/**",
    ],
    "/model-monitor/goalscorer": [
      "./data/oncourt/**",
      "./tml-data/**",
      "./data/sackmann/**",
    ],
    "/model-monitor/goalscorer/lineups": [
      "./data/oncourt/**",
      "./tml-data/**",
      "./data/sackmann/**",
    ],
    "/api/model-monitor/goalscorer/penalty-watchlist": [
      "./data/oncourt/**",
      "./tml-data/**",
      "./data/sackmann/**",
    ],
  },
  outputFileTracingIncludes: {
    "/api/fair-odds": [
      "./data/backtest/calibration-params-2022-2026-review.json",
      "./data/backtest/strict-signals-spreadv1-live.csv",
      "./data/backtest/strict-signals-volume200-live.csv",
      "./data/backtest/strict-signals-challenger-ml-live.csv",
      "./data/backtest/challenger-ml-shadow-nearmiss.csv",
      "./data/backtest/strict-signals-clayv3-shadow-live.csv",
      "./data/backtest/strict-signals-clay_bo3-live.csv",
      "./data/backtest/tournament-segment-roi.csv",
      "./data/injured-players-tennisexplorer.csv",
      "./data/oncourt/today_atp.csv",
    ],
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "flagcdn.com",
      },
      {
        protocol: "https",
        hostname: "upload.wikimedia.org",
      },
    ],
  },
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          {
            key: "X-Robots-Tag",
            value: "noindex, nofollow, noarchive",
          },
        ],
      },
      {
        source: "/admin/:path*",
        headers: [
          {
            key: "X-Robots-Tag",
            value: "noindex, nofollow, noarchive",
          },
        ],
      },
    ];
  },
  // No redirects: /atp-tennis is a real page with canonical to /tennis-tips so Google indexes content, not a redirect.
  async rewrites() {
    return [
      // Bing Webmaster verification: serve XML with correct Content-Type at exact URL
      { source: "/BingSiteAuth.xml", destination: "/api/bing-auth" },
    ];
  },
};

export default nextConfig;
