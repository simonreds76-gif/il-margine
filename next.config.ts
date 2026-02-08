import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
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
};

export default nextConfig;
