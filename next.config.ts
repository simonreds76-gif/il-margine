import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
