import type {
  MemoryRunHistoryItem,
  MemoryRunRealtimeEventPayload,
  MemoryRunRealtimeEventType,
} from "@/types/memory";
import { getMemoryRunStreamUrlWithCursor } from "@/lib/api-client";

export interface EventSourceLike {
  addEventListener: (type: string, handler: (event: MessageEvent) => void) => void;
  close: () => void;
}

interface RealtimeOptions {
  streamUrl: string;
  onUpdate: (item: MemoryRunHistoryItem) => void;
  onEvent?: (eventType: MemoryRunRealtimeEventType, payload: MemoryRunRealtimeEventPayload) => void;
  onPollingTick: () => Promise<void> | void;
  onModeChange?: (mode: "sse" | "polling") => void;
  eventSourceFactory?: (url: string) => EventSourceLike;
  hasEventSource?: () => boolean;
  setIntervalFn?: (fn: () => void, delay: number) => ReturnType<typeof setInterval>;
  clearIntervalFn?: (id: ReturnType<typeof setInterval>) => void;
  pollingMs?: number;
}

export function startMemoryRunRealtime(options: RealtimeOptions): () => void {
  const {
    streamUrl,
    onUpdate,
    onEvent,
    onPollingTick,
    onModeChange,
    pollingMs = 5000,
    eventSourceFactory = (url) => new EventSource(url) as unknown as EventSourceLike,
    hasEventSource = () => typeof window !== "undefined" && typeof window.EventSource !== "undefined",
    setIntervalFn = setInterval,
    clearIntervalFn = clearInterval,
  } = options;

  let intervalId: ReturnType<typeof setInterval> | null = null;
  let source: EventSourceLike | null = null;
  let usingPolling = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let lastEventId: string | null = null;

  const realtimeEvents: MemoryRunRealtimeEventType[] = [
    "detection_complete",
    "recognition_strategy_used",
    "synthesis_started",
    "synthesis_completed",
  ];

  const trackEventId = (event: MessageEvent) => {
    if (typeof event.lastEventId === "string" && event.lastEventId) {
      lastEventId = event.lastEventId;
    }
  };

  const parsePayload = (event: MessageEvent): MemoryRunRealtimeEventPayload => {
    try {
      return JSON.parse(event.data) as MemoryRunRealtimeEventPayload;
    } catch {
      return {};
    }
  };

  const startPolling = () => {
    if (usingPolling) return;
    usingPolling = true;
    onModeChange?.("polling");
    void Promise.resolve(onPollingTick());
    intervalId = setIntervalFn(() => {
      void Promise.resolve(onPollingTick());
    }, pollingMs);
  };

  if (!hasEventSource()) {
    startPolling();
    return () => {
      if (intervalId) clearIntervalFn(intervalId);
    };
  }

  const connect = (baseUrl: string) => {
    const resolvedUrl = lastEventId ? getMemoryRunStreamUrlWithCursor(lastEventId) : baseUrl;
    source = eventSourceFactory(resolvedUrl);
    onModeChange?.("sse");

    source.addEventListener("memory_run_status", (event: MessageEvent) => {
      trackEventId(event);
      try {
        const parsed = JSON.parse(event.data) as MemoryRunHistoryItem;
        onUpdate(parsed);
      } catch {
        // Ignore malformed events and keep stream active.
      }
    });

    for (const eventType of realtimeEvents) {
      source.addEventListener(eventType, (event: MessageEvent) => {
        trackEventId(event);
        onEvent?.(eventType, parsePayload(event));
      });
    }

    source.addEventListener("error", () => {
      source?.close();
      source = null;
      startPolling();
    });
  };

  try {
    connect(streamUrl);
  } catch {
    startPolling();
  }

  return () => {
    source?.close();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    if (intervalId) clearIntervalFn(intervalId);
  };
}

