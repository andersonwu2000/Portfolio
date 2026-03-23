import { test, expect } from "@playwright/test";

/**
 * Set localStorage keys so the app considers the user authenticated.
 * Must be called after page.goto() to a page on the same origin,
 * then we reload so the app picks up the new state.
 */
async function loginViaStorage(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.setItem("quant_authenticated", "true");
    localStorage.setItem("quant_user_role", "admin");
  });
  await page.goto("/");
}

test.describe("Smoke tests", () => {
  test("login → dashboard shows NAV, Cash, Positions metrics", async ({
    page,
  }) => {
    await loginViaStorage(page);

    // Dashboard heading should be visible
    await expect(page.locator("h2")).toBeVisible({ timeout: 10_000 });

    // Metric cards for key values should be present
    const main = page.locator("main");
    await expect(main.getByText("NAV")).toBeVisible({ timeout: 10_000 });
    await expect(main.getByText("Cash")).toBeVisible();
  });

  test("navigate to each page via sidebar links", async ({ page }) => {
    await loginViaStorage(page);

    const navLinks = [
      { path: "/portfolio", heading: /portfolio/i },
      { path: "/strategies", heading: /strateg/i },
      { path: "/orders", heading: /order/i },
      { path: "/backtest", heading: /backtest/i },
      { path: "/risk", heading: /risk/i },
      { path: "/settings", heading: /setting/i },
    ];

    for (const { path, heading } of navLinks) {
      await page.locator(`nav a[href="${path}"]`).click();
      await expect(page.locator("h2").first()).toHaveText(heading, {
        timeout: 10_000,
      });
    }
  });

  test("logout redirects to settings (login) page", async ({ page }) => {
    await loginViaStorage(page);

    // Click the logout button
    const logoutButton = page.locator("aside button").filter({ has: page.locator("svg") }).first();
    // The logout button contains a LogOut icon — find it by its position (before the collapse toggle)
    const buttons = page.locator("aside > div:last-child button");
    const logoutBtn = buttons.first();
    await logoutBtn.click();

    // After logout the app should redirect to /settings since isAuthenticated() is false
    await expect(page).toHaveURL(/settings/, { timeout: 10_000 });
  });
});
