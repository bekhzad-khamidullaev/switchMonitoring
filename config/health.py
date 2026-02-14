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
        response = celery_app.control.ping(timeout=1.5)
        if response:
            return True, "ok"
        return False, "no active celery workers"
    except Exception as exc:
        return False, str(exc)


def healthcheck_view(request):
    db_ok, db_message = _check_db()
    redis_ok, redis_message = _check_redis()
    celery_ok, celery_message = _check_celery()

    checks = {
        "db": {"ok": db_ok, "message": db_message},
        "redis": {"ok": redis_ok, "message": redis_message},
        "celery": {"ok": celery_ok, "message": celery_message},
    }
    overall_ok = all(item["ok"] for item in checks.values())
    status_code = 200 if overall_ok else 503

    return JsonResponse(
        {
            "status": "ok" if overall_ok else "degraded",
            "checks": checks,
        },
        status=status_code,
    )
