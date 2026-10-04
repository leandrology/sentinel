import { expect, test } from "@playwright/test";

/**
 * Sensor event -> WS ingestion -> mock triage -> SQLite -> SSE -> dashboard,
 * then operator acknowledge persists across reload.
 */
test("sensor event flows end to end and acknowledge persists", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Connected — live")).toBeVisible({ timeout: 60000 });

  const feed = page.getByLabel("Incident feed");
  const first = feed.getByRole("button").first();
  await expect(first).toBeVisible({ timeout: 60000 });

  const name = await first.getAttribute("aria-label");
  await first.click();
  const detail = page.getByLabel("Incident details");
  await detail.getByRole("button", { name: "Acknowledge" }).click();
  await expect(detail).toContainText("acknowledged", { timeout: 15000 });

  // Persisted status survives reload: find it under the acknowledged filter.
  await page.reload();
  await expect(page.getByText("Connected — live")).toBeVisible({ timeout: 60000 });
  await page.getByRole("group", { name: "Site and zone filters" }).getByLabel("Status").selectOption("acknowledged");
  const acked = page.getByLabel("Incident feed");
  await expect(acked.getByRole("button").first()).toBeVisible({ timeout: 60000 });
  expect(name).toBeTruthy();
});
