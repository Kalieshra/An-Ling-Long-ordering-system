# Phase 1 — Foundation & Role-Gated Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Django 5 + Postgres + Redis + Daphne stack under Docker Compose with a custom `User` model, JWT auth for customers, session auth for staff, and strict role-gating that is verified by a Playwright E2E suite — so Phase 2 (menu management) can plug in on a solid foundation.

**Architecture:** Greenfield Django project under `backend/`. Dual-role Django: `/api/v1/*` → DRF+JWT, `/dashboard/` `/cashier/` `/kitchen/` → session-auth templates. Role-gating via `AllowedRoleForPath` middleware (web) + `HasRole` DRF permission (API). `db` (Postgres 16), `redis` (Redis 7), `web` (Gunicorn), `asgi` (Daphne) containers; `asgi` idles in Phase 1 (first real consumer arrives Phase 4). TDD per unit + integration + E2E layered tests.

**Tech Stack:** Python 3.12, uv, Django 5.1, djangorestframework, djangorestframework-simplejwt (with token_blacklist), django-cors-headers, channels, channels-redis, daphne, gunicorn, psycopg[binary], pytest, pytest-django, pytest-asyncio, pytest-playwright, ruff.

**Spec reference:** `docs/superpowers/specs/2026-04-24-rms-mvp-design.md` §6 Phase 1 deliverables and E2E tests.

---

## File Structure

Files created in this plan (in execution order):

```
.
├── .gitignore                                          # extended
├── .env.example                                        # created
├── pyproject.toml                                      # created (uv)
├── ruff.toml                                           # created
├── Makefile                                            # created
├── docker-compose.yml                                  # created
├── docker/
│   ├── Dockerfile.web                                  # created
│   └── Dockerfile.asgi                                 # created
├── .github/workflows/ci.yml                            # created
├── README.md                                           # created
└── backend/
    ├── manage.py                                       # created (generated)
    ├── conftest.py                                     # created (pytest config)
    ├── rms/
    │   ├── __init__.py                                 # created
    │   ├── settings/
    │   │   ├── __init__.py                             # created
    │   │   ├── base.py                                 # created
    │   │   └── dev.py                                  # created
    │   ├── urls.py                                     # created
    │   ├── asgi.py                                     # created
    │   └── wsgi.py                                     # created
    ├── accounts/
    │   ├── __init__.py                                 # created
    │   ├── apps.py                                     # created
    │   ├── models.py                                   # created (User, Role)
    │   ├── managers.py                                 # created (UserManager)
    │   ├── admin.py                                    # created
    │   ├── serializers.py                              # created
    │   ├── views_api.py                                # created
    │   ├── views_web.py                                # created
    │   ├── middleware.py                               # created (AllowedRoleForPath)
    │   ├── permissions.py                              # created (HasRole)
    │   ├── urls_api.py                                 # created
    │   ├── urls_web.py                                 # created
    │   └── migrations/
    │       └── __init__.py                             # created (auto)
    ├── templates/
    │   ├── base.html                                   # created (CoreUI)
    │   ├── auth/login.html                             # created
    │   ├── dashboard/home.html                         # created
    │   ├── cashier/home.html                           # created
    │   ├── kitchen/home.html                           # created
    │   ├── 403.html                                    # created
    │   └── 404.html                                    # created
    ├── static/css/rms.css                              # created (minimal)
    └── tests/
        ├── __init__.py                                 # created
        ├── conftest.py                                 # created (fixtures)
        ├── unit/
        │   ├── __init__.py                             # created
        │   ├── test_user_model.py                      # created
        │   ├── test_middleware.py                      # created
        │   └── test_permissions.py                     # created
        ├── integration/
        │   ├── __init__.py                             # created
        │   ├── test_auth_api.py                        # created
        │   └── test_staff_login.py                     # created
        └── e2e/
            ├── __init__.py                             # created
            ├── conftest.py                             # created (seed users)
            └── test_phase1_role_gating.py              # created
```

Responsibilities are cleanly split: `models.py` owns persistence, `managers.py` owns object creation, `middleware.py` owns web role-gating, `permissions.py` owns DRF role-gating, `serializers.py` owns validation, `views_api.py` owns JWT endpoints, `views_web.py` owns session login + placeholder dashboards. Tests are split by speed (unit → integration → e2e) so CI can fail fast.

---

## Task 1: Python project scaffolding (uv + pyproject + ruff)

**Files:**
- Create: `pyproject.toml`
- Create: `ruff.toml`
- Create: `.env.example`
- Modify: `.gitignore` (extend)

- [ ] **Step 1: Check uv is installed**

Run: `uv --version`
Expected: prints version like `uv 0.5.x`. If missing, install via `curl -LsSf https://astral.sh/uv/install.sh | sh`.

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "rms"
version = "0.1.0"
description = "Restaurant Management System (Egypt MVP)"
requires-python = ">=3.12"
dependencies = [
    "django>=5.1,<5.2",
    "djangorestframework>=3.15",
    "djangorestframework-simplejwt[crypto]>=5.3",
    "django-cors-headers>=4.5",
    "channels>=4.1",
    "channels-redis>=4.2",
    "daphne>=4.1",
    "gunicorn>=23.0",
    "psycopg[binary]>=3.2",
    "django-environ>=0.11",
    "pillow>=10.4",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-django>=4.9",
    "pytest-asyncio>=0.24",
    "pytest-playwright>=0.5",
    "ruff>=0.7",
    "ipython>=8.28",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "rms.settings.dev"
python_files = ["test_*.py"]
pythonpath = ["backend"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers"
markers = [
    "e2e: end-to-end tests that require docker compose up",
]
```

- [ ] **Step 3: Create `ruff.toml`**

```toml
line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "W", "I", "B", "UP", "DJ"]
ignore = ["E501"]

[lint.per-file-ignores]
"**/migrations/*" = ["E501", "F401"]
"**/settings/*" = ["F401", "F403", "F405"]
```

- [ ] **Step 4: Create `.env.example`**

Note: hostnames here are what **host-side tools** (makemigrations, pytest-from-host) use. Inside Docker, `docker-compose.yml` overrides these to `db` / `redis` via the `environment:` block.

```
# Django
DJANGO_SETTINGS_MODULE=rms.settings.dev
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,web

# Database — host-side default (compose overrides to db:5432)
POSTGRES_DB=rms
POSTGRES_USER=rms
POSTGRES_PASSWORD=rms
DATABASE_URL=postgres://rms:rms@localhost:5432/rms

# Redis — host-side default (compose overrides to redis:6379)
REDIS_URL=redis://localhost:6379/0
CHANNEL_LAYERS_URL=redis://localhost:6379/1

# JWT
SIMPLE_JWT_SIGNING_KEY=change-me-too

# CORS (explicit allowlist, comma-separated)
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

- [ ] **Step 5: Extend `.gitignore`**

Append to existing `.gitignore`:

```
# uv
.uv/
uv.lock

# Django
backend/staticfiles/
backend/mediafiles/

# pytest
.pytest_cache/
htmlcov/
.coverage
```

- [ ] **Step 6: Initialize venv and install deps**

Run: `uv sync`
Expected: creates `.venv/`, writes `uv.lock`, installs all dependencies.

- [ ] **Step 7: Sanity-check ruff**

Run: `uv run ruff --version`
Expected: prints ruff version.

- [ ] **Step 8: Copy env**

Run: `cp .env.example .env`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml ruff.toml .env.example .gitignore uv.lock
git commit -m "chore: scaffold Python project with uv + ruff + pytest"
```

---

## Task 2: Django project skeleton (`rms/` + `manage.py`)

**Files:**
- Create: `backend/manage.py`
- Create: `backend/rms/__init__.py`
- Create: `backend/rms/settings/__init__.py`
- Create: `backend/rms/settings/base.py`
- Create: `backend/rms/settings/dev.py`
- Create: `backend/rms/urls.py`
- Create: `backend/rms/wsgi.py`
- Create: `backend/rms/asgi.py`

- [ ] **Step 1: Create `backend/manage.py`**

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and available on PYTHONPATH, "
            "and that your virtual environment is activated."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

Make it executable: `chmod +x backend/manage.py`

- [ ] **Step 2: Create empty `__init__.py` files**

```bash
touch backend/rms/__init__.py backend/rms/settings/__init__.py
```

- [ ] **Step 3: Create `backend/rms/settings/base.py`**

```python
"""Base Django settings. Shared between environments."""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    # local
    "accounts",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.AllowedRoleForPath",
]

