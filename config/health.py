from urllib.parse import urlparse

import redis
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

from config.celery import app as celery_app


def _check_db():
    try:
        connection.ensure_connection()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _check_redis():
    broker_url = getattr(settings, "CELERY_BROKER_URL", "")
    if not broker_url:
        return False, "CELERY_BROKER_URL is empty"

    parsed = urlparse(broker_url)
    if not parsed.scheme.startswith("redis"):
        return True, f"skipped: unsupported broker scheme '{parsed.scheme}'"

    try:
        client = redis.Redis.from_url(broker_url, socket_timeout=2, socket_connect_timeout=2)
        client.ping()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _check_celery():
    try:
        inspect = celery_app.control.inspect(timeout=1.5)
        response = inspect.ping() or []
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        workers = list(stats.keys()) if isinstance(stats, dict) else []
        details = {
            "workers": workers,
            "workers_count": len(workers),
            "active_tasks": sum(len(v) for v in active.values()) if isinstance(active, dict) else 0,
            "reserved_tasks": sum(len(v) for v in reserved.values()) if isinstance(reserved, dict) else 0,
        }
        if response:
            return True, "ok", details
        return False, "no active celery workers", details
    except Exception as exc:
        # Keep a stable 3-item contract for callers even on transport/runtime errors.
        return False, str(exc), {}


def _queue_depths():
    broker_url = getattr(settings, "CELERY_BROKER_URL", "")
    parsed = urlparse(broker_url) if broker_url else None
    if not parsed or not parsed.scheme.startswith("redis"):
        return {"supported": False, "reason": "non-redis broker"}

    queue_names = ["default", "polling", "discovery", "maintenance"]
    try:
        client = redis.Redis.from_url(broker_url, socket_timeout=2, socket_connect_timeout=2)
        depths = {name: int(client.llen(name)) for name in queue_names}
        max_depth = max(depths.values()) if depths else 0
        return {
            "supported": True,
            "depths": depths,
            "max_depth": max_depth,
        }
    except Exception as exc:
        return {"supported": True, "error": str(exc)}


def healthcheck_view(request):
    db_ok, db_message = _check_db()
    redis_ok, redis_message = _check_redis()
    celery_result = _check_celery()
    if len(celery_result) == 3:
        celery_ok, celery_message, celery_details = celery_result
    else:
        celery_ok, celery_message = celery_result
        celery_details = {}
    queue_depth = _queue_depths()

    checks = {
        "db": {"ok": db_ok, "message": db_message},
        "redis": {"ok": redis_ok, "message": redis_message},
        "celery": {"ok": celery_ok, "message": celery_message, "details": celery_details},
    }
    overall_ok = all(item["ok"] for item in checks.values())
    status_code = 200 if overall_ok else 503

    return JsonResponse(
        {
            "status": "ok" if overall_ok else "degraded",
            "checks": checks,
            "queues": queue_depth,
        },
        status=status_code,
    )
