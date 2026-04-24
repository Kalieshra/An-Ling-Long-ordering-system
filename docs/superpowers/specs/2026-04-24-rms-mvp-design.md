# Restaurant Management System (RMS) — Lean MVP Design

**Date:** 2026-04-24
**Author:** Solo developer (Zagazig, Sharqia, Egypt) + Claude (brainstorming)
**Source blueprint:** `e1589856-8aa2-4108-8851-383291e267c8.pdf` (44 pages; opinionated reference)
**Status:** Approved for implementation planning

---

## 1. Purpose

Ship a working restaurant backend with three role-gated web dashboards (admin, cashier, kitchen) and a REST+WebSocket API for a future customer mobile app. The defining quality is that **a new order appears in the kitchen instantly** — no refresh, no polling.

A separate Flutter mobile app is explicitly **out of scope**. We only expose the APIs a mobile app will consume.

## 2. Non-goals (deferred, not forgotten)

These are valuable but excluded from this MVP so the first slice ships:

- Paymob (or any) payment gateway integration — cashier records cash/paid manually
- Inventory auto-deduction on order (models exist; deduction logic deferred)
- Arabic RTL, i18n
- Loyalty points / customer tiers
- Analytics dashboards, materialized views, reporting exports
- Shift management and cash drawer reconciliation
- Celery workers (imports reserved; no jobs scheduled)
- Production deployment hardening (Nginx + TLS + secrets + monitoring + backups)

Each of these is a clean follow-up spec once the MVP is live.

## 3. Scope summary (what we ARE building)

| Area | In scope |
|---|---|
| Menu | Category, MenuItem (dish/drink/combo), ModifierGroup/Option, Ingredient, Recipe — full CRUD from admin dashboard |
| Users & auth | Custom `User` model; roles: admin, cashier, kitchen, customer; session auth for staff dashboards; JWT for customer API |
| Role gating | Strict — cashier cannot open admin or kitchen URLs; customer JWT rejected on staff URLs; verified by E2E tests per phase |
| Orders | `Order` with `Type ∈ {dine_in, takeaway, delivery}`, `Status`, `PaymentStatus`; `OrderItem`; JSONB price snapshot |
| Cashier POS | Touch-friendly web UI to build cart, pick table (dine-in) or capture phone/address, confirm, mark paid (cash) |
| Kitchen KDS | Web UI showing live order cards via WebSocket; buttons for preparing / ready / served |
| Customer API | Register, login, refresh/logout JWT; browse menu; place takeaway/delivery order; track live status via WebSocket |
| Real-time | Django Channels + `channels-redis`; ASGI via Daphne alongside Gunicorn |
| Infra | Docker Compose for dev only: db (Postgres 16) + redis (Redis 7) + web (Django/Gunicorn) + asgi (Daphne) |
| Tests | pytest (unit + integration) + Playwright (browser E2E), running in CI, per-phase suites |

## 4. Architecture

### 4.1 Component diagram (dev / local)

```
        ┌─────────────────────────────────────────────────┐
        │   Browser (admin / cashier / kitchen)           │
        │   JWT client (future mobile; today: curl/tests) │
        └──────────┬───────────────┬──────────────────────┘
                   │ HTTPS/HTTP    │ WSS/WS
                   ▼               ▼
              ┌─────────┐    ┌──────────┐
              │   web   │    │   asgi   │
              │ Django  │    │ Daphne   │
              │ Gunicorn│    │ Channels │
              └────┬────┘    └────┬─────┘
                   │              │
                   └──────┬───────┘
                          ▼
                   ┌──────────────┐
                   │  Postgres 16 │
                   │     (db)     │
                   └──────────────┘
                   ┌──────────────┐
                   │   Redis 7    │
                   │ (channels)   │
                   └──────────────┘
```

### 4.2 Dual-role Django: REST + Templates (single codebase)