ROOT_URLCONF = "rms.urls"
WSGI_APPLICATION = "rms.wsgi.application"
ASGI_APPLICATION = "rms.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://rms:rms@db:5432/rms"),
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("CHANNEL_LAYERS_URL", default="redis://redis:6379/1")]},
    },
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

# simplejwt with rotation + blacklist per spec §4.4
from datetime import timedelta  # noqa: E402
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "SIGNING_KEY": env("SIMPLE_JWT_SIGNING_KEY", default=SECRET_KEY),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

# Role-gating: web URL prefixes → required Role
# Consumed by accounts.middleware.AllowedRoleForPath
STAFF_PATH_ROLES = {
    "/dashboard/": "admin",
    "/cashier/": "cashier",
    "/kitchen/": "kitchen",
}
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"  # overridden by role-redirect view
```

- [ ] **Step 4: Create `backend/rms/settings/dev.py`**

```python
"""Dev-only settings. Imports everything from base."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]  # dev only
```

- [ ] **Step 5: Create `backend/rms/urls.py`**

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls_api")),
    path("", include("accounts.urls_web")),
]
```

- [ ] **Step 6: Create `backend/rms/wsgi.py`**

```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms.settings.dev")
application = get_wsgi_application()
```

- [ ] **Step 7: Create `backend/rms/asgi.py`**

```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms.settings.dev")
django_asgi_app = get_asgi_application()

# Phase 4 will add ProtocolTypeRouter with WebSocket routing here.
application = django_asgi_app
```

- [ ] **Step 8: Verify manage.py works (will fail on missing accounts app — that's fine)**

Run: `cd backend && DJANGO_SETTINGS_MODULE=rms.settings.dev uv run --project .. python -c "import django; django.setup()" 2>&1 | head -20`
Expected: `ModuleNotFoundError: No module named 'accounts'` — this is expected; we create `accounts` in Task 4.

- [ ] **Step 9: Commit**

```bash
git add backend/manage.py backend/rms/
git commit -m "feat: django project skeleton with split settings"
```

---

## Task 3: Docker Compose stack (db + redis + web + asgi)

**Files:**
- Create: `docker/Dockerfile.web`
- Create: `docker/Dockerfile.asgi`
- Create: `docker-compose.yml`
- Create: `Makefile`

- [ ] **Step 1: Create `docker/Dockerfile.web`**

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv==0.5.*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend /app/backend
WORKDIR /app/backend
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["gunicorn", "rms.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
```

- [ ] **Step 2: Create `docker/Dockerfile.asgi`**

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv==0.5.*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend /app/backend
WORKDIR /app/backend
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 9000
CMD ["daphne", "-b", "0.0.0.0", "-p", "9000", "rms.asgi:application"]
```

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"]
      interval: 5s
      timeout: 3s
      retries: 10
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    ports:
      - "6379:6379"

  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.web
    restart: unless-stopped
    env_file: .env
    environment:
      # Override .env localhost values to use docker-network hostnames
      DATABASE_URL: postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      CHANNEL_LAYERS_URL: redis://redis:6379/1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app/backend
      - staticfiles:/app/backend/staticfiles
      - mediafiles:/app/backend/mediafiles
    command: >
      sh -c "python manage.py migrate --noinput &&
             python manage.py collectstatic --noinput --clear &&
             gunicorn rms.wsgi:application --bind 0.0.0.0:8000 --workers 3 --reload --access-logfile -"
    ports:
      - "8000:8000"

  asgi:
    build:
      context: .
      dockerfile: docker/Dockerfile.asgi
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      CHANNEL_LAYERS_URL: redis://redis:6379/1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app/backend
    command: daphne -b 0.0.0.0 -p 9000 rms.asgi:application
    ports:
      - "9000:9000"

volumes:
  pgdata:
  redisdata:
  staticfiles:
  mediafiles:
```

- [ ] **Step 4: Create `Makefile`**

```makefile
.PHONY: up down build logs shell migrate test test-unit test-integration test-e2e lint fmt seed

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f web asgi

shell:
	docker compose exec web python manage.py shell

migrate:
	docker compose exec web python manage.py migrate

test: test-unit test-integration

test-unit:
	uv run pytest backend/tests/unit -v

test-integration:
	uv run pytest backend/tests/integration -v

test-e2e:
	uv run pytest backend/tests/e2e -v -m e2e

lint:
	uv run ruff check backend/

fmt:
	uv run ruff format backend/

seed:
	docker compose exec web python manage.py seed_demo
```

- [ ] **Step 5: Smoke-test the build (must skip migrate until Task 4 adds accounts app)**

For now, temporarily override the web command to just run gunicorn without migrate:

```bash
docker compose build db redis
```
Expected: images build without errors. (We don't build `web`/`asgi` until `accounts` exists in Task 4.)

- [ ] **Step 6: Start db + redis only to verify healthchecks**

```bash
docker compose up -d db redis
docker compose ps
```
Expected: both services `healthy` within 30 seconds.

Run: `docker compose exec db pg_isready -U rms`
Expected: `accepting connections`

Run: `docker compose exec redis redis-cli ping`
Expected: `PONG`

- [ ] **Step 7: Tear down**

```bash
docker compose down
```

- [ ] **Step 8: Commit**

```bash
git add docker/ docker-compose.yml Makefile
git commit -m "feat: docker compose stack (postgres, redis, web, asgi)"
```

---

## Task 4: Custom `User` model with `Role` enum (TDD)

**Files:**
- Create: `backend/accounts/__init__.py`
- Create: `backend/accounts/apps.py`
- Create: `backend/accounts/managers.py`
- Create: `backend/accounts/models.py`
- Create: `backend/accounts/migrations/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/unit/__init__.py`
- Create: `backend/tests/unit/test_user_model.py`
- Create: `backend/conftest.py`

- [ ] **Step 1: Create empty package files**

```bash
touch backend/accounts/__init__.py backend/accounts/migrations/__init__.py
touch backend/tests/__init__.py backend/tests/unit/__init__.py
```

- [ ] **Step 2: Create `backend/accounts/apps.py`**

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
```

- [ ] **Step 3: Create `backend/conftest.py`**

```python
"""Top-level pytest config — makes `backend/` importable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 4: Write failing tests first — `backend/tests/unit/test_user_model.py`**

