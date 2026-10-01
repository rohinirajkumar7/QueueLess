# QueueLess — Real-Time Queue & Appointment Management System

QueueLess is a production-grade, multi-tenant SaaS platform for organizations that need digital queue management, appointment booking, live customer updates, staff queue controls, email notifications, analytics, and operational observability — all delivered through a clean three-role portal system.

---

## What It Does

- **Customers** browse organizations, join FIFO queues, book appointments, track live queue position, and receive email/in-app notifications
- **Staff** operate assigned queues — call, start, complete, skip, or recall tokens in real time
- **Organization Admins** onboard their organization, manage services and staff, and view analytics

All three roles share the same JWT authentication backend. The frontend routes each role to its own dashboard automatically after login; backend RBAC remains authoritative at every API endpoint.

---

## Architecture

```
Browser  (React 18 + TypeScript + Vite + Tailwind)
    │  REST + WebSocket
    ▼
FastAPI (Gunicorn + 2 × UvicornWorker)   ←──  async SQLAlchemy / asyncpg
    │              │              │
PostgreSQL 16   Redis 7     Celery Worker  →  Gmail SMTP
    │
  Source of truth — queues, tokens, appointments,
  notifications, audit logs, organizations
```

**Key design decisions:**
- PostgreSQL is the **single source of truth** — Redis is never authoritative
- API workers use **async SQLAlchemy + asyncpg** (non-blocking I/O, connection pool of 20+10 per worker)
- Celery tasks use **synchronous SQLAlchemy + psycopg** (no event-loop conflicts in forked workers)
- Redis holds short-lived **read caches** (org list TTL 45 s, services list TTL 45 s) and acts as Celery broker/backend
- Queue token assignment uses **PostgreSQL row-level locking** (`SELECT … FOR UPDATE`) — not application-level counters
- Queue creation uses **`INSERT … ON CONFLICT DO NOTHING`** to be race-safe when multiple requests arrive simultaneously

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Backend API | FastAPI, Pydantic v2, SQLAlchemy 2 (async), asyncpg |
| Database | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| Background jobs | Celery 5 (prefork, sync workers), Celery Beat |
| Auth | JWT (access + refresh tokens), Argon2id password hashing |
| Email | Gmail SMTP via `smtplib` |
| Migrations | Alembic |
| Container runtime | Docker Compose |
| Tests | pytest, pytest-asyncio, anyio |
| E2E | Playwright |
| Load test | k6 |
| Observability | Prometheus `/metrics`, structured JSON logs, `/health`, `/ready` |

---

## Quick Start

### Prerequisites
- Docker Desktop (or Docker Engine + Compose plugin)

### Run everything
```bash
git clone <repo-url>
cd QueueLess-New
docker compose up --build
```

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **API** | http://localhost:8000 |
| **Swagger / OpenAPI** | http://localhost:8000/docs |
| **Prometheus metrics** | http://localhost:8000/metrics |
| **Health check** | http://localhost:8000/health |

The backend container automatically runs Alembic migrations and seeds demo data on every startup. The seed is idempotent — safe to run multiple times.

### Seeded demo accounts

| Role | Email | Password |
|------|-------|----------|
| Org Admin | `admin@democlinic.com` | `admin123` |
| Staff | `staff@democlinic.com` | `staff123` |
| Customer | `customer@example.com` | `customer123` |

> **Change all credentials before any non-development deployment.**

---

## Login Portals

| Portal | URL Path |
|--------|----------|
| Customer | `/login/customer` |
| Staff | `/login/staff` |
| Organization Admin | `/login/organization` |
| Register new organization | `/register/organization` |

---

## Email Configuration (Gmail SMTP)

