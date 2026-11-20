/** @type {import('next').NextConfig} */
const outputMode = process.env.NEXT_OUTPUT_MODE === 'export' ? 'export' : 'standalone';

const nextConfig = {
  output: outputMode,
  reactStrictMode: true,
  // Next 16 blocks dev assets when the browser uses 127.0.0.1 instead of localhost.
  allowedDevOrigins: ["127.0.0.1"],
  images: {
    unoptimized: outputMode === 'export',
  },
};

module.exports = nextConfig;

