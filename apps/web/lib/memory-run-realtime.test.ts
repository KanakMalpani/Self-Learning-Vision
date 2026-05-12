import { describe, expect, it, vi } from "vitest";
import { startMemoryRunRealtime } from "@/lib/memory-run-realtime";

describe("startMemoryRunRealtime", () => {
  it("falls back to polling when EventSource is unavailable", async () => {
    const onPollingTick = vi.fn().mockResolvedValue(undefined);
    const onModeChange = vi.fn();
    const setIntervalFn = vi.fn((fn: () => void) => {
      fn();
      return 123 as unknown as ReturnType<typeof setInterval>;
    });
    const clearIntervalFn = vi.fn();

    const stop = startMemoryRunRealtime({
      streamUrl: "http://localhost:8000/api/v1/memory_runs/stream",
      onUpdate: vi.fn(),
      onPollingTick,
      onModeChange,
      hasEventSource: () => false,
      setIntervalFn,
      clearIntervalFn,
      pollingMs: 1000,
    });

    expect(onModeChange).toHaveBeenCalledWith("polling");
    expect(setIntervalFn).toHaveBeenCalledTimes(1);
    expect(onPollingTick).toHaveBeenCalledTimes(2);

    stop();
    expect(clearIntervalFn).toHaveBeenCalledTimes(1);
  });

  it("switches from SSE to polling when stream errors", () => {
    const handlers: Record<string, (event: MessageEvent) => void> = {};
    const close = vi.fn();

    const sourceFactory = vi.fn(() => ({
      addEventListener: (type: string, handler: (event: MessageEvent) => void) => {
        handlers[type] = handler;
      },
      close,
    }));

    const onPollingTick = vi.fn();
    const onModeChange = vi.fn();

    startMemoryRunRealtime({
      streamUrl: "http://localhost:8000/api/v1/memory_runs/stream",
      onUpdate: vi.fn(),
      onPollingTick,
      onModeChange,
      eventSourceFactory: sourceFactory,
      hasEventSource: () => true,
      setIntervalFn: vi.fn(() => 456 as unknown as ReturnType<typeof setInterval>),
      clearIntervalFn: vi.fn(),
      pollingMs: 1000,
    });

    handlers.error({} as MessageEvent);

    expect(close).toHaveBeenCalled();
    expect(onModeChange).toHaveBeenCalledWith("sse");
    expect(onModeChange).toHaveBeenCalledWith("polling");
    expect(onPollingTick).toHaveBeenCalled();
  });
});