```python
"""Unit tests for the custom User model and Role enum."""
import pytest
from django.core.exceptions import ValidationError

from accounts.models import Role, User


@pytest.mark.django_db
class TestUserModel:
    def test_role_choices_contain_four_mvp_roles(self):
        values = {choice[0] for choice in Role.choices}
        assert values == {"admin", "cashier", "kitchen", "customer"}

    def test_create_user_with_email_succeeds(self):
        user = User.objects.create_user(
            email="alice@example.com", password="s3cret-pw", role=Role.CASHIER
        )
        assert user.email == "alice@example.com"
        assert user.role == "cashier"
        assert user.check_password("s3cret-pw")
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_user_requires_email(self):
        with pytest.raises(ValueError, match="email"):
            User.objects.create_user(email="", password="x", role=Role.CUSTOMER)

    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(
            email="Alice@EXAMPLE.com", password="s3cret-pw", role=Role.CUSTOMER
        )
        assert user.email == "Alice@example.com"  # Django normalizes domain only

    def test_default_role_is_customer(self):
        user = User.objects.create_user(email="bob@example.com", password="s3cret-pw")
        assert user.role == Role.CUSTOMER

    def test_create_superuser_is_admin_role(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="s3cret-pw")
        assert admin.role == Role.ADMIN
        assert admin.is_superuser
        assert admin.is_staff

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == "email"
        assert "email" not in User.REQUIRED_FIELDS  # USERNAME_FIELD can't be in REQUIRED_FIELDS

    def test_email_must_be_unique(self):
        User.objects.create_user(email="dup@example.com", password="s3cret-pw")
        with pytest.raises(Exception):  # IntegrityError at DB layer
            User.objects.create_user(email="dup@example.com", password="s3cret-pw")

    def test_str_returns_email(self):
        user = User.objects.create_user(email="who@example.com", password="s3cret-pw")
        assert str(user) == "who@example.com"

    def test_is_role_helper(self):
        user = User.objects.create_user(
            email="k@example.com", password="s3cret-pw", role=Role.KITCHEN
        )
        assert user.is_role(Role.KITCHEN)
        assert not user.is_role(Role.CASHIER)
```

- [ ] **Step 5: Run tests — expect import failure**

Run: `uv run pytest backend/tests/unit/test_user_model.py -v`
Expected: `ModuleNotFoundError` or `ImportError` on `accounts.models`.

- [ ] **Step 6: Create `backend/accounts/managers.py`**

```python
"""Custom manager for email-based User authentication."""
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Manager that uses email instead of username as the primary identifier."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        from .models import Role

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)
```

- [ ] **Step 7: Create `backend/accounts/models.py`**

```python
"""User and Role models. Session-auth for staff, JWT for customers."""
from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class Role(models.TextChoices):
    ADMIN = "admin", "Administrator"
    CASHIER = "cashier", "Cashier"
    KITCHEN = "kitchen", "Kitchen staff"
    CUSTOMER = "customer", "Customer"


class User(AbstractUser):
    username = None  # disable — we use email
    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.CUSTOMER, db_index=True
    )
    phone = models.CharField(max_length=20, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=["role", "is_active"])]

    def __str__(self) -> str:
        return self.email

    def is_role(self, role: str) -> bool:
        return self.role == role
```

- [ ] **Step 8: Generate the initial migration**

Run:
```bash
docker compose up -d db
uv run python backend/manage.py makemigrations accounts
```
Expected: `Migrations for 'accounts': backend/accounts/migrations/0001_initial.py - Create model User`

- [ ] **Step 9: Run tests — expect pass**

Run: `uv run pytest backend/tests/unit/test_user_model.py -v`
Expected: all 9 tests pass.

- [ ] **Step 10: Verify `makemigrations` is clean (no drift)**

Run: `uv run python backend/manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 11: Commit**

```bash
git add backend/accounts/ backend/tests/ backend/conftest.py
git commit -m "feat(accounts): custom User model with Role enum (admin/cashier/kitchen/customer)"
```

---

## Task 5: JWT auth API — register + login (TDD)

**Files:**
- Create: `backend/accounts/serializers.py`
- Create: `backend/accounts/views_api.py`
- Create: `backend/accounts/urls_api.py`
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_auth_api.py`

- [ ] **Step 1: Create `backend/tests/integration/__init__.py`** (empty)

- [ ] **Step 2: Write failing tests — `backend/tests/integration/test_auth_api.py`**

```python
"""Integration tests for JWT auth endpoints (customer-facing)."""
import pytest
from rest_framework.test import APIClient

from accounts.models import Role, User


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestRegister:
    url = "/api/v1/auth/register/"

    def test_registers_customer_with_valid_payload(self, client):
        resp = client.post(
            self.url,
            {
                "email": "new@example.com",
                "password": "s3cret-pw-long",
                "name": "New User",
                "phone": "+201001234567",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["user"]["email"] == "new@example.com"
        assert resp.data["user"]["role"] == "customer"

        user = User.objects.get(email="new@example.com")
        assert user.role == Role.CUSTOMER
        assert user.first_name == "New User"

    def test_rejects_weak_password(self, client):
        resp = client.post(
            self.url,
            {"email": "x@example.com", "password": "short", "name": "X"},
            format="json",
        )
        assert resp.status_code == 400
        assert "password" in resp.data

    def test_rejects_duplicate_email(self, client):
        User.objects.create_user(email="dup@example.com", password="s3cret-pw-long")
        resp = client.post(
            self.url,
            {"email": "dup@example.com", "password": "s3cret-pw-long", "name": "Dup"},
            format="json",
        )
        assert resp.status_code == 400

    def test_registration_always_creates_customer_role(self, client):
        """Even if payload tries to set role=admin, user must be created as customer."""
        resp = client.post(
            self.url,
            {
                "email": "sneaky@example.com",
                "password": "s3cret-pw-long",
                "name": "Sneaky",
                "role": "admin",
            },
            format="json",
        )
        assert resp.status_code == 201
        user = User.objects.get(email="sneaky@example.com")
        assert user.role == Role.CUSTOMER


@pytest.mark.django_db
class TestLogin:
    url = "/api/v1/auth/login/"

    def test_returns_access_and_refresh_on_valid_credentials(self, client):
        User.objects.create_user(
            email="login@example.com", password="s3cret-pw-long", role=Role.CUSTOMER
        )
        resp = client.post(
            self.url,
            {"email": "login@example.com", "password": "s3cret-pw-long"},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["user"]["email"] == "login@example.com"

    def test_rejects_bad_password(self, client):
        User.objects.create_user(email="login@example.com", password="s3cret-pw-long")
        resp = client.post(
            self.url, {"email": "login@example.com", "password": "wrong"}, format="json"
        )
        assert resp.status_code == 401

    def test_rejects_unknown_email(self, client):
        resp = client.post(
            self.url, {"email": "nobody@example.com", "password": "s3cret-pw-long"}, format="json"
        )
        assert resp.status_code == 401
```

- [ ] **Step 3: Run tests — expect fail (no endpoints yet)**

Run: `uv run pytest backend/tests/integration/test_auth_api.py -v`
Expected: all tests fail with 404 on missing URLs.

- [ ] **Step 4: Create `backend/accounts/serializers.py`**

```python
"""Serializers for auth API endpoints."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Role, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role", "first_name", "phone")
        read_only_fields = ("id", "role")


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        normalized = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value

    def create(self, validated_data):
        # Role is *always* customer for public registration.
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            role=Role.CUSTOMER,
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
```

- [ ] **Step 5: Create `backend/accounts/views_api.py`**

```python
"""Customer-facing auth endpoints (JWT)."""
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {**_tokens_for(user), "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
            )
        return Response(
            {**_tokens_for(user), "user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )
```

- [ ] **Step 6: Create `backend/accounts/urls_api.py`**

```python
from django.urls import path

from .views_api import LoginView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
]
```

- [ ] **Step 7: Create `backend/accounts/urls_web.py` (empty for now, will fill in Task 9)**

```python
from django.urls import path

urlpatterns: list = []
```

- [ ] **Step 8: Run tests — expect pass**

