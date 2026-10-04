import { expect, test } from "@playwright/test";

/**
 * Camera detection -> same queue -> same triage/persist/SSE -> dashboard
 * with a camera badge. The backend runs the synthetic motion video as
 * site-100/roof; worker events carry event_id prefix "cam_" (the simulator
 * uses "evt_" and may coincidentally emit camera rows, so the prefix is
 * the worker's fingerprint).
 */
test("camera detection enters the same pipeline", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Connected — live")).toBeVisible({ timeout: 60000 });

  const filters = page.getByRole("group", { name: "Site and zone filters" });
  await filters.getByLabel("Site").selectOption("site-100");
  await filters.getByLabel("Zone").selectOption("roof");

  const feed = page.getByLabel("Incident feed");
  const detail = page.getByLabel("Incident details");

  let workerRow = false;
  for (let attempt = 0; attempt < 6 && !workerRow; attempt++) {
    const candidate = feed
      .getByRole("button")
      .filter({ hasText: "◉ camera" })
      .filter({ hasText: "motion_detected" })
      .first();
    await expect(candidate).toBeVisible({ timeout: 120000 });
    await candidate.click();
    try {
      await expect(detail).toContainText("cam_", { timeout: 5000 });
      workerRow = true;
    } catch {
      // A simulator camera row; more worker rows keep arriving — retry.
    }
  }
  expect(workerRow).toBe(true);
  await expect(detail).toContainText("motion_detected");
  await expect(detail).toContainText("AI summary:");
});