Per the PDF blueprint:
- `rms/urls.py` routes `/api/v1/*` to DRF `ViewSet`s (JWT, CORS)
- Same file routes `/dashboard/`, `/cashier/`, `/kitchen/` to classical Django template views (session + CSRF)
- Business logic lives in `services.py` modules, **not** in views — both layers call the same functions. This is what makes "cashier confirms order in POS" and "customer POSTs order via API" produce identical side effects (including the KDS broadcast).

### 4.3 Real-time

- ASGI server: **Daphne** on port 9000 (alongside Gunicorn on 8000)
- Channel layer backend: `channels_redis.core.RedisChannelLayer`
- Groups:
  - `kds` — all kitchen staff join; receives `order.new` + `order.updated`
  - `order_<uuid>` — one customer per order; receives `order.updated`
- Trigger: `orders.services.on_order_confirmed(order)` does `async_to_sync(channel_layer.group_send)` — invoked by the cashier POS view, the customer API `create`, and (later) the payment-paid hook.

### 4.4 Auth strategy

| Consumer | Scheme | Library | Storage |
|---|---|---|---|
| Admin / cashier / kitchen web | Django session + CSRF | `django.contrib.auth` | HttpOnly cookie |
| Customer API | JWT (access 15 min, refresh 7 days, rotation + blacklist) | `djangorestframework-simplejwt` | Client-side (future mobile: secure storage) |
| KDS WebSocket | Session cookie | `channels.auth.AuthMiddlewareStack` | — |
| Customer order-track WebSocket | JWT in query string (`?token=<access>`) validated by custom `JwtAuthMiddleware` before `accept()` | custom middleware | — |

### 4.5 Role-gating

- Custom middleware `AllowedRoleForPath` that maps URL prefixes to allowed `Role` sets:
  - `/dashboard/` → `{ADMIN}`
  - `/cashier/` → `{CASHIER}`
  - `/kitchen/` → `{KITCHEN}`
  - (ADMIN does NOT automatically access cashier/kitchen URLs; admin uses `/dashboard/` only. If that proves inconvenient in dev, we widen via a small change — but the default is strict per your "no one can open another type's dashboard" requirement.)
- DRF permission class `HasRole` for API viewsets
- WS consumer checks `self.scope["user"].role` before `accept()`; closes with code 4401 otherwise
- Verified by E2E tests in phase 1 and every phase after (regression)

## 5. Data model (MVP surface only)

```
accounts/
  User (AbstractUser; email login; role enum)

menu/
  Category (name, slug, display_order, is_active, image)
  MenuItem (category FK, name, item_type{dish,drink,combo}, price, cost, image,
            is_available, prep_time_min, tags JSONB)
  ModifierGroup (menu_item FK, name, min_select, max_select, is_required)
  ModifierOption (group FK, name, price_delta, is_available)
  Ingredient (name, unit, stock_qty, low_threshold, cost_per_unit)  # tracked; not auto-deducted in MVP
  Recipe (menu_item FK, ingredient FK, quantity)                    # relation exists; unused by runtime in MVP

orders/
  Table (number, capacity, qr_token, is_active)
  Order (uuid, number, customer FK?, cashier FK?, table FK?,
         order_type, status, payment_status,
         subtotal, tax, service_charge, discount, total,
         delivery_address, notes,
         snapshot JSONB,           # frozen menu item names/prices for audit
         created_at, confirmed_at, ready_at, served_at)
  OrderItem (order FK, menu_item FK, quantity, unit_price, notes)
  OrderItemModifier (order_item FK, option FK, price_delta)
```

