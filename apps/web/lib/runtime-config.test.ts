import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clearRuntimeConfigForTests,
  getDesktopEngineStatus,
  getRuntimeConfig,
  restartDesktopEngine,
} from "@/lib/runtime-config";

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
      appDataDir: "/app-data/com.selflearningvision.desktop",
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

  it("refreshes a changed desktop sidecar URL", async () => {
    const invoke = vi
      .fn()
      .mockResolvedValueOnce({ apiBaseUrl: "http://127.0.0.1:49152", desktopMode: true })
      .mockResolvedValueOnce({ apiBaseUrl: "http://127.0.0.1:49153", desktopMode: true });
    window.__TAURI__ = { core: { invoke } };

    await expect(getRuntimeConfig()).resolves.toMatchObject({ apiBaseUrl: "http://127.0.0.1:49152" });
    await expect(getRuntimeConfig({ refresh: true })).resolves.toMatchObject({
      apiBaseUrl: "http://127.0.0.1:49153",
    });
  });

  it("exposes desktop engine status and restart commands", async () => {
    const invoke = vi.fn().mockImplementation((command: string) =>
      Promise.resolve({
        status: command === "restart_local_engine" ? "starting" : "ready",
        message: "Local engine ready.",
        attempt: 1,
        maxAttempts: 3,
      })
    );
    window.__TAURI__ = { core: { invoke } };

    await expect(getDesktopEngineStatus()).resolves.toMatchObject({ status: "ready" });
    await expect(restartDesktopEngine()).resolves.toMatchObject({ status: "starting" });
    expect(invoke).toHaveBeenCalledWith("get_engine_status");
    expect(invoke).toHaveBeenCalledWith("restart_local_engine");
  });
});
