import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in ("device_id", "profile_id", "interfaces_count", "subscriptions", "samples_saved", "ip", "warnings"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            try:
                payload["exception"] = self.formatException(record.exc_info)
            except Exception as exc:  # pragma: no cover - defensive path for broken traceback objects
                payload["exception"] = f"failed to format exception: {exc!r}"

        return json.dumps(payload, ensure_ascii=True)