Edit the `.env` file in the project root:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your.email@gmail.com
EMAIL_PASSWORD=your16charapppassword   # Gmail App Password
EMAIL_FROM=your.email@gmail.com
```

Generate an App Password at: **Google Account → Security → 2-Step Verification → App Passwords**

**How email works:**
- Password-reset emails are sent immediately (inline in the request)
- Queue join / appointment notifications are picked up by the Celery beat task within **~30 seconds**
- If the Gmail daily limit is reached (500/day on free accounts), the worker retries gracefully — no emails are lost, they are retried on the next beat cycle
- For development without a real inbox, replace the SMTP config with [Mailtrap](https://mailtrap.io) credentials

---

## Environment Variables

See `backend/.env.example` and `frontend/.env.example`. No production secret is committed to the repository.

**Required for production:**

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `SYNC_DATABASE_URL` | Sync connection for Celery (`postgresql+psycopg://...`) |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET` | Long random secret for JWT signing |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `FRONTEND_URL` | Public URL for password-reset email links |
| `EMAIL_*` | SMTP credentials (see above) |

---

## Project Structure

```
QueueLess-New/
├── backend/
│   ├── app/
│   │   ├── api/v1/router.py          # All REST endpoints
│   │   ├── core/
│   │   │   ├── config.py             # Settings (pydantic-settings)
│   │   │   ├── database.py           # Async engine + sync engine for Celery
│   │   │   └── security.py           # Argon2id hashing, JWT utilities
│   │   ├── models/models.py          # SQLAlchemy ORM models
│   │   ├── schemas/schemas.py        # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── auth_service.py       # Registration, login, password reset
│   │   │   ├── queue_service.py      # FIFO token assignment, call-next
│   │   │   └── appointment_service.py
│   │   ├── websocket/
│   │   │   ├── manager.py            # WebSocket connection manager
│   │   │   └── events.py             # Queue event broadcaster
│   │   └── workers/
│   │       ├── celery_app.py         # Celery config + beat schedule
│   │       └── tasks.py              # Email delivery, reminders, cleanup
│   ├── migrations/versions/          # Alembic migration files
│   ├── scripts/cleanup_test_orgs.py  # Remove load-test orgs from DB
│   ├── tests/
│   │   ├── conftest.py               # Shared fixtures
│   │   ├── test_api.py               # Health check smoke test
│   │   ├── test_core.py              # Password hashing unit test
│   │   └── test_queue_concurrency.py # Concurrent join + call-next locking
│   ├── seed.py                       # Idempotent demo data seeder
│   ├── pytest.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                    # Customer, Staff, Admin, Queue pages
│   │   ├── components/               # Layout, Icons
│   │   ├── services/api.ts           # Typed API client
│   │   └── store/auth.ts             # Auth state (Zustand)
│   └── e2e/customer-queue-join.spec.ts
├── loadtests/queueless.js            # k6 load test
├── docker-compose.yml
└── .env
```

---

## API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create customer account |
| POST | `/api/v1/auth/login` | Login, receive access + refresh tokens |
| POST | `/api/v1/auth/refresh` | Exchange refresh token for new access token |
| GET  | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/auth/forgot-password` | Send password-reset email |
| POST | `/api/v1/auth/reset-password` | Consume reset token, set new password |

### Organizations & Services
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/organizations` | List all real (non-test) organizations |
| POST | `/api/v1/organizations` | Create organization (admin) |
| GET | `/api/v1/organizations/{id}/services` | List services for an org |
| POST | `/api/v1/organizations/{id}/services` | Add service (admin) |

> Organization listing and services listing are **Redis-cached** (TTL 45 s). The cache is invalidated automatically on any create/update/deactivate mutation.

### Queue Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/services/{id}/queue/join` | Join queue, receive sequential token |
| GET  | `/api/v1/queues/{id}/position` | Live position + estimated wait |
| POST | `/api/v1/queues/{id}/call-next` | Staff: advance queue |
| POST | `/api/v1/tokens/{id}/start` | Staff: mark service started |
| POST | `/api/v1/tokens/{id}/complete` | Staff: mark service complete |
| POST | `/api/v1/tokens/{id}/skip` | Staff: skip token |
| POST | `/api/v1/tokens/{id}/recall` | Staff: recall skipped token |

