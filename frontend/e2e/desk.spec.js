import { test, expect } from "@playwright/test";

const CLEAR_PREFS = {
  tags: [],
  sentiments: ["good", "bad", "ugly", "neutral"],
  keywords: [],
  tag_mode: "union",
};

test.describe.configure({ mode: "serial" });

test.describe("NewsPulse personal desk", () => {
  test.beforeAll(async ({ request }) => {
    const resp = await request.put("http://127.0.0.1:8010/api/preferences", {
      data: CLEAR_PREFS,
    });
    expect(resp.ok()).toBeTruthy();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("brand")).toHaveText("NewsPulse");
    await expect(page.getByTestId("tag-selector")).toBeVisible();
    await expect(page.locator('[data-testid="tag-selector"] option')).toHaveCount(8, {
      timeout: 20_000,
    });
  });

  test("loads sidebar, stats, and tag selector", async ({ page }) => {
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expect(page.getByTestId("stats")).toBeVisible();
    await expect(page.getByTestId("stat-stories")).toBeVisible();
    await expect(page.getByTestId("selected-tags")).toContainText("All domains");
    await expect(page.getByTestId("error-banner")).toHaveCount(0);
  });

  test("fetch this hour populates the feed", async ({ page }) => {
    await page.getByTestId("fetch-now").click();
    await expect(page.getByTestId("fetch-now")).toHaveText("Working…");
    await expect(page.getByTestId("fetch-now")).toHaveText("Fetch this hour", {
      timeout: 90_000,
    });
    await expect(page.getByTestId("error-banner")).toHaveCount(0);
    const cards = page.getByTestId("article-card");
    if ((await cards.count()) > 0) {
      const readMore = page.getByTestId("read-full");
      if ((await readMore.count()) > 0) {
        const href = await readMore.first().getAttribute("href");
        expect(href).toBeTruthy();
        expect(href).not.toContain("example.com");
        expect(href.startsWith("https://")).toBeTruthy();
      }
    } else {
      await expect(page.getByTestId("empty-state")).toBeVisible();
    }
  });

  test("tag selector filters the desk to one domain", async ({ page }) => {
    await page.getByTestId("tag-selector").selectOption("tech");
    await expect(page.getByTestId("tag-chip-tech")).toBeVisible();
    await expect(page.getByTestId("selected-tags")).not.toContainText("All domains");
    await expect(page.getByTestId("error-banner")).toHaveCount(0);
    await page.getByTestId("refresh-filters").click();
    await expect(page.getByTestId("stats")).toBeVisible();
  });

  test("sentiment checkboxes can hide ugly", async ({ page }) => {
    await page.getByTestId("sentiment-check-ugly").uncheck();
    await expect(page.getByTestId("sentiment-check-ugly")).not.toBeChecked();
    await expect(page.getByTestId("sentiment-check-good")).toBeChecked();
    await page.getByTestId("keywords-input").fill("chip");
    await expect(page.getByTestId("keywords-input")).toHaveValue("chip");
  });

  test("agent applies only-good health priorities", async ({ page }) => {
    await page.getByTestId("agent-input").fill("only good health news");
    await page.getByTestId("agent-submit").click();
    await expect(page.getByTestId("agent-note")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("tag-chip-health")).toBeVisible();
    await expect(page.getByTestId("sentiment-check-good")).toBeChecked();
    await expect(page.getByTestId("sentiment-check-ugly")).not.toBeChecked();
    await expect(page.getByTestId("sentiment-check-bad")).not.toBeChecked();
  });

  test("save priorities survives reload", async ({ page }) => {
    await page.getByTestId("tag-selector").selectOption("science");
    await page.getByTestId("save-priorities").click();
    await expect(page.getByTestId("save-priorities")).toBeEnabled({ timeout: 15_000 });
    await page.reload();
    await expect(page.getByTestId("tag-chip-science")).toBeVisible();
  });
});
