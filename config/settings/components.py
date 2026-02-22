from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


PROD_ENV_NAMES = {"prod", "production"}
LOCAL_HOST_NAMES = {"localhost", "127.0.0.1", "0.0.0.0"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        value = int(default)
    else:
        value = int(raw)

    if minimum is not None and value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise RuntimeError(f"{name} must be <= {maximum}")
    return value


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_host(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if raw == "*":
        return "*"

    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.hostname or raw

    raw = raw.strip().split("/", 1)[0]
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]

    if raw.count(":") == 1 and not raw.startswith("."):
        # host:port (drop port); keep wildcard subdomain notation untouched
        raw = raw.split(":", 1)[0]

    return raw.strip().lower()


def _normalize_origin(value: str) -> str:
    raw = value.strip().rstrip("/")
    if not raw:
        return ""

    if "://" not in raw:
        host = _normalize_host(raw)
        return f"https://{host}" if host else ""

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


@dataclass(frozen=True)
class HostConfig:
    allowed_hosts: list[str]
    csrf_trusted_origins: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed_hosts": list(self.allowed_hosts),
            "csrf_trusted_origins": list(self.csrf_trusted_origins),
        }


@dataclass(frozen=True)
class MetricsConfig:
    poll_interval_sec: int
    poll_async_dispatch: bool
    poll_batch_size: int
    poll_max_queue_depth: int
    discovery_batch_size: int
    discovery_max_queue_depth: int
    retention_enabled: bool
    retention_days: int
    retention_batch_size: int
    retention_max_batches: int
    retention_hour: str
    retention_minute: int
    legacy_tasks_enabled: bool
    autoprovision_enabled: bool
    autoprovision_hour: str
    autoprovision_minute: int
    autoprovision_assign_profiles: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "polling": {
                "interval_sec": self.poll_interval_sec,
                "async_dispatch": self.poll_async_dispatch,
                "batch_size": self.poll_batch_size,
                "max_queue_depth": self.poll_max_queue_depth,
            },
            "discovery": {
                "batch_size": self.discovery_batch_size,
                "max_queue_depth": self.discovery_max_queue_depth,
            },
            "retention": {
                "enabled": self.retention_enabled,
                "days": self.retention_days,
                "batch_size": self.retention_batch_size,
                "max_batches": self.retention_max_batches,
                "schedule": {
                    "hour": self.retention_hour,
                    "minute": self.retention_minute,
                },
            },
            "legacy_tasks_enabled": self.legacy_tasks_enabled,
            "autoprovision": {
                "enabled": self.autoprovision_enabled,
                "schedule": {
                    "hour": self.autoprovision_hour,
                    "minute": self.autoprovision_minute,
                },
                "assign_profiles": self.autoprovision_assign_profiles,
            },
        }


def load_host_config(*, env_name: str) -> HostConfig:
    raw_allowed_hosts = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
    allowed_hosts: list[str] = []
    seen_hosts: set[str] = set()
    for item in raw_allowed_hosts:
        normalized = _normalize_host(item)
        if not normalized or normalized in seen_hosts:
            continue
        seen_hosts.add(normalized)
        allowed_hosts.append(normalized)

    auto_csrf = env_bool("HOST_AUTO_TRUST_CSRF_FROM_ALLOWED_HOSTS", True)
    include_http_local = env_bool("HOST_TRUST_CSRF_HTTP_FOR_LOCALHOST", True)
    include_http_all = env_bool("HOST_TRUST_CSRF_HTTP_FOR_ALL", False)

    raw_csrf = env_list("CSRF_TRUSTED_ORIGINS", "")
    csrf_items: list[str] = []
    if auto_csrf:
        for host in allowed_hosts:
            if host == "*":
                continue

            normalized_host = host.lstrip(".")
            if not normalized_host:
                continue

            if normalized_host in LOCAL_HOST_NAMES:
                csrf_items.append(f"https://{normalized_host}")
                if include_http_local:
                    csrf_items.append(f"http://{normalized_host}")
                continue

            csrf_items.append(f"https://{normalized_host}")
            if include_http_all:
                csrf_items.append(f"http://{normalized_host}")

    csrf_items.extend(raw_csrf)

    csrf_trusted_origins: list[str] = []
    seen_origins: set[str] = set()
    for item in csrf_items:
        normalized = _normalize_origin(item)
        if not normalized or normalized in seen_origins:
            continue
        seen_origins.add(normalized)
        csrf_trusted_origins.append(normalized)

    is_prod = env_name.strip().lower() in PROD_ENV_NAMES
    if is_prod:
        if not allowed_hosts:
            raise RuntimeError("ALLOWED_HOSTS must be set in production")
        if "*" in allowed_hosts and env_bool("ALLOW_WILDCARD_HOSTS_IN_PROD", False) is False:
            raise RuntimeError("ALLOWED_HOSTS cannot contain '*' in production")

    return HostConfig(
        allowed_hosts=allowed_hosts,
        csrf_trusted_origins=csrf_trusted_origins,
    )


def load_metrics_config() -> MetricsConfig:
    return MetricsConfig(
        poll_interval_sec=env_int("POLL_ALL_DEVICES_INTERVAL_SEC", 300, minimum=10),
        poll_async_dispatch=env_bool("POLL_ALL_DEVICES_ASYNC_DISPATCH", True),
        poll_batch_size=env_int("POLL_BATCH_SIZE", 500, minimum=1),
        poll_max_queue_depth=env_int("POLL_MAX_QUEUE_DEPTH", 20000, minimum=1),
        discovery_batch_size=env_int("DISCOVERY_BATCH_SIZE", 200, minimum=1),
        discovery_max_queue_depth=env_int("DISCOVERY_MAX_QUEUE_DEPTH", 1000, minimum=1),
        retention_enabled=env_bool("METRIC_SAMPLE_RETENTION_ENABLED", False),
        retention_days=env_int("METRIC_SAMPLE_RETENTION_DAYS", 30, minimum=1),
        retention_batch_size=env_int("METRIC_SAMPLE_RETENTION_BATCH_SIZE", 20000, minimum=1),
        retention_max_batches=env_int("METRIC_SAMPLE_RETENTION_MAX_BATCHES", 10, minimum=1),
        retention_hour=os.getenv("METRIC_SAMPLE_RETENTION_HOUR", "2"),
        retention_minute=env_int("METRIC_SAMPLE_RETENTION_MINUTE", 20, minimum=0, maximum=59),
        legacy_tasks_enabled=env_bool("LEGACY_TASKS_ENABLED", False),
        autoprovision_enabled=env_bool("AUTOPROVISION_ENABLED", True),
        autoprovision_hour=os.getenv("AUTOPROVISION_HOUR", "3"),
        autoprovision_minute=env_int("AUTOPROVISION_MINUTE", 10, minimum=0, maximum=59),
        autoprovision_assign_profiles=env_bool("AUTOPROVISION_ASSIGN_PROFILES", True),
    )