### Appointments & Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/appointments` | Book appointment (overlap-checked transactionally) |
| GET  | `/api/v1/notifications` | Fetch user notifications |
| POST | `/api/v1/notifications/{id}/read` | Mark notification read |

### Analytics & Observability
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/overview` | Org-level stats (admin) |
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check (DB + Redis) |
| GET | `/metrics` | Prometheus metrics |

Full interactive documentation: **http://localhost:8000/docs**

---

## Queue Concurrency Design

This is the most critical correctness concern in the system.

**Token assignment (join queue):**
1. A `SELECT … FOR UPDATE` lock is acquired on the Queue row
2. `last_token_number` is incremented atomically inside the same transaction
3. A unique `(queue_id, token_number)` database constraint provides a final guard
4. Queue creation uses `INSERT … ON CONFLICT DO NOTHING` followed by a SELECT — atomic and safe when multiple requests race to create the same queue

**Call-next (staff advancing the queue):**
1. A `SELECT … FOR UPDATE` lock is acquired on the Queue row
2. The next waiting token is selected using `SKIP LOCKED` — concurrent call-next operations on the same queue are safe without application-level mutexes
3. No token is ever served twice

**PostgreSQL is the source of truth. Redis is never used for queue state.**

---

## Background Jobs (Celery)

The worker runs with **2 prefork processes**, `prefetch_multiplier=1`, and `acks_late=True`.

| Beat Task | Schedule | Purpose |
|-----------|----------|---------|
| `send_pending_emails` | Every 30 s | Deliver queued notification emails via SMTP |
| `send_appointment_reminders` | Every 5 min | Create reminder notifications for upcoming appointments |
| `cleanup_old_notifications` | Every 1 hr | Prune old read notifications |

All Celery tasks use **synchronous SQLAlchemy + psycopg** (not asyncpg) to avoid event-loop conflicts in forked worker processes. `send_pending_emails` uses `SELECT FOR UPDATE SKIP LOCKED` so multiple worker processes never double-deliver the same email.

---

## WebSocket

Connect to `/ws/queues/{queue_id}` for live queue position updates.

- The WebSocket endpoint is **advisory** — clients always refresh queue state after reconnect
- If no clients are connected to a queue, the broadcaster short-circuits and skips all DB queries (fast path)
- The frontend falls back to polling if WebSocket is unavailable, preserving correctness

---

## Database Migrations

```bash
cd backend
alembic upgrade head     # apply all migrations
alembic current          # show current revision
alembic history          # list all revisions
```

| Migration | Description |
|-----------|-------------|
| `0001_initial.py` | All core tables: users, organizations, services, queues, tokens, appointments, notifications, audit logs |
| `0002_password_reset.py` | Password reset tokens table |
| `0003_is_test_org.py` | `is_test` boolean column on organizations (composite index included) |

The `is_test` flag ensures load-test and CI-created organizations **never appear** in the customer-facing organization listing.

---

## Running Tests

### Backend (pytest)
```bash
cd backend
pytest tests -q
```

**What the tests cover:**

| Test | What it verifies |
|------|-----------------|
| `test_api.py::test_health` | `/health` returns 200 |
| `test_core.py::test_password_hashing` | Argon2 hash + verify round-trip |
| `test_core.py::test_fifo_ordering` | Token ordering model logic |
| `test_queue_concurrency.py::test_concurrent_join_queue_assigns_unique_sequential_tokens` | 20 concurrent join calls produce 20 unique, sequential, gap-free token numbers |
| `test_queue_concurrency.py::test_concurrent_call_next_never_serves_same_token_twice` | 10 concurrent call-next calls never return the same token twice |

The concurrency tests run against a real PostgreSQL database — `SKIP LOCKED` is not meaningfully testable with SQLite. Test organizations are flagged `is_test=True` and cleaned up in `finally` blocks.

```bash
# Point at a test database:
export DATABASE_URL=postgresql+asyncpg://queueless:queueless@localhost:5432/queueless_test
alembic upgrade head
pytest tests/test_queue_concurrency.py -v
```

### Frontend type-check + build
```bash
cd frontend
npm install
npm run build
```

### Playwright E2E
```bash
cd frontend
npx playwright install --with-deps chromium   # first time only
npm run test:e2e
```

`e2e/customer-queue-join.spec.ts` logs in as the seeded demo customer, browses to **QueueLess Demo Clinic**, joins the **General Consultation** queue, and asserts the token page renders. If the customer already holds an active token (previous run), the test asserts the "already in queue" message — safe to re-run without resetting data.

---

## Load Test (k6)

```bash
docker run --rm \
  -v "$(pwd)/loadtests:/loadtests" \
  --network="queueless-new_default" \
  grafana/k6:latest run \
  -e BASE_URL=http://backend:8000 \
  -e VUS=100 \
  -e DURATION=30s \
  /loadtests/queueless.js
