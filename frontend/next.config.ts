import type { NextConfig } from "next";

const internalApiBase = process.env.INTERNAL_API_BASE ?? "http://backend:8000/api/v1";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${internalApiBase}/:path*`
      }
    ];
  }
};

export default nextConfig;
