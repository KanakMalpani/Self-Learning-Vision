import { spawn } from "node:child_process";

const baseUrl = "http://localhost:3000";

function spawnProcess(command, args, options = {}) {
  return spawn(command, args, {
    stdio: "inherit",
    ...options,
  });
}

async function waitForServer(timeoutMs = 120_000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(baseUrl);
      if (response.ok || response.status < 500) {
        return;
      }
    } catch {
      // Wait until the standalone server accepts connections.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${baseUrl}`);
}

function runPlaywright() {
  return new Promise((resolve) => {
    const child = spawnProcess("node", ["node_modules/@playwright/test/cli.js", "test"], {
      env: {
        ...process.env,
        PLAYWRIGHT_EXTERNAL_SERVER: "true",
      },
    });
    child.on("close", (code) => resolve(code ?? 1));
  });
}

const server = spawnProcess("node", [".next/standalone/server.js"], {
  env: {
    ...process.env,
    PORT: "3000",
    NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000",
    NEXT_PUBLIC_AUTH_ENABLED: "false",
  },
});

let exitCode = 1;
try {
  await waitForServer();
  exitCode = await runPlaywright();
} finally {
  server.kill();
}

process.exit(exitCode);