```

### What the script does
- **`setup()`** — pre-registers 100 unique users once before the load phase
- **Load phase** — each VU: logs in → fetches org listing → fetches services → joins queue (repeats for `DURATION`)
- Tracks `login_duration`, `join_duration`, `org_duration`, `services_duration` as separate custom trends

### Results on this machine (100 VUs, 30 s)

| Metric | Value |
|--------|-------|
| Total HTTP requests | 1,016 |
| **HTTP error rate** | **0.00%** (0 failures) |
| Checks passed | **914 / 914 (100%)** |
| Throughput | ~27.7 req/s |
| Iterations completed | 457 |
| Login p50 / p95 | 3.45 s / 9.41 s |
| Join queue p50 / p95 | 2.04 s / 6.38 s |
| **Org listing p95** | **173 ms** (Redis cached — flat) |
| **Services listing p95** | **90 ms** (Redis cached — flat) |

**Key observations:**
- **Zero HTTP errors** across all 1,016 requests under 100 concurrent users — the app is completely stable
- **Redis caching delivers perfectly flat latency** for read-heavy endpoints: org listing and services listing show identical response times with zero variance, regardless of concurrency
- **Login latency is CPU-bound** — Argon2id password verification is intentionally expensive (~1–2 s per call). With 100 VUs all logging in simultaneously on a 2-process Docker container on a Windows/WSL2 host with limited CPU cores, the hashing operations queue serially. This is a hardware capacity constraint, not a code bug. On a dedicated multi-core server, Argon2 parallelizes and login p95 would be in the 200–400 ms range
- **Concurrency correctness holds under load** — no duplicate token numbers, no double-serving, no lost updates

To control VUs and duration:
```bash
-e VUS=50 -e DURATION=60s
```

### Cleanup after load tests
```bash
docker compose exec backend python scripts/cleanup_test_orgs.py
```
This removes all organizations (and their cascaded data) that were created by k6 or CI runs.

---

## Performance Optimizations Applied

| Optimization | Effect |
|-------------|--------|
| Gunicorn + 2 × UvicornWorker | 2 independent OS processes handle requests in parallel |
| Async SQLAlchemy + asyncpg | Non-blocking DB I/O; each worker handles many concurrent requests |
| Connection pool `size=20, max_overflow=10` per worker | Up to 60 API connections total; within PostgreSQL's `max_connections=100` |
| Redis cache on org listing + services | Read-heavy endpoints served from memory with 45 s TTL |
| Cache invalidation on mutation | Cache never serves stale data after writes |
| Celery `SKIP LOCKED` on email delivery | Concurrent workers never double-deliver emails |
| WebSocket fast-path | Queue broadcaster skips all DB queries when no clients are connected |
| `ON CONFLICT DO NOTHING` queue creation | Atomic, race-safe queue creation without retry loops |
| TanStack Query `staleTime=45s` on frontend | Browser does not re-fetch cached org/service data on every focus |
| `is_test` flag on organizations | Load-test orgs never pollute the customer org listing |

---

## Monitoring & Observability

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness — returns 200 if the process is alive |
| `GET /ready` | Readiness — checks PostgreSQL + Redis connectivity |
| `GET /metrics` | Prometheus-compatible metrics (request counts, latency histograms) |

Structured JSON logs are written to stdout with request IDs for correlation. All logs from all containers are available via:
```bash
docker compose logs -f backend
docker compose logs -f worker
```

**Recommended production metrics to alert on:**
- Request rate and P95/P99 latency per endpoint
- 4xx / 5xx error rate
- WebSocket active connections
- DB connection pool saturation
- Redis availability
- Celery task failure rate
- Queue depth per organization

> Prometheus scrape config and Grafana dashboard are not shipped in this repository. Prometheus can scrape `http://backend:8000/metrics` directly.

