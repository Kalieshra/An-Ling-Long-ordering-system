"""E2E fixtures: seed staff + customer users via the running web container.

Requires `docker compose up -d` (the override file maps host ports 15432/16379).
The seed step uses `docker compose exec -T web python manage.py shell` so the
test runner does not need DB credentials on its host.

Run with:
    docker compose up -d
    uv run playwright install chromium
    uv run pytest backend/tests/e2e -v -m e2e
"""
import os
import shutil
import subprocess

import pytest
import requests

BASE_URL = os.environ.get("RMS_BASE_URL", "http://localhost:18000")

SEED_USERS = {
    "admin":    {"email": "e2e-admin@rms.local",    "password": "admin-pw-long-enough",    "role": "admin"},
    "cashier":  {"email": "e2e-cashier@rms.local",  "password": "cashier-pw-long-enough",  "role": "cashier"},
    "kitchen":  {"email": "e2e-kitchen@rms.local",  "password": "kitchen-pw-long-enough",  "role": "kitchen"},
    "customer": {"email": "e2e-customer@rms.local", "password": "customer-pw-long-enough", "role": "customer"},
}


def _seed_via_compose() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not on PATH")
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
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if "seeded" not in result.stdout:
        pytest.skip(
            f"Could not seed users via compose: {result.stdout}\n{result.stderr}"
        )


@pytest.fixture(scope="session", autouse=True)
def seed_users():
    try:
        requests.get(f"{BASE_URL}/login/", timeout=3)
    except requests.RequestException as e:
        pytest.skip(f"Server not reachable at {BASE_URL}: {e}. Run `docker compose up -d` first.")
    _seed_via_compose()
    yield


@pytest.fixture(scope="session")
def base_url():
    # Session-scoped so it composes with pytest-base-url's session-scoped _verify_url.
    return BASE_URL


@pytest.fixture(scope="session")
def users():
    return SEED_USERS
