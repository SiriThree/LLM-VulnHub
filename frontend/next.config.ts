import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const internalApiBase = process.env.INTERNAL_API_BASE ?? "http://localhost:8000/api/v1";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${internalApiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