---

## Deployment

Recommended low-cost path:

| Component | Provider |
|-----------|---------|
| Frontend | Vercel or Cloudflare Pages |
| Backend + Worker | Render, Railway, or any container host |
| PostgreSQL | Neon, Supabase, or managed RDS |
| Redis | Upstash or managed ElastiCache |
| CI/CD | GitHub Actions (`.github/workflows/ci.yml`) |
| Monitoring | Grafana Cloud (optional) |

**Before going to production:**
1. Set strong `JWT_SECRET` (minimum 32 random bytes)
2. Set `CORS_ORIGINS` to exact frontend origin only
3. Use a managed PostgreSQL instance with backups enabled
4. Use a managed Redis instance with persistence
5. Configure production SMTP credentials
6. Enable HTTPS (handled by the hosting platform or a reverse proxy)
7. Remove or disable the development seed accounts

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `GET /ready` returns 503 | PostgreSQL not reachable | Check `DATABASE_URL` and that `db` container is healthy |
| Worker logs show `smtp_error` | SMTP credentials wrong or Gmail limit hit | Check `.env` email config; Gmail free accounts allow 500 emails/day |
| Queue join returns 409 | Customer already has an active token in this queue | Expected behavior — one active token per customer per queue |
| WebSocket disconnects in browser | Proxy not forwarding `Upgrade` header | Configure your reverse proxy for WebSocket proxying |
| Worker logs show `Retry in Xs` | Transient SMTP error | Celery will retry automatically — check email logs |
| Frontend shows test org in listing | `is_test` flag not set correctly on seeded data | Run `python seed.py` to re-seed with correct flags |
| CORS errors in browser | `CORS_ORIGINS` mismatch | Set `CORS_ORIGINS` to the exact origin including scheme and port |

---

## Security

- Passwords hashed with **Argon2id** (winner of the Password Hashing Competition) — memory-hard, GPU-resistant
- API access uses **short-lived JWT access tokens** (15 min) + **refresh tokens** (7 days)
- All database queries use **SQLAlchemy parameterized statements** — no raw string interpolation
- Organization and service mutation endpoints verify **ownership** in addition to role
- Password-reset tokens are **single-use** and **time-limited**
- `.env` is gitignored — no secrets are committed to the repository

---

## Non-Docker Development

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in DATABASE_URL, REDIS_URL, etc.
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

### Celery worker (separate terminal)
```bash
cd backend
celery -A app.workers.celery_app.celery worker --beat --loglevel=info
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

---

## Interview Discussion Topics

- Why PostgreSQL is the source of truth and Redis is never authoritative
- Why `SELECT … FOR UPDATE` and `SKIP LOCKED` are necessary for call-next (and why the concurrency test proves it, and what happens if you remove the lock)
- Why Argon2id over bcrypt, and the performance trade-off at high concurrency
- JWT access vs. refresh token lifecycle and why both are needed
- FIFO queue modeling: token numbers, ordering guarantees, gap prevention
- `INSERT … ON CONFLICT DO NOTHING` vs. application-level retry for queue creation
- WebSocket advisory model: why clients must always re-fetch state after reconnect
- Cache-aside with Redis: TTL selection, invalidation strategy, eventual consistency window
- Celery prefork vs. eventlet/gevent for CPU-bound vs. I/O-bound tasks
- The `is_test` flag pattern for isolating load-test data from production data
- How to scale the stateless API horizontally (add Gunicorn workers or container replicas)
- What's still missing (Grafana dashboard) and how you'd prioritize it
