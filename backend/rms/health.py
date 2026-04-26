"""Liveness + readiness probes.

`GET /healthz/` exercises the things that would prevent a request from being
served correctly: the database (one SELECT) and the cache (one round-trip).
Each check is wrapped in its own try-block so a failed dep produces a 503
with a detail field — useful for ops dashboards.

`GET /readyz/` is intentionally trivial: returns 200 as soon as Django has
booted. It exists so a load-balancer / k8s liveness probe can distinguish
"process is alive" from "process is healthy AND deps are reachable".
"""
from dataclasses import dataclass

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


@dataclass
class HealthStatus:
    ok: bool
    detail: str


def _check_db() -> HealthStatus:
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
        return HealthStatus(True, "ok")
    except Exception as e:  # noqa: BLE001 — health check should catch everything
        return HealthStatus(False, str(e))


def _check_cache() -> HealthStatus:
    try:
        cache.set("__healthz__", "1", 5)
        if cache.get("__healthz__") != "1":
            return HealthStatus(False, "cache round-trip failed")
        return HealthStatus(True, "ok")
    except Exception as e:  # noqa: BLE001
        return HealthStatus(False, str(e))


def healthz(request):
    db = _check_db()
    cc = _check_cache()
    payload = {
        "status": "ok" if (db.ok and cc.ok) else "degraded",
        "checks": {
            "db": {"ok": db.ok, "detail": db.detail},
            "cache": {"ok": cc.ok, "detail": cc.detail},
        },
    }
    code = 200 if (db.ok and cc.ok) else 503
    return JsonResponse(payload, status=code)


def readyz(request):
    return JsonResponse({"status": "ok"})