Run: `uv run pytest backend/tests/integration/test_auth_api.py -v`
Expected: all 7 tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/accounts/serializers.py backend/accounts/views_api.py \
        backend/accounts/urls_api.py backend/accounts/urls_web.py \
        backend/tests/integration/
git commit -m "feat(accounts): JWT register + login endpoints"
```

---

## Task 6: Refresh + logout + password-change (TDD)

**Files:**
- Modify: `backend/accounts/views_api.py`
- Modify: `backend/accounts/urls_api.py`
- Modify: `backend/accounts/serializers.py`
- Modify: `backend/tests/integration/test_auth_api.py`

- [ ] **Step 1: Extend tests in `backend/tests/integration/test_auth_api.py`**

Append these classes to the file:

```python
@pytest.mark.django_db
class TestRefresh:
    url = "/api/v1/auth/refresh/"

    def _login(self, client):
        User.objects.create_user(email="r@example.com", password="s3cret-pw-long")
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": "r@example.com", "password": "s3cret-pw-long"},
            format="json",
        )
        return resp.data["refresh"], resp.data["access"]

    def test_refresh_rotates_tokens(self, client):
        refresh, _access = self._login(client)
        resp = client.post(self.url, {"refresh": refresh}, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["refresh"] != refresh  # rotation

    def test_old_refresh_blacklisted_after_rotation(self, client):
        refresh, _access = self._login(client)
        first = client.post(self.url, {"refresh": refresh}, format="json")
        assert first.status_code == 200
        second = client.post(self.url, {"refresh": refresh}, format="json")
        assert second.status_code == 401


@pytest.mark.django_db
class TestLogout:
    url = "/api/v1/auth/logout/"

    def _login(self, client):
        User.objects.create_user(email="o@example.com", password="s3cret-pw-long")
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": "o@example.com", "password": "s3cret-pw-long"},
            format="json",
        )
        return resp.data["refresh"], resp.data["access"]

    def test_logout_blacklists_refresh(self, client):
        refresh, access = self._login(client)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = client.post(self.url, {"refresh": refresh}, format="json")
        assert resp.status_code == 205
        # Using the refresh again must now fail
        resp2 = client.post("/api/v1/auth/refresh/", {"refresh": refresh}, format="json")
        assert resp2.status_code == 401

    def test_logout_requires_auth(self, client):
        resp = client.post(self.url, {"refresh": "whatever"}, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestPasswordChange:
    url = "/api/v1/auth/password/change/"

    def test_changes_password(self, client):
        user = User.objects.create_user(email="p@example.com", password="old-pw-long-enough")
        login = client.post(
            "/api/v1/auth/login/",
            {"email": "p@example.com", "password": "old-pw-long-enough"},
            format="json",
        )
        access = login.data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = client.post(
            self.url,
            {"old_password": "old-pw-long-enough", "new_password": "new-pw-long-enough"},
            format="json",
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password("new-pw-long-enough")

    def test_rejects_wrong_old_password(self, client):
        User.objects.create_user(email="p@example.com", password="old-pw-long-enough")
        login = client.post(
            "/api/v1/auth/login/",
            {"email": "p@example.com", "password": "old-pw-long-enough"},
            format="json",
        )
        access = login.data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = client.post(
            self.url,
            {"old_password": "wrong", "new_password": "new-pw-long-enough"},
            format="json",
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests — expect fail**

Run: `uv run pytest backend/tests/integration/test_auth_api.py -v -k "Refresh or Logout or PasswordChange"`
Expected: failures with 404 on missing URLs.

- [ ] **Step 3: Add `PasswordChangeSerializer` to `backend/accounts/serializers.py`**

Append at the bottom:

```python
class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value
```

- [ ] **Step 4: Extend `backend/accounts/views_api.py` with three new views**

Append to the file:

```python
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import PasswordChangeSerializer


class RefreshView(TokenRefreshView):
    """Thin wrapper — simplejwt handles rotation + blacklist per SIMPLE_JWT settings."""
    permission_classes = [AllowAny]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "refresh token is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            RefreshToken(refresh).blacklist()
        except TokenError as e:
            raise InvalidToken(str(e)) from e
        return Response(status=status.HTTP_205_RESET_CONTENT)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Wrong password."}, status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password changed."}, status=status.HTTP_200_OK)
```

- [ ] **Step 5: Register new URLs in `backend/accounts/urls_api.py`**

Replace file contents with:

```python
from django.urls import path

from .views_api import LoginView, LogoutView, PasswordChangeView, RefreshView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("password/change/", PasswordChangeView.as_view(), name="auth-password-change"),
]
```

- [ ] **Step 6: Run all auth tests**

Run: `uv run pytest backend/tests/integration/test_auth_api.py -v`
Expected: all tests pass (15+).

- [ ] **Step 7: Commit**

```bash
git add backend/accounts/
git commit -m "feat(accounts): refresh rotation, logout blacklist, password-change"
```

---

## Task 7: `HasRole` DRF permission class (TDD)

**Files:**
- Create: `backend/accounts/permissions.py`
- Create: `backend/tests/unit/test_permissions.py`

- [ ] **Step 1: Write failing test `backend/tests/unit/test_permissions.py`**

```python
"""Unit tests for HasRole permission class."""
from unittest.mock import MagicMock

import pytest

from accounts.models import Role
from accounts.permissions import HasRole, IsAdmin, IsCashier, IsKitchen


def _fake_request(authenticated=True, role=Role.CUSTOMER):
    req = MagicMock()
    req.user.is_authenticated = authenticated
    req.user.role = role
    return req


class TestHasRole:
    def test_denies_anonymous(self):
        perm = HasRole(Role.ADMIN)
        assert perm.has_permission(_fake_request(authenticated=False), None) is False

    def test_denies_wrong_role(self):
        perm = HasRole(Role.ADMIN)
        assert perm.has_permission(_fake_request(role=Role.CASHIER), None) is False

    def test_allows_correct_role(self):
        perm = HasRole(Role.ADMIN)
        assert perm.has_permission(_fake_request(role=Role.ADMIN), None) is True

    def test_multiple_roles_allowed(self):
        perm = HasRole(Role.ADMIN, Role.CASHIER)
        assert perm.has_permission(_fake_request(role=Role.CASHIER), None) is True
        assert perm.has_permission(_fake_request(role=Role.KITCHEN), None) is False


class TestPresetPermissions:
    def test_is_admin(self):
        assert IsAdmin().has_permission(_fake_request(role=Role.ADMIN), None)
        assert not IsAdmin().has_permission(_fake_request(role=Role.CUSTOMER), None)

    def test_is_cashier(self):
        assert IsCashier().has_permission(_fake_request(role=Role.CASHIER), None)

    def test_is_kitchen(self):
        assert IsKitchen().has_permission(_fake_request(role=Role.KITCHEN), None)
```

- [ ] **Step 2: Run tests — expect fail**

Run: `uv run pytest backend/tests/unit/test_permissions.py -v`
Expected: `ImportError` on missing module.

- [ ] **Step 3: Create `backend/accounts/permissions.py`**

```python
"""DRF permission classes that check the authenticated user's role."""
from rest_framework.permissions import BasePermission

from .models import Role


class HasRole(BasePermission):
    """Allow access only to users whose role is in `allowed_roles`.

    Usage:
        class MenuAdminViewSet(ViewSet):
            permission_classes = [HasRole(Role.ADMIN)]
    """

    def __init__(self, *allowed_roles: str):
        self.allowed_roles = set(allowed_roles)

    def __call__(self):
        # DRF instantiates permission classes without args; when used with HasRole(Role.X)
        # we return the pre-configured instance from __call__.
        return self

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.role in self.allowed_roles


class IsAdmin(HasRole):
    def __init__(self):
        super().__init__(Role.ADMIN)


class IsCashier(HasRole):
    def __init__(self):
        super().__init__(Role.CASHIER)


class IsKitchen(HasRole):
    def __init__(self):
        super().__init__(Role.KITCHEN)


class IsCustomer(HasRole):
    def __init__(self):
        super().__init__(Role.CUSTOMER)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `uv run pytest backend/tests/unit/test_permissions.py -v`
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/accounts/permissions.py backend/tests/unit/test_permissions.py
git commit -m "feat(accounts): HasRole DRF permission + IsAdmin/IsCashier/IsKitchen presets"
```

---

## Task 8: `AllowedRoleForPath` middleware (TDD)

**Files:**
- Create: `backend/accounts/middleware.py`
- Create: `backend/tests/unit/test_middleware.py`

- [ ] **Step 1: Write failing tests `backend/tests/unit/test_middleware.py`**

```python
"""Unit tests for AllowedRoleForPath middleware.

Behavior:
- /dashboard/, /cashier/, /kitchen/ are "staff paths"
- Anonymous user on a staff path -> redirect to /login/?next=<path>
- Authenticated user with wrong role on a staff path -> 403
- Correct role -> pass through
- Non-staff paths (/, /api/*, /admin/) -> pass through for everyone
"""
from unittest.mock import MagicMock

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from accounts.middleware import AllowedRoleForPath
from accounts.models import Role, User


def _get_response(request):
    return HttpResponse("ok")


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def mw():
    return AllowedRoleForPath(_get_response)


@pytest.mark.django_db
class TestAllowedRoleForPath:
    def test_non_staff_path_passes_through_anonymous(self, rf, mw):
        request = rf.get("/api/v1/menu/items/")
        request.user = MagicMock(is_authenticated=False)
        resp = mw(request)
        assert resp.status_code == 200

    def test_anonymous_on_dashboard_redirects_to_login(self, rf, mw):
        request = rf.get("/dashboard/")
        request.user = MagicMock(is_authenticated=False)
        resp = mw(request)
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]
        assert "next=%2Fdashboard%2F" in resp["Location"]

    def test_cashier_on_dashboard_gets_403(self, rf, mw):
        user = User.objects.create_user(
            email="c@example.com", password="pw-long-enough", role=Role.CASHIER
        )
        request = rf.get("/dashboard/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 403

    def test_admin_on_dashboard_passes(self, rf, mw):
        user = User.objects.create_user(
            email="a@example.com", password="pw-long-enough", role=Role.ADMIN
        )
        request = rf.get("/dashboard/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 200

    def test_customer_on_cashier_gets_403(self, rf, mw):
        user = User.objects.create_user(
            email="cust@example.com", password="pw-long-enough", role=Role.CUSTOMER
        )
        request = rf.get("/cashier/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 403

    def test_kitchen_on_kitchen_passes(self, rf, mw):
        user = User.objects.create_user(
            email="k@example.com", password="pw-long-enough", role=Role.KITCHEN
        )
        request = rf.get("/kitchen/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 200

    def test_deep_url_under_staff_prefix_also_gated(self, rf, mw):
        user = User.objects.create_user(
            email="c@example.com", password="pw-long-enough", role=Role.CASHIER
        )
        request = rf.get("/dashboard/menu/edit/42/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 403
```

- [ ] **Step 2: Run tests — expect fail**

Run: `uv run pytest backend/tests/unit/test_middleware.py -v`
Expected: `ImportError` on `accounts.middleware`.

- [ ] **Step 3: Create `backend/accounts/middleware.py`**

```python
"""Role-gating middleware for staff web dashboards.

Reads STAFF_PATH_ROLES from settings (declared in rms/settings/base.py):
    STAFF_PATH_ROLES = {"/dashboard/": "admin", "/cashier/": "cashier", "/kitchen/": "kitchen"}
"""
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.template.loader import render_to_string


class AllowedRoleForPath:
    def __init__(self, get_response):
        self.get_response = get_response
        # Tuple of (prefix, required_role), ordered by prefix length desc so the longest prefix
        # matches first (cheap way to support nested prefixes in the future).
        self._rules = sorted(
            settings.STAFF_PATH_ROLES.items(), key=lambda kv: len(kv[0]), reverse=True
        )

    def __call__(self, request):
        required = self._required_role(request.path)
        if required is None:
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            next_url = quote(request.get_full_path(), safe="")
            return HttpResponseRedirect(f"{settings.LOGIN_URL}?next={next_url}")

        if user.role != required:
            return self._forbidden(request, required)

        return self.get_response(request)

    def _required_role(self, path: str) -> str | None:
        for prefix, role in self._rules:
            if path.startswith(prefix):
                return role
        return None

    def _forbidden(self, request, required: str):
        context = {"required_role": required, "user_role": getattr(request.user, "role", None)}
        try:
            body = render_to_string("403.html", context, request=request)
        except Exception:
            body = f"Forbidden. This area requires role '{required}'."
        return HttpResponseForbidden(body)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `uv run pytest backend/tests/unit/test_middleware.py -v`
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/accounts/middleware.py backend/tests/unit/test_middleware.py
git commit -m "feat(accounts): AllowedRoleForPath middleware (/dashboard|/cashier|/kitchen)"
```

---

## Task 9: Staff session login + role-based redirect + placeholder dashboards

**Files:**
- Create: `backend/accounts/views_web.py`
- Modify: `backend/accounts/urls_web.py`
- Create: `backend/templates/base.html`
- Create: `backend/templates/auth/login.html`
- Create: `backend/templates/dashboard/home.html`
- Create: `backend/templates/cashier/home.html`
- Create: `backend/templates/kitchen/home.html`
- Create: `backend/templates/403.html`
- Create: `backend/templates/404.html`
- Create: `backend/static/css/rms.css`
- Create: `backend/tests/integration/test_staff_login.py`

- [ ] **Step 1: Write failing tests `backend/tests/integration/test_staff_login.py`**

```python
"""Integration tests for staff login + role-based redirect."""
import pytest
from django.test import Client

from accounts.models import Role, User


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestStaffLogin:
    def _make(self, role, email="s@example.com"):
        return User.objects.create_user(email=email, password="pw-long-enough", role=role)

    def test_get_login_renders(self, client):
        resp = client.get("/login/")
        assert resp.status_code == 200
        assert b"Sign in" in resp.content or b"Login" in resp.content

    def test_admin_login_redirects_to_dashboard(self, client):
        self._make(Role.ADMIN)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        assert resp.status_code == 302
        assert resp["Location"].endswith("/dashboard/")

    def test_cashier_login_redirects_to_cashier(self, client):
        self._make(Role.CASHIER)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        assert resp.status_code == 302
        assert resp["Location"].endswith("/cashier/")

    def test_kitchen_login_redirects_to_kitchen(self, client):
        self._make(Role.KITCHEN)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        assert resp.status_code == 302
        assert resp["Location"].endswith("/kitchen/")

    def test_customer_cannot_use_staff_login(self, client):
        self._make(Role.CUSTOMER)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        # Rendered form with error — 200 with error, no session established
        assert resp.status_code in (200, 403)
        assert "_auth_user_id" not in client.session

    def test_logout_clears_session(self, client):
        user = self._make(Role.ADMIN)
        client.force_login(user)
        resp = client.post("/logout/")
        assert resp.status_code == 302
        assert "_auth_user_id" not in client.session

    def test_dashboard_requires_admin(self, client):
        self._make(Role.CASHIER, email="c@example.com")
        client.login(email="c@example.com", password="pw-long-enough")
        resp = client.get("/dashboard/")
        assert resp.status_code == 403

    def test_cashier_page_renders_for_cashier(self, client):
        user = self._make(Role.CASHIER)
        client.force_login(user)
        resp = client.get("/cashier/")
        assert resp.status_code == 200
        assert b"Cashier" in resp.content

    def test_kitchen_page_renders_for_kitchen(self, client):
        user = self._make(Role.KITCHEN)
        client.force_login(user)
        resp = client.get("/kitchen/")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests — expect fail**

Run: `uv run pytest backend/tests/integration/test_staff_login.py -v`
Expected: failures — no views, no templates yet.

- [ ] **Step 3: Create `backend/accounts/views_web.py`**

```python
"""Session-auth views for staff dashboards."""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import Role

ROLE_LANDING = {
    Role.ADMIN: "/dashboard/",
    Role.CASHIER: "/cashier/",
    Role.KITCHEN: "/kitchen/",
}


@require_http_methods(["GET", "POST"])
def staff_login(request):
    if request.method == "GET":
        return render(request, "auth/login.html")

    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    user = authenticate(request, username=email, password=password)

    if user is None or not user.is_active:
        return render(
            request, "auth/login.html", {"error": "Invalid email or password."}, status=200
        )

    if user.role == Role.CUSTOMER:
        return render(
            request,
            "auth/login.html",
            {"error": "Customer accounts cannot sign in here."},
            status=200,
        )

    login(request, user)
    landing = ROLE_LANDING.get(user.role, "/")
    next_url = request.POST.get("next") or request.GET.get("next") or landing
    return HttpResponseRedirect(next_url)


@require_http_methods(["POST", "GET"])
def staff_logout(request):
    logout(request)
    return redirect("/login/")


@login_required
def dashboard_home(request):
    return render(request, "dashboard/home.html", {"user_role": request.user.role})


@login_required
def cashier_home(request):
    return render(request, "cashier/home.html", {"user_role": request.user.role})


@login_required
def kitchen_home(request):
    return render(request, "kitchen/home.html", {"user_role": request.user.role})
```

- [ ] **Step 4: Replace `backend/accounts/urls_web.py`**

```python
from django.urls import path

from . import views_web

urlpatterns = [
    path("login/", views_web.staff_login, name="staff-login"),
    path("logout/", views_web.staff_logout, name="staff-logout"),
    path("dashboard/", views_web.dashboard_home, name="dashboard-home"),
    path("cashier/", views_web.cashier_home, name="cashier-home"),
    path("kitchen/", views_web.kitchen_home, name="kitchen-home"),
]
```

- [ ] **Step 5: Create `backend/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}RMS{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@coreui/coreui@5.1.2/dist/css/coreui.min.css">
    <link rel="stylesheet" href="/static/css/rms.css">
</head>
<body>
    {% block header %}
    {% if request.user.is_authenticated %}
    <nav class="navbar navbar-light bg-light px-4">
        <span>RMS — {{ request.user.role|capfirst }}</span>
        <span>
            {{ request.user.email }}
            <form method="post" action="/logout/" style="display:inline">
                {% csrf_token %}
                <button type="submit" class="btn btn-link btn-sm">Logout</button>
            </form>
        </span>
    </nav>
    {% endif %}
    {% endblock %}
    <main class="container py-4">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 6: Create `backend/templates/auth/login.html`**

```html
{% extends "base.html" %}
{% block title %}Sign in — RMS{% endblock %}
{% block header %}{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-5">
    <div class="card shadow-sm">
      <div class="card-body">
        <h3 class="card-title mb-4">Sign in</h3>
        {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
        <form method="post" action="/login/">
          {% csrf_token %}
          <input type="hidden" name="next" value="{{ request.GET.next }}">
          <div class="mb-3">
            <label class="form-label">Email</label>
            <input name="email" type="email" class="form-control" required autofocus>
          </div>
          <div class="mb-3">
            <label class="form-label">Password</label>
            <input name="password" type="password" class="form-control" required>
          </div>
          <button class="btn btn-primary w-100" type="submit">Sign in</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Create `backend/templates/dashboard/home.html`**

```html
{% extends "base.html" %}
{% block title %}Admin Dashboard — RMS{% endblock %}
{% block content %}
<h1>Admin Dashboard</h1>
<p class="text-muted">Role: {{ user_role }}</p>
<p>Menu, orders, staff, and reports will appear here as later phases ship.</p>
{% endblock %}
```

- [ ] **Step 8: Create `backend/templates/cashier/home.html`**

```html
{% extends "base.html" %}
{% block title %}Cashier — RMS{% endblock %}
{% block content %}
<h1>Cashier POS</h1>
<p class="text-muted">Role: {{ user_role }}</p>
<p>Phase 3 will render the point-of-sale interface here.</p>
{% endblock %}
```

- [ ] **Step 9: Create `backend/templates/kitchen/home.html`**

```html
{% extends "base.html" %}
{% block title %}Kitchen — RMS{% endblock %}
{% block content %}
<h1>Kitchen Display</h1>
<p class="text-muted">Role: {{ user_role }}</p>
<p>Phase 4 will stream live orders here over WebSocket.</p>
{% endblock %}
```

- [ ] **Step 10: Create `backend/templates/403.html`**

```html
{% extends "base.html" %}
{% block title %}Forbidden — RMS{% endblock %}
{% block content %}
<div class="alert alert-warning">
  <h2>403 — Forbidden</h2>
  <p>This area requires the <strong>{{ required_role|default:"another" }}</strong> role.</p>
  <p>You are signed in as <strong>{{ user_role|default:"anonymous" }}</strong>.</p>
  <a href="/login/" class="btn btn-primary">Sign in as a different user</a>
</div>
{% endblock %}
```

- [ ] **Step 11: Create `backend/templates/404.html`**

```html
{% extends "base.html" %}
{% block title %}Not found — RMS{% endblock %}
{% block content %}
<div class="alert alert-info">
  <h2>404 — Not found</h2>
  <p>The page you requested doesn't exist.</p>
</div>
{% endblock %}
```

- [ ] **Step 12: Create `backend/static/css/rms.css`**

```css
body { font-family: Inter, system-ui, -apple-system, sans-serif; }
.card { border-radius: 0.625rem; }
```

- [ ] **Step 13: Run tests — expect pass**

Run: `uv run pytest backend/tests/integration/test_staff_login.py -v`
Expected: all 9 tests pass. If `test_customer_cannot_use_staff_login` fails because middleware ran before login view returned, check that the form-error branch returns status 200 without logging in — the test tolerates both 200 and 403.

- [ ] **Step 14: Commit**

```bash
git add backend/accounts/views_web.py backend/accounts/urls_web.py \
        backend/templates/ backend/static/ \
        backend/tests/integration/test_staff_login.py
git commit -m "feat(accounts): staff login with role redirect + placeholder dashboards"
```

---

## Task 10: Django admin registration + superuser bootstrap

**Files:**
- Create: `backend/accounts/admin.py`

- [ ] **Step 1: Create `backend/accounts/admin.py`**

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("email", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "phone")
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "phone", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role", "is_staff", "is_superuser")}),
    )
```

- [ ] **Step 2: Verify admin registers without error**

Run: `uv run python backend/manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add backend/accounts/admin.py
git commit -m "feat(accounts): register User in Django admin"
```

---

## Task 11: Bring up compose stack and verify end-to-end manually

- [ ] **Step 1: Build images**

Run: `docker compose build`
Expected: all four images build without errors.

- [ ] **Step 2: Start stack**

Run: `docker compose up -d`
Then: `docker compose ps`
Expected: all services `running` / `healthy` within 30 seconds. If `web` crashes, run `docker compose logs web` and fix.

- [ ] **Step 3: Create a superuser**

Run: `docker compose exec web python manage.py createsuperuser --email admin@rms.local`
Enter password: `admin-pw-long-enough` (pick anything ≥8 chars).

- [ ] **Step 4: Smoke-test browser flow**

Open `http://localhost:8000/login/` — login form renders.
Login with `admin@rms.local` / the password you set. → redirects to `/dashboard/`.
Try `http://localhost:8000/cashier/` → 403 page rendered (CoreUI styled).
Logout via top-right → returns to `/login/`.

- [ ] **Step 5: Smoke-test the API**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"c@rms.local","password":"customer-pw-long","name":"Cust"}'
```
Expected: 201 JSON with `access`, `refresh`, `user.role=customer`.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"c@rms.local","password":"customer-pw-long"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")
echo $TOKEN
```
Expected: a long JWT string.

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/dashboard/ \
  -H "Authorization: Bearer $TOKEN"
```
Expected: `302` (Bearer is ignored by session auth → anonymous → login redirect). For the role-gate to return 403 the user must have a staff session cookie with the wrong role; covered by E2E.

- [ ] **Step 6: Tear down (keep volumes for next runs)**

Run: `docker compose down`

---

## Task 12: Playwright E2E suite for Phase 1 (role-gating)

**Files:**
- Create: `backend/tests/e2e/__init__.py`
- Create: `backend/tests/e2e/conftest.py`
- Create: `backend/tests/e2e/test_phase1_role_gating.py`

- [ ] **Step 1: Install Playwright browsers**

Run: `uv run playwright install chromium`
Expected: Chromium downloaded to `~/.cache/ms-playwright/`.

- [ ] **Step 2: Create `backend/tests/e2e/__init__.py`** (empty)

- [ ] **Step 3: Create `backend/tests/e2e/conftest.py`**

```python
"""E2E fixtures: seed three staff users + one customer via HTTP against live stack.

Assumes `docker compose up -d` is running and a superuser exists OR we create all
fixture users fresh each test run via an idempotent seed HTTP call.

Usage:
    uv run pytest backend/tests/e2e -v -m e2e
"""
import os
import subprocess

import pytest
import requests

BASE_URL = os.environ.get("RMS_BASE_URL", "http://localhost:8000")

SEED_USERS = {
    "admin": {"email": "e2e-admin@rms.local", "password": "admin-pw-long-enough", "role": "admin"},
    "cashier": {"email": "e2e-cashier@rms.local", "password": "cashier-pw-long-enough", "role": "cashier"},
    "kitchen": {"email": "e2e-kitchen@rms.local", "password": "kitchen-pw-long-enough", "role": "kitchen"},
    "customer": {"email": "e2e-customer@rms.local", "password": "customer-pw-long-enough", "role": "customer"},
}


def _seed_via_compose():
    """Create the fixture users via manage.py shell inside the web container. Idempotent."""
    script = (
        "from accounts.models import User, Role\n"
        "users = [\n"
    )
    for u in SEED_USERS.values():
        script += f"    ('{u['email']}', '{u['password']}', Role.{u['role'].upper()}),\n"
    script += (
        "]\n"
        "for email, pw, role in users:\n"
        "    u, _ = User.objects.get_or_create(email=email, defaults={'role': role})\n"
        "    u.role = role\n"
        "    u.set_password(pw)\n"
        "    u.save()\n"
        "print('seeded')\n"
    )
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "shell", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "seeded" in result.stdout, result.stdout + result.stderr


@pytest.fixture(scope="session", autouse=True)
def seed_users():
    """Seed the test users once per session. Requires compose stack up."""
    # Sanity: is the server reachable?
    try:
        requests.get(f"{BASE_URL}/login/", timeout=3)
    except requests.RequestException as e:
        pytest.skip(f"Server not reachable at {BASE_URL}: {e}. Run `docker compose up -d` first.")
    _seed_via_compose()
    yield


@pytest.fixture
def base_url():
    return BASE_URL


@pytest.fixture
def users():
    return SEED_USERS
```

- [ ] **Step 4: Create `backend/tests/e2e/test_phase1_role_gating.py`**

```python
"""Phase 1 E2E: role-gated auth.

Covers the deliverables in spec §6 Phase 1 E2E:
1. Admin lands on /dashboard/; 403 on /cashier/ and /kitchen/
2. Cashier lands on /cashier/; 403 on /dashboard/
3. Kitchen lands on /kitchen/; 403 on /cashier/
4. Customer registered via API cannot reach staff dashboards
5. JWT refresh rotates; logout blacklists
"""
import pytest
import requests
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _login_ui(page: Page, base_url: str, email: str, password: str):
    page.goto(f"{base_url}/login/")
    page.fill("input[name='email']", email)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")


class TestAdminGating:
    def test_admin_lands_on_dashboard(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["admin"]["email"], users["admin"]["password"])
        expect(page).to_have_url(f"{base_url}/dashboard/")
        expect(page.get_by_text("Admin Dashboard")).to_be_visible()

    def test_admin_cannot_open_cashier(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["admin"]["email"], users["admin"]["password"])
        resp = page.goto(f"{base_url}/cashier/")
        assert resp.status == 403
        expect(page.get_by_text("403", exact=False)).to_be_visible()

    def test_admin_cannot_open_kitchen(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["admin"]["email"], users["admin"]["password"])
        resp = page.goto(f"{base_url}/kitchen/")
        assert resp.status == 403


class TestCashierGating:
    def test_cashier_lands_on_cashier(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["cashier"]["email"], users["cashier"]["password"])
        expect(page).to_have_url(f"{base_url}/cashier/")
        expect(page.get_by_text("Cashier POS")).to_be_visible()

    def test_cashier_cannot_open_dashboard(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["cashier"]["email"], users["cashier"]["password"])
        resp = page.goto(f"{base_url}/dashboard/")
        assert resp.status == 403

    def test_cashier_cannot_open_kitchen(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["cashier"]["email"], users["cashier"]["password"])
        resp = page.goto(f"{base_url}/kitchen/")
        assert resp.status == 403


class TestKitchenGating:
    def test_kitchen_lands_on_kitchen(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["kitchen"]["email"], users["kitchen"]["password"])
        expect(page).to_have_url(f"{base_url}/kitchen/")
        expect(page.get_by_text("Kitchen Display")).to_be_visible()

    def test_kitchen_cannot_open_cashier(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["kitchen"]["email"], users["kitchen"]["password"])
        resp = page.goto(f"{base_url}/cashier/")
        assert resp.status == 403


class TestCustomerJwtCannotReachStaff:
    def test_customer_jwt_bearer_does_not_grant_dashboard(self, base_url, users):
        """JWT is for /api/v1/*; staff dashboards use sessions. A JWT in the header should
        never grant access to /dashboard/."""
        resp = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": users["customer"]["email"], "password": users["customer"]["password"]},
            timeout=5,
        )
        assert resp.status_code == 200
        access = resp.json()["access"]

        # Follow_redirects=False so the middleware's login redirect is visible
        dash = requests.get(
            f"{base_url}/dashboard/",
            headers={"Authorization": f"Bearer {access}"},
            allow_redirects=False,
            timeout=5,
        )
        # Either redirect-to-login (302) or forbidden (403) — both deny access.
        assert dash.status_code in (302, 403)
        if dash.status_code == 302:
            assert "/login/" in dash.headers.get("Location", "")

    def test_customer_cannot_login_via_staff_form(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["customer"]["email"], users["customer"]["password"])
        # Should stay on /login/ with an error, not navigate to any dashboard
        expect(page).to_have_url(f"{base_url}/login/")
        expect(page.get_by_text("Customer accounts cannot sign in here.")).to_be_visible()


class TestJwtRotationAndBlacklist:
    def test_refresh_rotates_and_old_is_blacklisted(self, base_url, users):
        login = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": users["customer"]["email"], "password": users["customer"]["password"]},
            timeout=5,
        )
        refresh = login.json()["refresh"]
        first = requests.post(
            f"{base_url}/api/v1/auth/refresh/", json={"refresh": refresh}, timeout=5
        )
        assert first.status_code == 200
        assert first.json()["refresh"] != refresh
        second = requests.post(
            f"{base_url}/api/v1/auth/refresh/", json={"refresh": refresh}, timeout=5
        )
        assert second.status_code == 401

    def test_logout_blacklists_refresh(self, base_url, users):
        login = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": users["customer"]["email"], "password": users["customer"]["password"]},
            timeout=5,
        )
        access = login.json()["access"]
        refresh = login.json()["refresh"]
        out = requests.post(
            f"{base_url}/api/v1/auth/logout/",
            json={"refresh": refresh},
            headers={"Authorization": f"Bearer {access}"},
            timeout=5,
        )
        assert out.status_code == 205
        again = requests.post(
            f"{base_url}/api/v1/auth/refresh/", json={"refresh": refresh}, timeout=5
        )
        assert again.status_code == 401
