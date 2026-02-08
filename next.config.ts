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
  async headers() {
    return [
      { source: "/bookmakers", headers: [{ key: "Cache-Control", value: "no-store, max-age=0, must-revalidate" }] },
      { source: "/bookmakers/:path*", headers: [{ key: "Cache-Control", value: "no-store, max-age=0, must-revalidate" }] },
    ];
  },
};

export default nextConfig;
