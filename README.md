# QueueLess — Real-Time Queue & Appointment Management System

QueueLess is a full-stack, multi-tenant SaaS application that replaces physical waiting lines with digital FIFO queues, real-time live updates, staff controls, appointment scheduling, and email notifications.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| **Backend API** | FastAPI, Python 3.12, SQLAlchemy 2 (Async), asyncpg, Pydantic v2 |
| **Database** | PostgreSQL 16 (Single source of truth) |
| **Caching & Broker** | Redis 7 |
| **Task Queue** | Celery 5 (sync prefork workers) + Celery Beat |
| **Security & Auth** | Argon2id password hashing, Stateless JWT (Access + Refresh tokens), RBAC |
| **Real-Time** | WebSockets + polling fallback |
| **Testing & Load** | Pytest, Playwright (E2E), Grafana k6 |
| **DevOps** | Docker & Docker Compose, Gunicorn + Uvicorn workers |

---

## Project Structure

```text
QueueLess/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints (auth, queues, appointments, orgs)
│   │   ├── core/            # Config, database engines, security, Argon2/JWT
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/        # Business logic (FIFO queue locking, auth, emails)
│   │   ├── websocket/       # Real-time WebSocket connection manager & broadcaster
│   │   └── workers/         # Celery background tasks & beat schedules
│   ├── migrations/          # Alembic database migration revisions
│   ├── tests/               # Pytest suite (health, auth, queue concurrency locking)
│   ├── seed.py              # Idempotent development demo seeder
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # UI components & shared layouts
│   │   ├── pages/           # Customer, Staff, Admin, and Queue views
│   │   ├── services/        # Typed API client
│   │   └── store/           # Zustand authentication state
│   ├── e2e/                 # Playwright end-to-end test specs
│   └── Dockerfile
├── loadtests/
│   └── queueless.js         # k6 stress test script (100 concurrent VUs)
└── docker-compose.yml       # Orchestrates DB, Redis, Backend, Worker, & Frontend
```

---

## Quick Start (One Command)

### Prerequisites
- Docker Desktop

### Run the App
```bash
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **API Docs (Swagger):** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

### Demo Login Accounts

| Role | Email | Password |
|---|---|---|
| **Org Admin** | `admin@queueless.example.com` | `Admin123!` |
| **Staff** | `staff@queueless.example.com` | `Staff123!` |
| **Customer** | `customer@queueless.example.com` | `Customer123!` |

---

## Email Notifications (Gmail SMTP)

QueueLess dispatches transactional emails for appointment confirmations, upcoming reminders, and password resets:
- **Asynchronous Delivery**: Fast, non-blocking requests. Emails are stored as pending records in PostgreSQL and swept every 30 seconds by a background Celery Beat worker.
- **Gmail SMTP Integration**: Works out-of-the-box via Gmail with a 16-character App Password configured in `.env`.
- **Fault-Tolerant & Retry-Safe**: Uses `SELECT FOR UPDATE SKIP LOCKED` so concurrent worker processes never double-deliver emails. If Gmail hits its daily free limit (500 emails/day) or experiences a timeout, Celery automatically retries with backoff without losing pending emails.

---

## Key Engineering Highlights

1. **Transactional FIFO Queue (Zero Token Collisions)**:
   - Uses PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) on the queue row during token generation.
   - Calling next token uses `SKIP LOCKED` to prevent duplicate assignments even under heavy concurrent staff calls.
   - Guaranteed sequential token numbers with database-level unique constraints.

2. **Isolated Database Layers**:
   - **FastAPI Backend**: Fully asynchronous using `SQLAlchemy + asyncpg` connection pools for high-throughput I/O.
   - **Celery Workers**: Synchronous connections using `psycopg` to prevent event-loop conflicts across forked background processes.

3. **High-Performance Redis Caching**:
   - Organization and service directories are cached in Redis with a 45-second TTL.
   - Automatically invalidated on updates/creates, delivering sub-180ms read responses.

4. **Resilient Real-Time Updates (WebSocket + Polling Fallback)**:
   - Live queue updates stream over WebSockets with an automatic TanStack Query polling fallback, ensuring zero UI disruption during network drops.

5. **Atomic Appointment Conflict Prevention**:
   - Time-slot validation executes inside strict database transactions, preventing double-booking when multiple customers attempt to book the same staff or time slot concurrently.

6. **Test Data Isolation (`is_test` Architecture)**:
   - CI and k6 load test organizations are tagged with an `is_test` flag and composite indexes, ensuring high-concurrency benchmarks never pollute customer-facing organization directories.

---

## Verification & Test Results

### 1. Automated Pytest Suite
Verifies API health, Argon2id round-trips, and concurrent queue locking:
```text
tests/test_api.py::test_health                                           PASSED
tests/test_core.py::test_password_hashing                                PASSED
tests/test_core.py::test_fifo_ordering_model                             PASSED
tests/test_queue_concurrency.py::test_concurrent_join_queue_assigns...   PASSED
tests/test_queue_concurrency.py::test_concurrent_call_next_never...      PASSED

