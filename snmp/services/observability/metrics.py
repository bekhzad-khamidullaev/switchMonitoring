import time
from typing import Dict

from django.core.cache import cache

from config.celery import app as celery_app

POLL_TOTAL_KEY = "metrics:poll_total"
POLL_DURATION_MS_TOTAL_KEY = "metrics:poll_duration_ms_total"
SAMPLES_TOTAL_KEY = "metrics:samples_total"
SNMP_ERRORS_TOTAL_KEY = "metrics:snmp_errors_total"
LAST_POLL_TS_KEY = "metrics:last_poll_ts"


def _incr(key: str, delta: int = 1) -> None:
    try:
        cache.incr(key, delta)
    except Exception:
        current = cache.get(key, 0) or 0
        cache.set(key, current + delta)


def record_poll_metrics(duration_ms: int, samples_saved: int, snmp_errors: int) -> None:
    _incr(POLL_TOTAL_KEY, 1)
    _incr(POLL_DURATION_MS_TOTAL_KEY, max(0, int(duration_ms)))
    _incr(SAMPLES_TOTAL_KEY, max(0, int(samples_saved)))
    _incr(SNMP_ERRORS_TOTAL_KEY, max(0, int(snmp_errors)))
    cache.set(LAST_POLL_TS_KEY, int(time.time()))


def _celery_queue_depth() -> Dict[str, int]:
    try:
        inspect = celery_app.control.inspect(timeout=1.5)
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        scheduled = inspect.scheduled() or {}
        return {
            "active": sum(len(items or []) for items in active.values()),
            "reserved": sum(len(items or []) for items in reserved.values()),
            "scheduled": sum(len(items or []) for items in scheduled.values()),
        }
    except Exception:
        return {"active": -1, "reserved": -1, "scheduled": -1}


def get_metrics_snapshot() -> Dict[str, object]:
    poll_total = int(cache.get(POLL_TOTAL_KEY, 0) or 0)
    duration_total = int(cache.get(POLL_DURATION_MS_TOTAL_KEY, 0) or 0)
    samples_total = int(cache.get(SAMPLES_TOTAL_KEY, 0) or 0)
    snmp_errors_total = int(cache.get(SNMP_ERRORS_TOTAL_KEY, 0) or 0)

    avg_poll_ms = float(duration_total / poll_total) if poll_total else 0.0
    queue_depth = _celery_queue_depth()

    return {
        "poll": {
            "total": poll_total,
            "avg_duration_ms": round(avg_poll_ms, 2),
            "samples_total": samples_total,
            "snmp_errors_total": snmp_errors_total,
            "last_poll_ts": cache.get(LAST_POLL_TS_KEY),
        },
        "celery": {
            "queue_depth": queue_depth,
        },
    }
