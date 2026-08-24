/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/api/router/:path*', destination: `${process.env.ROUTER_URL || 'http://localhost:9080'}/:path*` },
      { source: '/api/mind/:path*', destination: `${process.env.MIND_URL || 'http://localhost:9081'}/:path*` },
      { source: '/api/agents/:path*', destination: `${process.env.AGENTS_URL || 'http://localhost:9082'}/:path*` },
      { source: '/api/sentinel/:path*', destination: `${process.env.SENTINEL_URL || 'http://localhost:9083'}/:path*` },
    ];
  },
};

export default nextConfig;
