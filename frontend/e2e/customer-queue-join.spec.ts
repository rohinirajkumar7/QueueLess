
import { test, expect } from "@playwright/test";

/**
 * End-to-end smoke test for the customer flow:
 * log in -> browse organizations -> open a service -> join its queue.
 *
 * Uses the seeded dev data:
 * - customer@queueless.example.com / Customer123!
 * - QueueLess Demo Clinic
 * - General Consultation and Billing services
 *
 * Handles both a fresh queue join and the case where the customer
 * already has an active token from a previous test run.
 */

test("customer can log in, join a queue, and see their token", async ({
  page,
}) => {
  await page.goto("/login/customer");

  // Enter credentials explicitly instead of relying on pre-filled values.
  await page.locator('input[type="email"]').fill(
    "customer@queueless.example.com"
  );
  await page.locator('input[type="password"]').fill("Customer123!");

  await page.getByRole("button", { name: /sign in/i }).click();

  // Verify successful login.
  await expect(page).toHaveURL(/\/dashboard$/);

  // Navigate to organizations.
  await page.getByRole("link", { name: /find a service/i }).click();
  await expect(page).toHaveURL(/\/organizations$/);

  // Open the demo clinic.
  await page
    .getByRole("link", { name: /queueless demo clinic/i })
    .click();

  await expect(page).toHaveURL(/\/organizations\/.+/);

  // Locate the General Consultation service.
  const generalConsultationCard = page
    .locator(".card", { hasText: "General Consultation" })
    .first();

  await expect(generalConsultationCard).toBeVisible();

  // Attempt to join the queue.
  await generalConsultationCard
    .getByRole("button", { name: /join queue/i })
    .click();

  // Wait for either navigation to the queue page or the existing-token
  // message. The app may return a 409 if this customer already joined.
  const onQueuePage = page
    .waitForURL(/\/queue\/.+/, { timeout: 10000 })
    .then(() => "queue" as const)
    .catch(() => null);

  const alreadyJoined = page
    .getByText(/you already have an active token for this queue/i)
    .waitFor({ timeout: 10000 })
    .then(() => "already-joined" as const)
    .catch(() => null);

  const result = await Promise.race([onQueuePage, alreadyJoined]);

  if (result === "queue") {
    // Fresh join: verify the customer landed on the live queue page.
    await expect(
      page.getByText(/your place is reserved/i)
    ).toBeVisible();

    await expect(page.getByText(/your token/i)).toBeVisible();
  } else if (result === "already-joined") {
    // Existing token: verify the app explains why another join
    // was not allowed.
    await expect(
      page.getByText(/you already have an active token for this queue/i)
    ).toBeVisible();
  } else {
    throw new Error(
      "Queue join did not navigate to the queue page or show the existing-token message."
    );
  }
});
