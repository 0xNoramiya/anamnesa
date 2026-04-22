/** @type {import('next').NextConfig} */
const backend =
  process.env.NEXT_PUBLIC_ANAMNESA_API ?? "http://127.0.0.1:8000";

const nextConfig = {
  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the Next.js dev server
    // and the API are same-origin to the browser. No CORS games in dev.
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

module.exports = nextConfig;
