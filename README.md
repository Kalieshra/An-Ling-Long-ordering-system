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

## Phase 2 — complete ✅

| Area | Status |
|---|---|
| 6 menu models with `pg_trgm` GIN trigram index | ✓ |
| Public read-only API: `/api/v1/menu/{categories,items,items/<id>}/` (paginated, filtered, fuzzy-searchable) | ✓ |
| Dashboard CRUD UI under `/dashboard/menu/{categories,items,inventory}/` | ✓ |
| Django admin back-door with inline modifier groups + recipe rows | ✓ |
| Image upload (≤ 5 MB) | ✓ |
| Phase 2 Playwright suite (5 tests) + Phase 1 tests still green | ✓ |

### Menu API examples

```
# Categories (anonymous)
curl http://localhost:18000/api/v1/menu/categories/

# Items, filtered + paginated
curl 'http://localhost:18000/api/v1/menu/items/?category=pizzas&type=dish&search=marg&ordering=price'

# Item detail (with nested modifier groups)
curl http://localhost:18000/api/v1/menu/items/1/
```

## Phase 3 — complete ✅

| Area | Status |
|---|---|
| Order/OrderItem/Table models with JSONB price snapshot | ✓ |
| `orders.services` layer (`create_order`, `confirm_order`, `mark_paid_cash`, `cancel_order`, `transition_status`) | ✓ |
| Cashier POS at `/cashier/` with grid + cart + dine-in/takeaway/delivery tabs + 14% VAT live totals | ✓ |
| Pending customer-orders panel + cashier confirm action | ✓ |
| HTML receipt at `/cashier/orders/<uuid>/receipt/` | ✓ |
| Kitchen list at `/kitchen/` (refresh-only) with status transition buttons | ✓ |
| Customer JWT API: `POST/GET /api/v1/orders/`, `GET /api/v1/orders/<uuid>/`, `PATCH /api/v1/orders/<uuid>/cancel/` | ✓ |
| Snapshot survives menu rename | ✓ |
| Phase 3 Playwright suite + Phase 1+2 still green | ✓ |

### Order API examples

```
# Customer login (Phase 1 endpoint)
TOKEN=$(curl -s -X POST http://localhost:18000/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"customer@x.com","password":"customer-pw"}' | jq -r .access)

# Place a delivery order
curl -X POST http://localhost:18000/api/v1/orders/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"delivery","delivery_address":"10 Cairo St",
       "items":[{"menu_item":1,"quantity":2,"modifiers":[]}]}'

# List my orders
curl http://localhost:18000/api/v1/orders/ -H "Authorization: Bearer $TOKEN"

# Cancel while pending
curl -X PATCH http://localhost:18000/api/v1/orders/<uuid>/cancel/ \
  -H "Authorization: Bearer $TOKEN"
```

### Phase 3 routes

| Path | Method | Auth | Notes |
|---|---|---|---|
| `/cashier/` | GET | session (cashier) | POS UI |
| `/cashier/orders/create/` | POST JSON | session (cashier) | Calls `create_order` + `confirm_order` |
| `/cashier/orders/<uuid>/` | GET | session (cashier) | Order detail with mark-paid action |
| `/cashier/orders/<uuid>/mark-paid/` | POST | session (cashier) | `mark_paid_cash` |
| `/cashier/orders/<uuid>/receipt/` | GET | session (cashier) | Printable HTML receipt |
| `/cashier/orders/pending/` | GET | session (cashier) | Customer-API orders awaiting confirm |
| `/cashier/orders/<uuid>/confirm/` | POST | session (cashier) | `confirm_order` for pending → confirmed |
| `/kitchen/` | GET | session (kitchen) | List of confirmed/preparing/ready (refresh-only — Phase 4 → WS) |
| `/kitchen/orders/<uuid>/status/` | POST | session (kitchen) | `transition_status` |

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
| 4 | Real-time KDS via Django Channels + Redis (WebSocket). |
| 5 | Customer API polish — profile, featured menu, throttling, OpenAPI schema. |
| 6 | Docs, healthz, admin polish, handoff. |

Each phase ships its own implementation plan and Playwright E2E suite.