```

- [ ] **Step 5: Ensure compose stack is up**

Run: `docker compose up -d && sleep 5 && docker compose ps`
Expected: all services healthy.

- [ ] **Step 6: Run the E2E suite**

Run: `uv run pytest backend/tests/e2e -v -m e2e`
Expected: all tests pass. If seeding fails because the web container isn't found, confirm you're in the project root and `docker compose ps` shows `web`.

- [ ] **Step 7: Tear down (optional)**

Run: `docker compose down`

- [ ] **Step 8: Commit**

```bash
git add backend/tests/e2e/
git commit -m "test(e2e): phase 1 role-gating suite with playwright"
```

---

## Task 13: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-unit:
    runs-on: ubuntu-24.04
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping" --health-interval 5s --health-retries 5
    env:
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/postgres
      DJANGO_SECRET_KEY: ci-secret
      DJANGO_DEBUG: "0"
      CHANNEL_LAYERS_URL: redis://localhost:6379/1
      CORS_ALLOWED_ORIGINS: ""
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"
      - run: uv sync
      - name: Ruff
        run: uv run ruff check backend/
      - name: Pytest (unit + integration)
        run: uv run pytest backend/tests/unit backend/tests/integration -v

  build-and-e2e:
    runs-on: ubuntu-24.04
    needs: lint-and-unit
    steps:
      - uses: actions/checkout@v4
      - run: cp .env.example .env
      - run: docker compose build
      - run: docker compose up -d
      - name: Wait for /login/
        run: |
          for i in {1..30}; do
            if curl -sf http://localhost:8000/login/ >/dev/null; then echo healthy; exit 0; fi
            sleep 2
          done
          docker compose logs web
          exit 1
      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"
      - run: uv sync
      - run: uv run playwright install --with-deps chromium
      - name: E2E
        env:
          RMS_BASE_URL: http://localhost:8000
        run: uv run pytest backend/tests/e2e -v -m e2e
      - if: failure()
        run: docker compose logs
      - if: always()
        run: docker compose down -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: github actions for lint + unit/integration + e2e"
```

