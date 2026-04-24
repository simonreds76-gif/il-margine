import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  turbopack: {
    root: projectRoot,
  },
  // Keep unrelated tennis-model datasets out of the football monitor functions.
  // The goalscorer monitor now reads a compact snapshot payload instead of raw league trees.
  outputFileTracingExcludes: {
    "/api/fair-odds": [
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
