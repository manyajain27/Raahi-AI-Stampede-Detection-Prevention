/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/planner/:path*',
        destination: 'http://localhost:5000/api/:path*',
      },
      {
        source: '/api/visualizer/:path*',
        destination: 'http://localhost:5001/api/:path*',
      },
      {
        source: '/planner',
        destination: 'http://localhost:5000/',
      },
      {
        source: '/planner/outdoor',
        destination: 'http://localhost:5000/outdoor',
      },
    ];
  },
};

export default nextConfig;
