/** @type {import('next').NextConfig} */
const outputMode = process.env.NEXT_OUTPUT_MODE === 'export' ? 'export' : 'standalone';

const nextConfig = {
  output: outputMode,
  reactStrictMode: true,
  images: {
    unoptimized: outputMode === 'export',
  },
};

module.exports = nextConfig;

