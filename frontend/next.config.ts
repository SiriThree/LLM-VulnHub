import type { NextConfig } from "next";

const internalApiBase = process.env.INTERNAL_API_BASE ?? "http://backend:8000/api/v1";

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
          },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
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
