import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Exclude large tennis-model data files from serverless functions that don't need them.
  // dynamic fs.readFile calls (e.g. goalscorer match-results) cause Next.js to over-trace
  // the entire data/ tree, pulling in ~160 MB of unrelated oncourt/tml-data/sackmann files.
  outputFileTracingExcludes: {
    "/model-monitor/goalscorer": [
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
  async redirects() {
    return [
      {
        source: "/atp-tennis",
        destination: "/tennis-tips",
        permanent: true,
      },
    ];
  },
  async headers() {
    return [
      { source: "/bookmakers", headers: [{ key: "Cache-Control", value: "no-store, max-age=0, must-revalidate" }] },
      { source: "/bookmakers/:path*", headers: [{ key: "Cache-Control", value: "no-store, max-age=0, must-revalidate" }] },
    ];
  },
};

export default nextConfig;