No `payments/`, `loyalty/`, `analytics/` apps in MVP (they're post-MVP phases).

## 6. Phases (vertical slices)

> **Rule for every phase:** migrations green, unit + integration tests green, phase-specific Playwright E2E suite green, seed data loads cleanly, README updated.
>
> **Planning note:** each phase gets its own implementation plan (written via `superpowers:writing-plans`). We'll start by writing the plan for **Phase 1** next. Subsequent phases are planned at the *end* of the preceding phase so the plan reflects what actually got built, not what we predicted.

### Phase 1 — Foundation & Role-Gated Auth (week 1)

Plumbing only; no menu or orders.

**Deliverables**
- Django 5 project `backend/`, apps `accounts/`, shared `rms/` project config
- Docker Compose with `db`, `redis`, `web`, `asgi`
- Custom `User` with email login + `Role` enum
- JWT endpoints: `POST /api/v1/auth/{register,login,refresh,logout,password/change}/`
- Session-auth login views at `/login/` (staff) + role-based redirect after login
- Empty placeholder pages at `/dashboard/`, `/cashier/`, `/kitchen/` — each inherits CoreUI base
- `AllowedRoleForPath` middleware
- DRF `HasRole` permission class
- CI: GitHub Actions → ruff → pytest → docker compose build

**E2E (per phase)**
- Admin login → `/dashboard/` loads; hitting `/cashier/` or `/kitchen/` → 403
- Cashier login → `/cashier/` loads; hitting `/dashboard/` → 403
- Kitchen login → `/kitchen/` loads; hitting `/cashier/` → 403
- Customer registers via API → receives JWT → `/dashboard/` with that bearer → 401/403
- Refresh rotation issues new tokens; logout blacklists the refresh

### Phase 2 — Menu Management (week 2)

Admin fully manages menu; customers read it.

**Deliverables**
- Models: Category, MenuItem, ModifierGroup, ModifierOption, Ingredient, Recipe
- Admin dashboard pages: Categories CRUD, Menu Items CRUD with inline modifiers + image upload, Ingredients CRUD
- Public read API: `GET /api/v1/menu/categories/`, `GET /api/v1/menu/items/?category=&type=&search=&available=`, `GET /api/v1/menu/items/{id}/`
- Image storage on `mediafiles` volume via Pillow
- Django admin registered for all models (power-user CRUD)

**E2E**
- Admin creates category → dish with 2 modifier groups → uploads image → toggles availability off → item disappears from API
- Customer API browse: only `is_available=True` items returned; filter by category slug works; filter by `type=drink` works
- Cashier/kitchen user hitting admin menu pages → 403
- Item detail API returns nested modifier groups with options

### Phase 3 — Cashier POS & Order Flow (weeks 3-4)

Orders can be placed. Kitchen page still static-refresh (real-time arrives in phase 4).

**Deliverables**
- Models: Table, Order, OrderItem, OrderItemModifier
- `orders.services.create_order(cart, *, cashier=None, customer=None, table=None, order_type, delivery_address=None)` — `@transaction.atomic`, freezes prices into `snapshot` JSONB
- `orders.services.confirm_order(order)` — transitions `draft → confirmed`, sets `confirmed_at`
- `orders.services.mark_paid_cash(order, cashier)` — cashier-only, sets `payment_status=PAID`
- Cashier POS (`/cashier/`):
  - Grid of available menu items (big touch buttons, image + name + price)
  - Cart sidebar with qty steppers and modifier pickers
  - Order-type tabs: dine-in (table picker) / takeaway (phone) / delivery (phone + address)
  - Live totals (subtotal + 14% VAT + total)
  - "Confirm" button (POST to a cashier view, which calls `create_order` + `confirm_order`)
  - "Mark paid" on the order detail page
- Kitchen page (`/kitchen/`): lists `Order.status IN (confirmed, preparing, ready)` — **full-page refresh only** (upgraded in Phase 4)
- Customer API (JWT required):
  - `POST /api/v1/orders/` — body `{type, items: [{menu_item, quantity, modifiers: [option_id]}], notes, delivery_address}`
  - `GET /api/v1/orders/` — customer's history, paginated
  - `GET /api/v1/orders/{uuid}/` — detail
  - `PATCH /api/v1/orders/{uuid}/cancel/` — only if `status IN (draft, pending)`
- Invoice HTML view at `/cashier/orders/<uuid>/receipt/`

**E2E**
- Cashier: add 2 items + modifiers → dine-in, table 3 → confirm → DB has order with correct totals + snapshot freezes name/price
- Cashier: takeaway order → mark paid → receipt page renders totals + items
- Customer API: create delivery order with address → GET detail shows it → cancel while pending → OK; try cancel after cashier confirms → 403
- After admin renames a dish, an existing order's receipt still shows the original name (snapshot works)
- Ordering an `is_available=False` item → 400 from API, hidden from POS
- Kitchen refreshes page → sees the confirmed order

### Phase 4 — Real-Time Kitchen (WebSocket KDS) (week 5)

The defining phase. Orders appear **instantly**.

**Deliverables**
- `rms/asgi.py` wires `ProtocolTypeRouter` with `AuthMiddlewareStack` for WS
- `orders/consumers.py`: `KDSConsumer` (group `kds`), `OrderTrackConsumer` (group `order_<uuid>`)
- `orders/routing.py`: `ws/kds/`, `ws/order/<uuid>/`
- `orders.services.on_order_confirmed(order)` → broadcasts `order.new` to `kds` group — **called from `confirm_order`** (same signal for cashier and customer-API flows)
- `orders.services.update_order_status(order, new_status, by_user)` → broadcasts `order.updated` to both `kds` and `order_<uuid>` groups
- Kitchen dashboard upgraded: WebSocket JS connects on load, renders incoming `order.new` as a card, listens for `order.updated`; buttons "Preparing" / "Ready" / "Served" POST to `/kitchen/orders/<uuid>/status/` which calls `update_order_status`
- Customer order-track WebSocket authenticated via JWT in query string (short-lived token best practice)
- Graceful reconnect (exponential backoff in client JS)

**E2E (the marquee test)**
- Playwright opens `/kitchen/` as kitchen user; within the same test, a second Playwright browser context logs in as cashier, places an order, and confirms — within 2 seconds, the kitchen browser's DOM must show the new order card **without reload**
- Kitchen clicks "Preparing" → pytest `WebsocketCommunicator` connected to `ws/order/<uuid>/?token=<customerJWT>` receives `{"event": "order.updated", "status": "preparing"}`
- Two kitchen browsers open → one clicks "Ready" → the other's card updates without reload
- Non-kitchen user (cashier) connecting to `ws/kds/` → close code 4401
- WS disconnect + reconnect within 5s → state still correct (kitchen not missing any order)

### Phase 5 — Customer API Polish & Self-Serve (week 6)

API becomes production-shape for a future mobile app.

**Deliverables**
- `GET/PATCH /api/v1/me/` (profile)
- `GET /api/v1/me/addresses/` (saved delivery addresses)
- `GET /api/v1/menu/featured/` — cached 60s via `django-redis`
- DRF throttling: `5/min` on `/auth/login/`, `UserRateThrottle='60/min'` default
- `django-cors-headers` with an explicit allow-list via env var
- `drf-spectacular` → `/api/schema/`, `/api/schema/swagger-ui/`
- Seed command `manage.py seed_demo`: 3 categories, 12 dishes, 6 drinks, 5 modifier groups, 4 tables, 1 admin + 1 cashier + 1 kitchen + 2 customers (credentials documented in README)
- Mobile-devs section in README: endpoint map, WS event schema, error envelope

**E2E**
- Full customer happy path by API only: register → browse featured (hits cache on 2nd call) → browse by category → view item detail → create delivery order → WS-connect to order-track → (cashier marks paid) → WS receives `order.updated: confirmed` → (kitchen marks ready) → WS receives `order.updated: ready`
- Throttling: 6th `/auth/login/` attempt within a minute → 429
- CORS: preflight from allowed origin → 200; from disallowed origin → blocked
- OpenAPI schema validates (schemathesis round-trip on a subset)

### Phase 6 — Polish, Docs, Handoff (week 7)

Make it inheritable.

**Deliverables**
- Django admin polish: list filters, search fields, inline modifiers on MenuItem, read-only timestamps
- Friendly 403/404/500 error pages (role-aware back-link)
- JSON logging to stdout for `web`/`asgi`; request-id middleware
- `/healthz/` (DB + Redis ping), `/readyz/`
- Makefile: `up / down / test / seed / logs / shell / migrate / lint`
- README with: architecture diagram (reuse §4.1), local setup, seed creds, "how to add a new role", "how the WebSocket broadcast works"
- Full regression: every phase's E2E suite runs back-to-back in one CI job

**E2E**
- Smoke suite: register customer → customer creates delivery order → cashier sees it, marks paid → kitchen sees it, marks ready → customer WS receives every transition
- `/healthz/` returns 200 normally; returns 503 when Redis unreachable (verified by `docker compose stop redis` in test)
- 403/404 pages render role-aware nav

## 7. Code layout

```
An_Ling_Long_Ordering_system/
├── backend/
│   ├── rms/                    # settings (base/dev), urls, asgi, wsgi, celery (stub only)
│   ├── accounts/               # User, Role, auth views/serializers, middleware, permissions
│   ├── menu/                   # models, serializers, admin dashboard views, API viewsets
│   ├── orders/                 # models, services, consumers, routing, admin + cashier + kitchen views, API
│   ├── dashboards/             # shared dashboard base view/templates
│   ├── templates/              # base.html (CoreUI), auth/, dashboard/, cashier/, kitchen/, errors/
│   ├── static/                 # coreui/, css/rms.css, js/
│   ├── mediafiles/             # user uploads (volume-mounted)
│   └── tests/
│       ├── unit/               # services, serializers, permissions
│       ├── integration/        # APIClient + channels WebsocketCommunicator
│       └── e2e/                # Playwright per-phase suites
├── docker/
│   ├── Dockerfile.web          # Django + Gunicorn
│   └── Dockerfile.asgi         # Django + Daphne
├── docker-compose.yml
├── Makefile
├── pyproject.toml              # ruff, pytest, pytest-django, pytest-asyncio deps
├── .github/workflows/ci.yml
├── docs/superpowers/
│   ├── specs/                  # this file + follow-ups
│   └── plans/                  # implementation plans
└── README.md
```

## 8. Testing strategy

Pyramid:
- **Unit** (fast, isolated): `services/` logic, serializer validation, permission classes, role helpers. Target: 80%+ coverage on these modules.
- **Integration**: `APIClient` for REST (real DB, real serializers); `channels.testing.WebsocketCommunicator` for consumers; DB fixtures via pytest-django factories.
- **E2E** (Playwright): real browser over `docker compose up` stack. Each phase adds a suite in `tests/e2e/phaseN_*.py`. CI runs them all by phase 6.

CI job order:
```
ruff check → pytest unit → pytest integration → docker compose up -d → pytest e2e → compose down
```

## 9. Open points (resolved at implementation time, not now)

- Secret/env management for dev — `.env` file (gitignored), committed `.env.example`
- Tax rate — fixed at 14% Egypt VAT in Phase 3 (hard-coded in settings); admin-configurable `SiteSettings` model deferred to a post-MVP spec
- Receipt PDF vs HTML — HTML is enough for MVP; PDF export deferred
- Customer delivery fee — not in MVP scope (flat zero)
- Which Python/uv — Python 3.12, `uv` for dependency management (fast, 2026 standard)

## 10. Definition of done (MVP)

All of:
1. `docker compose up` brings the stack up, all health checks green
2. `make seed` populates demo data
3. Admin can fully CRUD the menu from `/dashboard/menu/`
4. Cashier can place a dine-in order from `/cashier/`; within 2 seconds a kitchen user at `/kitchen/` sees the new order card **without refreshing**
5. A customer registered via API can `POST /api/v1/orders/` a delivery order, connect to `ws/order/<uuid>/`, and observe status transitions in real time
6. Cashier cannot open `/dashboard/` or `/kitchen/`; kitchen user cannot open `/cashier/`; customer JWT cannot call any staff URL (all 401/403)
7. Every phase's Playwright E2E suite passes in CI, and the phase-6 smoke suite passes end-to-end in one run
