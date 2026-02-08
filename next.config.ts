import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  // No redirects: /atp-tennis is a real page with canonical to /tennis-tips so Google indexes content, not a redirect.
};

export default nextConfig;
