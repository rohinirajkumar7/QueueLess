import { defineConfig, devices } from "@playwright/test";

// Requires the backend running and migrated/seeded (see README "Testing"
// section) and reachable at VITE_API_URL - the seeded demo customer
// account and "QueueLess Demo Clinic" organization are what
// e2e/customer-queue-join.spec.ts logs in as and joins a queue for.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // the demo customer account is shared across a run; parallel runs would race for the same token
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
