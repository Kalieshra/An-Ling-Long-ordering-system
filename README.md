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

## Phase 4 — complete ✅

| Area | Status |
|---|---|
| ASGI app upgraded with `ProtocolTypeRouter` (HTTP via Django, WS via Channels) | ✓ |
| `KDSConsumer` (group `kds`, session-auth, kitchen-role only) | ✓ |
| `OrderTrackConsumer` (group `order_<uuid>`, JWT-auth via `?token=...`) | ✓ |
| `services.on_order_confirmed` + `services.update_order_status` broadcasters wired into `confirm_order` / kitchen view / cancel | ✓ |
| Kitchen page rewrites the grid live from `order.new` / `order.updated` events | ✓ |
| Reconnect with exponential backoff (capped at 30s) in the JS client | ✓ |
| pytest-asyncio + `WebsocketCommunicator` consumer tests | ✓ |
| Playwright marquee test: cashier confirms → kitchen browser shows card within 2s without reload | ✓ |

### WebSocket endpoints

| URL | Auth | Group | Notes |
|---|---|---|---|
| `ws://<host>:19000/ws/kds/` | session cookie + role=kitchen | `kds` | Receives `order.new` + `order.updated` |
| `ws://<host>:19000/ws/order/<uuid>/?token=<jwt>` | JWT in query string | `order_<uuid>` | Receives `order.updated` for the customer's own order |

Daphne runs on container port 9000 (host 19000). Gunicorn still serves HTTP on host 18000. Production will collapse them with a reverse proxy.

### Customer order-track example (mobile-side)

```js
const token = "<your-jwt-access-token>";
const ws = new WebSocket(`ws://api.example.com/ws/order/${orderUuid}/?token=${token}`);
ws.onmessage = (e) => {
  const evt = JSON.parse(e.data);
  console.log(evt.event, evt.payload.status);   // e.g. "order.updated", "preparing"
};
```

## Phase 5 — complete ✅

| Area | Status |
|---|---|
| `/api/v1/me/` profile (GET/PATCH; email + role read-only) | ✓ |
| `/api/v1/me/addresses/` saved-address CRUD with single-default-per-user | ✓ |
| `/api/v1/menu/featured/` cached 60s via django-redis | ✓ |
| Login throttle 5/min via `LoginThrottle(scope='auth_login')`; default user throttle 60/min | ✓ |
| CORS allow-list strict via `CORS_ALLOWED_ORIGINS` env var | ✓ |
| OpenAPI schema at `/api/schema/` + Swagger UI at `/api/schema/swagger-ui/` (drf-spectacular) | ✓ |
| `manage.py seed_demo` populates 3 cats + 12 dishes + 6 drinks + 5 modifier groups + 4 tables + 5 users | ✓ |
| Phase 5 Playwright E2E + Phase 1-4 still green (31 e2e total) | ✓ |

### Mobile developers — start here

The customer-facing API is what your mobile (or web) app talks to.

#### Demo credentials (run `manage.py seed_demo` first)

| Role | Email | Password |
|---|---|---|
| Admin | `demo-admin@rms.local` | `admin-pw-long-enough` |
| Cashier | `demo-cashier@rms.local` | `cashier-pw-long-enough` |
| Kitchen | `demo-kitchen@rms.local` | `kitchen-pw-long-enough` |
| Customer 1 | `demo-customer1@rms.local` | `customer-pw-long-enough` |
| Customer 2 | `demo-customer2@rms.local` | `customer-pw-long-enough` |

#### REST endpoint map

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/register/` | none | Register a customer |
| POST | `/api/v1/auth/login/` | none (5/min) | Get access + refresh tokens |
| POST | `/api/v1/auth/refresh/` | refresh | Rotate access token |
| POST | `/api/v1/auth/logout/` | refresh | Blacklist refresh |
| GET | `/api/v1/menu/categories/` | optional | List active categories |
| GET | `/api/v1/menu/items/?category=&type=&search=&ordering=` | optional | Browse menu (paginated, fuzzy search) |
| GET | `/api/v1/menu/items/<id>/` | optional | Item with nested modifier groups |
| GET | `/api/v1/menu/featured/` | optional | Featured items (60s cache) |
| GET, PATCH | `/api/v1/me/` | JWT | Profile (email + role read-only) |
| GET, POST | `/api/v1/me/addresses/` | JWT | Saved-address book |
| GET, PATCH, DELETE | `/api/v1/me/addresses/<id>/` | JWT | Single saved address |
| POST | `/api/v1/orders/` | JWT customer | Place takeaway/delivery order |
| GET | `/api/v1/orders/` | JWT customer | My orders, paginated |
| GET | `/api/v1/orders/<uuid>/` | JWT customer | Order detail with snapshot |
| PATCH | `/api/v1/orders/<uuid>/cancel/` | JWT customer | Cancel while pending (else 409) |
| GET | `/api/schema/` | none | OpenAPI 3 YAML |
| GET | `/api/schema/swagger-ui/` | none | Swagger UI explorer |

#### WebSocket events (Phase 4)

`ws://<host>:19000/ws/order/<uuid>/?token=<jwt>` — sends one or more JSON events:

```json
{ "event": "order.updated", "payload": { "uuid": "<uuid>", "status": "preparing" } }
```

Events seen by a customer for one order:
- `order.updated` with `status="confirmed"` after the cashier accepts a pending order
- `order.updated` with `status="preparing"` when the kitchen starts the order
- `order.updated` with `status="ready"` when the order is ready for pickup/delivery
- `order.updated` with `status="cancelled"` if cancelled

#### Error envelope

DRF default error shape — for validation:

```json
{ "field_name": ["Error message"] }
```

For domain conflicts (e.g. cancel-after-confirm):

```json
{ "detail": "Cannot move order ... from confirmed to cancelled." }
```

For throttling (HTTP 429):

```json
{ "detail": "Request was throttled. Expected available in 42 seconds." }
```

#### Quick happy path (curl)

```bash
HOST=http://localhost:18000

# Register + login
curl -X POST $HOST/api/v1/auth/register/ -H 'Content-Type: application/json' \
     -d '{"email":"a@x.com","password":"a-pw-long-enough"}'
TOKEN=$(curl -s -X POST $HOST/api/v1/auth/login/ -H 'Content-Type: application/json' \
        -d '{"email":"a@x.com","password":"a-pw-long-enough"}' | jq -r .access)

# Browse + place
curl $HOST/api/v1/menu/featured/
ITEM=$(curl -s $HOST/api/v1/menu/items/?category=pizzas | jq '.results[0].id')
ORDER=$(curl -s -X POST $HOST/api/v1/orders/ -H "Authorization: Bearer $TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"type\":\"delivery\",\"delivery_address\":\"X\",\"items\":[{\"menu_item\":$ITEM,\"quantity\":1}]}")
UUID=$(echo $ORDER | jq -r .uuid)

# Track via WS
wscat -c "ws://localhost:19000/ws/order/$UUID/?token=$TOKEN"
```

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
| 6 | Docs, healthz, admin polish, handoff. |

Each phase ships its own implementation plan and Playwright E2E suite.
