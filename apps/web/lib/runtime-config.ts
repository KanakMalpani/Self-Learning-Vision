"use client";

export type RuntimeConfig = {
  apiBaseUrl: string;
  appVersion: string;
  appDataDir: string;
  databaseMode: string;
  providerMode: string;
  desktopMode: boolean;
};

const fallbackConfig: RuntimeConfig = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  appVersion: process.env.NEXT_PUBLIC_APP_VERSION || "dev",
  appDataDir: "",
  databaseMode: "configured",
  providerMode: process.env.NEXT_PUBLIC_EMBEDDING_PROVIDER || "auto",
  desktopMode: false,
};

let cachedConfig: RuntimeConfig | null = null;
let configPromise: Promise<RuntimeConfig> | null = null;

type TauriGlobal = {
  core?: {
    invoke?: <T>(command: string) => Promise<T>;
  };
};

declare global {
  interface Window {
    __SLV_RUNTIME_CONFIG__?: Partial<RuntimeConfig>;
    __TAURI__?: TauriGlobal;
  }
}

function normalizeConfig(payload: Partial<RuntimeConfig> | null | undefined): RuntimeConfig {
  return {
    ...fallbackConfig,
    ...(payload || {}),
    apiBaseUrl: (payload?.apiBaseUrl || fallbackConfig.apiBaseUrl).replace(/\/$/, ""),
  };
}

export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  if (cachedConfig) return cachedConfig;
  if (configPromise) return configPromise;

  configPromise = (async () => {
    if (typeof window === "undefined") {
      cachedConfig = normalizeConfig(null);
      return cachedConfig;
    }

    if (window.__SLV_RUNTIME_CONFIG__) {
      cachedConfig = normalizeConfig(window.__SLV_RUNTIME_CONFIG__);
      return cachedConfig;
    }

    const invoke = window.__TAURI__?.core?.invoke;
    if (invoke) {
      try {
        cachedConfig = normalizeConfig(await invoke<Partial<RuntimeConfig>>("get_runtime_config"));
        return cachedConfig;
      } catch {
        // Browser fallback keeps Docker/local development usable.
      }
    }

    cachedConfig = normalizeConfig(null);
    return cachedConfig;
  })();

  return configPromise;
}

export function clearRuntimeConfigForTests(): void {
  cachedConfig = null;
  configPromise = null;
}