---

## Task 14: README for Phase 1

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# An Ling Long — Restaurant Management System

Production-oriented RMS for the Egyptian market. Dashboards for admin / cashier / kitchen, and a REST + WebSocket API for a future customer mobile app. Real-time kitchen display via Django Channels.

## Phase 1 status — complete

- Django 5 project + apps scaffolded
- Custom `User` with 4 roles (admin / cashier / kitchen / customer)
- JWT auth for customers (`/api/v1/auth/{register,login,refresh,logout,password/change}/`) with refresh rotation + blacklist
- Session auth for staff (`/login/`) with role-based landing page
- Strict role-gating middleware: `/dashboard/` → admin, `/cashier/` → cashier, `/kitchen/` → kitchen
- Docker Compose: db + redis + web + asgi
- pytest (unit + integration) + Playwright E2E suite passing in CI

## Local setup

```bash
# 1. Copy env
cp .env.example .env
# edit .env if you want to change passwords

# 2. Install Python deps
uv sync

# 3. Build and start
make up
make migrate
docker compose exec web python manage.py createsuperuser --email admin@rms.local

# 4. Visit
open http://localhost:8000/login/
```

## Running tests

```bash
# Unit + integration (needs Postgres running; stack will start it)
make test

# E2E (needs full compose stack up)
make up
uv run playwright install chromium
make test-e2e
```

