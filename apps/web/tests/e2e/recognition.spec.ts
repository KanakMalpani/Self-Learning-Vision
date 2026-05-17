import { expect, test } from "@playwright/test";

const API = "http://localhost:8000";

test.beforeEach(async ({ page }) => {
  await page.route(`${API}/api/v1/memory-run-events/stream**`, async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });
  await page.route(`${API}/api/v1/upload`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        upload_id: "11111111-1111-4111-8111-111111111111",
        face_boxes: [{ x: 0.25, y: 0.2, width: 0.35, height: 0.45, score: 0.97 }],
      }),
    });
  });
  await page.route(`${API}/api/v1/memory-runs`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        memory_run_id: "22222222-2222-4222-8222-222222222222",
        recognition_result: {
          selected_face_index: 0,
          status: "unknown",
          confidence: 0.22,
          top_candidate_name: null,
          top_candidate_provider: "local-face-embedding",
          memory_summary: null,
          notes: null,
          tags: [],
          unknown_sample_id: "sample-1",
          unknown_sample_stored: true,
          unknown_cluster_id: "cluster-1",
          unknown_cluster_sighting_count: 1,
          unknown_cluster_suggested_for_enrollment: false,
          quality_score: 0.91,
          reason: "No trusted local identity matched this face.",
          embedding_dimensions: 128,
          candidate_count: 0,
        },
      }),
    });
  });
  await page.route(`${API}/api/v1/memory-runs/22222222-2222-4222-8222-222222222222`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "22222222-2222-4222-8222-222222222222",
        status: "done",
        memory_report: null,
        activities: [{ stage: "matching", message: "Unknown face queued for review", created_at: new Date().toISOString() }],
      }),
    });
  });
  await page.route(`${API}/api/v1/learning/review-inbox`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        questions: [],
        contradictions: [],
        candidate_memories: [],
        low_health_memories: [],
        replay_suggestions: [],
        signals: [],
        summary: { total_pending: 0 },
      }),
    });
  });
});

test("first-run recognition flow and Review Inbox shell are usable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Self-Learning Vision" })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-demo.png",
    mimeType: "image/png",
    buffer: Buffer.from("public-safe synthetic fixture"),
  });
  await page.getByRole("button", { name: "Upload & Detect Faces" }).click();
  await expect(page.getByRole("button", { name: /Face 1/ })).toBeVisible();

  await page.getByRole("button", { name: "Recognize Selected Face" }).click();
  await expect(page.getByText("Unknown face", { exact: true })).toBeVisible();
  await expect(page.getByText("Saved as a useful unknown sample")).toBeVisible();

  await page.goto("/learning-review");
  await expect(page.getByRole("heading", { name: /Review Inbox/i })).toBeVisible();
});