============================== 5 passed in 3.32s ===============================
```

### 2. k6 Load Test Results (100 Concurrent Virtual Users)
Tested end-to-end customer journey (Login -> Fetch Organizations -> Fetch Services -> Join Queue):

| Metric | Result | Note |
|---|---|---|
| **HTTP Request Failure Rate** | **0.00%** (0 / 1,016 errors) | Zero dropped requests under peak load |
| **Functional Checks** | **100% Passed** (914 / 914) | All token and login contracts held |
| **Cached Org Listing** | **~173 ms flat** | Served instantly from Redis |
| **Cached Services Listing** | **~90 ms flat** | Zero database pressure on repeat reads |
| **Queue Concurrency** | **Passed** | No token duplicates or race conditions |

---

## Running Tests Locally

```bash
# Run backend concurrency & unit tests inside Docker
docker compose exec backend pytest -v

# Run k6 load test (requires k6 or Docker)
docker run --rm -v "${PWD}/loadtests:/loadtests" --network="queueless-new_default" grafana/k6:latest run -e BASE_URL=http://backend:8000 -e VUS=100 -e DURATION=30s /loadtests/queueless.js
```

---

## Production Deployment

QueueLess supports two primary deployment strategies:

### Option A: Single VPS (Docker Compose + Automated SSL)
Best for cost efficiency (e.g., AWS EC2, DigitalOcean, Hetzner, or Linode):
1. Install Docker and Docker Compose on Ubuntu.
2. Clone the repository and configure `.env` with production secrets.
3. Start the containers:
   ```bash
   docker compose up -d --build
   ```
4. Point a reverse proxy (such as Caddy or Nginx) to the containers for automatic Let's Encrypt HTTPS:
   - Frontend: Reverse proxy to `localhost:3000`
   - Backend API & WebSockets: Reverse proxy to `localhost:8000`

### Option B: Managed Cloud Services
- **Frontend**: Deploy `frontend/` to Vercel or Cloudflare Pages with build argument `VITE_API_URL=https://api.yourdomain.com/api/v1`.
- **Backend API & Celery Worker**: Deploy on Render or Railway from `backend/Dockerfile` as two instances (one web service for Gunicorn/FastAPI, one background worker for Celery).
- **Databases**: Use managed PostgreSQL (Neon, Supabase) and managed Redis (Upstash).

### Production Pre-Flight Checklist
- Generate a cryptographically secure `JWT_SECRET`: `python -c "import secrets; print(secrets.token_hex(32))"`
- Restrict `CORS_ORIGINS` to the exact production frontend domain.
- Configure production SMTP credentials in `.env`.
- Remove `python seed.py` from the backend startup command after the initial run to prevent re-seeding default demo credentials.

