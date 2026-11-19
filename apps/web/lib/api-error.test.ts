import { describe, expect, it } from "vitest";
import { readApiFailure } from "@/lib/api-error";

describe("readApiFailure", () => {
  it("reads status and message from API errors", () => {
    const error = Object.assign(new Error("Session expired"), { status: 401 });
    expect(readApiFailure(error, "fallback")).toEqual({
      status: 401,
      message: "Session expired",
    });
  });

  it("uses the fallback when the failure has no message", () => {
    expect(readApiFailure("offline", "Upload failed")).toEqual({
      status: 0,
      message: "Upload failed",
    });
  });
});
