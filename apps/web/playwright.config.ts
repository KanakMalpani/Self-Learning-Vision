import { defineConfig, devices } from "@playwright/test";

const webServer = process.env.PLAYWRIGHT_EXTERNAL_SERVER === "true"
  ? undefined
  : {
      command: "node ./.next/standalone/server.js",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        PORT: "3000",
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000",
        NEXT_PUBLIC_AUTH_ENABLED: "false",
      },
    };

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer,
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
