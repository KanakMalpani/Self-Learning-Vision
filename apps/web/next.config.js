/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  experimental: {
    externalDir: true,
  },
};

module.exports = nextConfig;

