import { afterEach, describe, expect, it, vi } from "vitest";
import { clearRuntimeConfigForTests, getRuntimeConfig } from "@/lib/runtime-config";

describe("runtime config", () => {
  afterEach(() => {
    clearRuntimeConfigForTests();
    delete window.__SLV_RUNTIME_CONFIG__;
    delete window.__TAURI__;
    vi.restoreAllMocks();
  });

  it("falls back to local browser defaults", async () => {
    await expect(getRuntimeConfig()).resolves.toMatchObject({
      apiBaseUrl: "http://localhost:8000",
      desktopMode: false,
    });
  });

  it("uses injected desktop config when available", async () => {
    window.__SLV_RUNTIME_CONFIG__ = {
      apiBaseUrl: "http://127.0.0.1:49152/",
      appDataDir: "C:/Users/demo/AppData/Roaming/Self-Learning Vision",
      databaseMode: "sqlite",
      providerMode: "local",
      desktopMode: true,
    };

    await expect(getRuntimeConfig()).resolves.toMatchObject({
      apiBaseUrl: "http://127.0.0.1:49152",
      databaseMode: "sqlite",
      providerMode: "local",
      desktopMode: true,
    });
  });
});
