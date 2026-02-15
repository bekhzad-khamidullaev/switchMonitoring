import logging

import requests
from django.conf import settings
from django.core.mail import send_mail

from snmp.models import AlertEvent

logger = logging.getLogger(__name__)


def _build_message(event: AlertEvent) -> str:
    sub = event.subscription
    device = sub.device
    metric = sub.metric
    iface = f"ifIndex={sub.interface.if_index}" if sub.interface_id else 'device-level'
    return (
        f"[{event.state.upper()}] {event.severity.upper()} "
        f"{device.ip} {metric.key} {iface} value={event.last_value}"
    )


def notify_alert_event(event: AlertEvent) -> None:
    message = _build_message(event)

    if settings.ALERT_EMAIL_TO:
        try:
            send_mail(
                subject=f"Device monitoring alert: {event.severity} {event.state}",
                message=message,
                from_email=settings.ALERT_EMAIL_FROM,
                recipient_list=settings.ALERT_EMAIL_TO,
                fail_silently=True,
            )
        except Exception as exc:
            logger.warning('alert email notification failed', extra={'error': str(exc)})

    if settings.ALERT_WEBHOOK_URL:
        try:
            requests.post(
                settings.ALERT_WEBHOOK_URL,
                json={
                    'event_id': event.id,
                    'state': event.state,
                    'severity': event.severity,
                    'subscription_id': event.subscription_id,
                    'value': event.last_value,
                    'message': message,
                },
                timeout=settings.ALERT_NOTIFY_TIMEOUT,
            )
        except Exception as exc:
            logger.warning('alert webhook notification failed', extra={'error': str(exc)})
