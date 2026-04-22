/** @type {import('next').NextConfig} */
/*
 * We deliberately do NOT use Next's `rewrites()` to proxy /api/* to
 * the FastAPI backend. Its dev-server proxy buffers responses and
 * chokes on long-lived SSE connections (socket hang up after the
 * first query). The frontend calls the backend directly via
 * NEXT_PUBLIC_ANAMNESA_API, and the backend's CORS middleware allows
 * localhost:3000 in dev. In production, put Caddy in front of both.
 */
const nextConfig = {};

module.exports = nextConfig;
