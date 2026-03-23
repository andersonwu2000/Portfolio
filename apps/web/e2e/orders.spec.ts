import { test, expect } from "@playwright/test";

async function loginViaStorage(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.setItem("quant_authenticated", "true");
    localStorage.setItem("quant_user_role", "admin");
  });
  await page.goto("/orders");
}

test.describe("Orders page", () => {
  test("navigate to orders → see order table", async ({ page }) => {
    await loginViaStorage(page);

    // Page heading
    await expect(page.locator("h2")).toHaveText(/order/i, { timeout: 10_000 });

    // Table should be visible with header columns
    const table = page.locator("table");
    await expect(table).toBeVisible({ timeout: 10_000 });

    // Verify some order data rendered (symbol from mock)
    await expect(page.getByText("AAPL")).toBeVisible();
  });

  test("fill order form → submit → success toast appears", async ({
    page,
  }) => {
    await loginViaStorage(page);

    // Open the order form — click "New Order" button
    const newOrderBtn = page.locator("button", { hasText: /new order/i });
    await newOrderBtn.click();

    // Fill the form
    const form = page.locator('form[aria-label="New order form"]');
    await expect(form).toBeVisible({ timeout: 5_000 });

    // Symbol input
    await form.locator('input[placeholder="AAPL"]').fill("TSLA");

    // Quantity input (type=number)
    const qtyInput = form.locator('input[type="number"]').first();
    await qtyInput.fill("50");

    // Price input (type=number, second one)
    const priceInput = form.locator('input[type="number"]').nth(1);
    await priceInput.fill("250");

    // Submit
    await form.locator('button[type="submit"]').click();

    // Toast notification should appear
    await expect(page.getByText(/order submitted|success/i)).toBeVisible({
      timeout: 10_000,
    });
  });
});
