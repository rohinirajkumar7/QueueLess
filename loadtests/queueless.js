/**
 * k6 load test for QueueLess
 *
 * Flow per VU iteration: login (with pre-registered k6 user) → join queue
 * The seeded k6 user is registered once during setup(); k6 users are NOT
 * registered per-iteration to avoid the high argon2 hashing cost dominating
 * the results.  Each VU still gets a unique user so concurrent joins all hit
 * the same service without "already in queue" 409 collisions.
 *
 * Run:
 *   k6 run \
 *     -e BASE_URL=http://localhost:8000 \
 *     -e VUS=100 \
 *     -e DURATION=60s \
 *     loadtests/queueless.js
 *
 * To use a different service directly (skip org discovery):
 *   k6 run -e SERVICE_ID=<uuid> ...
 */

import http from "k6/http";
import { check, sleep, fail } from "k6";
import { Trend, Counter } from "k6/metrics";
import { SharedArray } from "k6/data";

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------
const loginTrend    = new Trend("login_duration",    true);
const joinTrend     = new Trend("join_duration",     true);
const orgTrend      = new Trend("org_duration",      true);
const servicesTrend = new Trend("services_duration", true);
const join409       = new Counter("join_409_conflicts");

// ---------------------------------------------------------------------------
// Test options
// ---------------------------------------------------------------------------
export const options = {
  scenarios: {
    queue_join_load: {
      executor:  "constant-vus",
      vus:       Number(__ENV.VUS || 100),
      duration:  __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    // No more than 1 % hard HTTP failures (excludes expected 409 on join)
    http_req_failed:   ["rate<0.01"],
    // p95 login+join combined under 3 s (realistic for 100 VU, argon2 excluded)
    login_duration:    ["p(95)<3000"],
    join_duration:     ["p(95)<2000"],
  },
};

const BASE_URL    = __ENV.BASE_URL    || "http://localhost:8000";
const SERVICE_ID  = __ENV.SERVICE_ID  || null;   // skip discovery if set

// 409 on join is NOT an HTTP failure — it means "already in queue", which is
// valid business logic when a VU re-uses the same account across iterations.
http.setResponseCallback(http.expectedStatuses(200, 201, 409));

// ---------------------------------------------------------------------------
// setup(): runs once before load.  Creates VUS * some factor k6 users and
// discovers the target service ID, then shares the data with all VUs.
// ---------------------------------------------------------------------------

const VUS_COUNT = Number(__ENV.VUS || 100);

export function setup() {
  // --- Discover service ID ---
  let serviceId = SERVICE_ID;

  if (!serviceId) {
    const orgsRes = http.get(`${BASE_URL}/api/v1/organizations`, {
      tags: { name: "setup_list_organizations" },
    });
    orgTrend.add(orgsRes.timings.duration);

    if (orgsRes.status !== 200) {
      fail(`setup: GET /organizations returned ${orgsRes.status}`);
    }

    const orgs = orgsRes.json();
    if (!orgs || orgs.length === 0) {
      fail("setup: no organizations found — run seed.py first");
    }

    for (const org of orgs) {
      const svcRes = http.get(
        `${BASE_URL}/api/v1/organizations/${org.id}/services`,
        { tags: { name: "setup_list_services" } },
      );
      servicesTrend.add(svcRes.timings.duration);
      if (svcRes.status !== 200) continue;

      const services = svcRes.json();
      const active = services.find((s) => s.status === "ACTIVE");
      if (active) {
        serviceId = active.id;
        break;
      }
    }
  }

  if (!serviceId) {
    fail("setup: no ACTIVE service found — run seed.py first");
  }

  // --- Pre-register one user per VU ---
  // Using a stable prefix so re-runs on the same DB work (register returns
  // 409 if already exists, which we tolerate here).
  const users = [];
  for (let i = 0; i < VUS_COUNT; i++) {
    const email    = `k6-vu${i}@k6loadtest.io`;
    const password = "LoadTest123!";
    const name     = `K6 User ${i}`;

    const regRes = http.post(
      `${BASE_URL}/api/v1/auth/register`,
      JSON.stringify({ name, email, password, role: "CUSTOMER" }),
      { headers: { "Content-Type": "application/json" }, tags: { name: "setup_register" } },
    );
    // 200/201 = created; 409 = already exists from a previous run — both fine.
    if (regRes.status !== 200 && regRes.status !== 201 && regRes.status !== 409) {
      console.warn(`setup: register VU ${i} returned ${regRes.status}: ${regRes.body}`);
    }
    users.push({ email, password });
  }

  return { serviceId, users };
}

// ---------------------------------------------------------------------------
// default function — called once per VU per iteration
// ---------------------------------------------------------------------------
export default function (data) {
  const { serviceId, users } = data;

  // Each VU picks its own stable account (0-indexed, wraps if more iters
  // than users — but with 1 iter per VU this is always unique).
  const vuIdx    = (__VU - 1) % users.length;
  const { email, password } = users[vuIdx];

  // 1. Login
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email, password }),
    { headers: { "Content-Type": "application/json" }, tags: { name: "login" } },
  );
  loginTrend.add(loginRes.timings.duration);

  const loginOk = check(loginRes, {
    "login: 200": (r) => r.status === 200,
  });
  if (!loginOk) {
    console.warn(`login failed for ${email}: ${loginRes.status} ${loginRes.body}`);
    sleep(1);
    return;
  }

  const accessToken = loginRes.json("access_token");
  const authHeaders = {
    headers: {
      "Content-Type": "application/json",
      Authorization:  `Bearer ${accessToken}`,
    },
  };

  // 2. Join queue
  const joinRes = http.post(
    `${BASE_URL}/api/v1/services/${serviceId}/queue/join`,
    JSON.stringify({}),
    { ...authHeaders, tags: { name: "queue_join" } },
  );
  joinTrend.add(joinRes.timings.duration);

  check(joinRes, {
    "join: 200 or expected 409": (r) => r.status === 200 || r.status === 409,
  });

  if (joinRes.status === 409) {
    join409.add(1);
  }

  sleep(1);
}

// ---------------------------------------------------------------------------
// teardown(): runs once after load.  Leaves no permanent test orgs.
// Users registered in setup() remain in the DB but have email pattern
// k6-vu*@k6loadtest.io and are removed by cleanup_test_orgs.py.
// ---------------------------------------------------------------------------
export function teardown(data) {
  // Nothing to do here — k6 users are cleaned up by scripts/cleanup_test_orgs.py
  // which deletes users matching k6-%@k6loadtest.io pattern.
  console.log(
    `Teardown: service ${data.serviceId} is shared with the real app — not deleted.` +
    " Run scripts/cleanup_test_orgs.py to remove k6 test users if desired.",
  );
}