## Seed credentials (after createsuperuser)

The Playwright E2E suite seeds its own users at `e2e-{admin,cashier,kitchen,customer}@rms.local` with per-role passwords — see `backend/tests/e2e/conftest.py`.

## Architecture

See `docs/superpowers/specs/2026-04-24-rms-mvp-design.md` §4.

## Next phases

- Phase 2: Menu management (Category, MenuItem, Modifier, Ingredient) — admin CRUD + read API
- Phase 3: Orders (cashier POS + customer API; non-realtime kitchen)
- Phase 4: Real-time kitchen via Django Channels + Redis
- Phase 5: Customer API polish (profile, featured menu, OpenAPI schema, throttling, CORS)
- Phase 6: Docs, healthz, admin polish, handoff
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: phase 1 readme with setup + status"
```

---

## Task 15: Full regression run

- [ ] **Step 1: Tear down any stale state**

Run: `docker compose down -v`

- [ ] **Step 2: Lint**

Run: `uv run ruff check backend/`
Expected: `All checks passed!`

- [ ] **Step 3: Unit tests**

Run: `uv run pytest backend/tests/unit -v`
Expected: all pass (20+).

- [ ] **Step 4: Integration tests**

Run: `uv run pytest backend/tests/integration -v`
Expected: all pass (15+).

- [ ] **Step 5: Build + start**

Run: `docker compose up -d --build && sleep 10 && docker compose ps`
Expected: all services healthy.

- [ ] **Step 6: E2E**

Run: `uv run pytest backend/tests/e2e -v -m e2e`
Expected: all Playwright + requests tests pass.

- [ ] **Step 7: Final commit if any cleanup**

If lint/test fixes surfaced trivia:

```bash
git add -u
git commit -m "chore: phase 1 final cleanup" --allow-empty
```

- [ ] **Step 8: Tag the milestone**

```bash
git tag -a phase-1-foundation -m "Phase 1 complete: foundation + role-gated auth + E2E"
```

---

## Definition of done (Phase 1)

- [ ] `docker compose up -d` brings all four services healthy within 30s
- [ ] Admin user can log in via `/login/` and lands on `/dashboard/`; hitting `/cashier/` or `/kitchen/` returns 403
- [ ] Cashier and kitchen users are similarly confined to their own URLs
- [ ] `POST /api/v1/auth/register/` creates a customer-role user and returns JWT
- [ ] `POST /api/v1/auth/login/`, `/refresh/`, `/logout/`, `/password/change/` all work
- [ ] Refresh rotation: using the same refresh token twice → second attempt 401
- [ ] Logout: refresh is blacklisted immediately
- [ ] A customer's JWT cannot grant access to any `/dashboard/`, `/cashier/`, `/kitchen/` URL
- [ ] All pytest unit + integration + Playwright E2E tests pass locally and in CI
- [ ] `ruff check backend/` is clean
- [ ] README explains how to get a dev loop running in <5 minutes

When every box is checked, Phase 1 is done and Phase 2 (menu management) can begin on a clean foundation.
