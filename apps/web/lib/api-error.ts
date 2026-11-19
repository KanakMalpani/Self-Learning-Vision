export type ApiFailure = {
  status: number;
  message: string;
};

export function readApiFailure(error: unknown, fallback: string): ApiFailure {
  if (typeof error === "object" && error !== null) {
    const statusValue = "status" in error ? Number(error.status) : 0;
    const message = error instanceof Error && error.message ? error.message : fallback;
    return {
      status: Number.isFinite(statusValue) ? statusValue : 0,
      message,
    };
  }
  return { status: 0, message: fallback };
}
