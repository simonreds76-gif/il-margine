import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
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
