import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  // Exclude large tennis-model data files from serverless functions that don't need them.
  // dynamic fs.readFile calls (e.g. goalscorer match-results) cause Next.js to over-trace
  // the entire data/ tree, pulling in ~160 MB of unrelated oncourt/tml-data/sackmann files.
  outputFileTracingExcludes: {
    "/model-monitor/goalscorer": [
      "./data/oncourt/**",
      "./tml-data/**",
      "./data/sackmann/**",
      "./data/goalscorer/live-history/**",
      "./data/goalscorer/epl/**",
      "./data/goalscorer/la-liga/**",
      "./data/goalscorer/bundesliga/**",
      "./data/goalscorer/ligue-1/**",
      "./data/goalscorer/inbox/**",
      "./data/goalscorer/**/*player-match-logs*.csv",
      "./data/goalscorer/goalscorer-live-snapshot.json",
      "./data/goalscorer/all-leagues-live-board.json",
      "./data/goalscorer/live-board.json",
      "./data/goalscorer/goalscorer-odds-history.csv",
      "./data/team-shots/historical/**",
    ],
    "/api/model-monitor/goalscorer/penalty-watchlist": [
      "./data/oncourt/**",
      "./tml-data/**",
      "./data/sackmann/**",
      "./data/goalscorer/live-history/**",
      "./data/goalscorer/epl/**",
      "./data/goalscorer/la-liga/**",
      "./data/goalscorer/bundesliga/**",
      "./data/goalscorer/ligue-1/**",
      "./data/goalscorer/inbox/**",
      "./data/goalscorer/**/*player-match-logs*.csv",
      "./data/goalscorer/goalscorer-live-snapshot.json",
      "./data/goalscorer/all-leagues-live-board.json",
      "./data/goalscorer/live-board.json",
      "./data/goalscorer/goalscorer-odds-history.csv",
      "./data/team-shots/historical/**",
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
