# An Ling Long — Restaurant Management System

Production-oriented RMS for the Egyptian market: dashboards for **admin / cashier / kitchen** plus a REST + WebSocket API for a future customer mobile app. Real-time kitchen display via Django Channels.

## Phase 1 — complete ✅

| Area | Status |
|---|---|
| Custom `User` model with 4 roles (admin / cashier / kitchen / customer) | ✓ |
| JWT auth for customers (`/api/v1/auth/{register,login,refresh,logout,password/change}/`) with refresh rotation + blacklist | ✓ |
| Session auth for staff (`/login/`) with role-based landing | ✓ |
| Strict role-gating middleware: `/dashboard/` → admin, `/cashier/` → cashier, `/kitchen/` → kitchen | ✓ |
| Docker Compose stack: db + redis + web + asgi | ✓ |
| Pytest unit + integration suites (52 tests) | ✓ |
| Playwright E2E role-gating suite | ✓ |
| GitHub Actions CI | ✓ |

## Local setup

Prereqs: Docker 24+, Docker Compose v2, [uv](https://docs.astral.sh/uv/), Python 3.12+.

```bash
# 1. Copy env file
cp .env.example .env

# 2. Install Python deps
uv sync

# 3. Build images and start the stack
make build
make up

# Watch logs (optional)
make logs

# 4. Create an admin superuser
docker compose exec web python manage.py createsuperuser --email admin@rms.local

# 5. Visit
open http://localhost:18000/login/       # staff login (port 18000 in dev to avoid host clashes)
# Django admin lives at /admin/ once you've created a superuser
```

By default, the override file maps host ports to non-defaults to avoid collisions: db **15432**, redis **16379**, web **18000**, asgi **19000**. Edit `docker-compose.override.yml` if your host is free and you'd like the standard ports.

## Tests

```bash
# Unit + integration (host-side, hits Postgres at localhost:15432 — needs `make up`)
make test

# Playwright E2E (needs `make up` + a chromium browser)
uv run playwright install chromium
make test-e2e

# Lint
make lint
```

E2E seed users (created automatically by the suite):

| Role | Email | Password |
|---|---|---|
| admin | `e2e-admin@rms.local` | `admin-pw-long-enough` |
| cashier | `e2e-cashier@rms.local` | `cashier-pw-long-enough` |
| kitchen | `e2e-kitchen@rms.local` | `kitchen-pw-long-enough` |
| customer | `e2e-customer@rms.local` | `customer-pw-long-enough` |

## Architecture

See [`docs/superpowers/specs/2026-04-24-rms-mvp-design.md`](docs/superpowers/specs/2026-04-24-rms-mvp-design.md) for the full MVP design (architecture, data model, phase plan).

```
┌──────────────────────────────┐
│  Browser (admin/cashier/     │
│  kitchen) + JWT API client   │
└──────┬─────────────────┬─────┘
       │ HTTP            │ WS (Phase 4)
       ▼                 ▼
   ┌────────┐       ┌────────┐
   │  web   │       │  asgi  │
   │ Django │       │ Daphne │
   │ Gunicorn│      │Channels│
   └───┬────┘       └───┬────┘
       └────────┬───────┘
                ▼
         ┌──────────────┐
         │ Postgres 16  │
         │   Redis 7    │
         └──────────────┘
```

## API endpoints (Phase 1)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/register/` | public | Customer signup; returns `{access, refresh, user}` |
| POST | `/api/v1/auth/login/` | public | Returns `{access, refresh, user}` |
| POST | `/api/v1/auth/refresh/` | refresh token | Rotates and returns new `{access, refresh}` |
| POST | `/api/v1/auth/logout/` | access token | Blacklists the refresh, 205 |
| POST | `/api/v1/auth/password/change/` | access token | Body `{old_password, new_password}` |

## Web routes (Phase 1)

| URL | Auth | Allowed role |
|---|---|---|
| `/login/` | public | — |
| `/logout/` | session | any authed |
| `/dashboard/` | session | admin only |
| `/cashier/` | session | cashier only |
| `/kitchen/` | session | kitchen only |
| `/admin/` | session + staff | superuser |

ADMIN is **strictly limited** to `/dashboard/` per the design. Admins do not auto-access `/cashier/` or `/kitchen/`.

## What's next

| Phase | Goal |
|---|---|
| 2 | Menu management — Category, MenuItem (dish/drink/combo), Modifier, Ingredient. Admin CRUD + read-only customer API. |
| 3 | Orders — Cashier POS UI, order types (dine-in / takeaway / delivery), customer API. Kitchen page polled. |
| 4 | Real-time KDS via Django Channels + Redis (WebSocket). |
| 5 | Customer API polish — profile, featured menu, throttling, OpenAPI schema. |
| 6 | Docs, healthz, admin polish, handoff. |

Each phase ships its own implementation plan and Playwright E2E suite.
