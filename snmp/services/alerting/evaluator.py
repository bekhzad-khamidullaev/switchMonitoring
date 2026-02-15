from django.conf import settings
from django.utils import timezone

from snmp.models import AlertEvent, AlertRule, MetricSample, MetricSubscription
from .notifier import notify_alert_event


def _is_breach(direction: str, value: float, threshold: float) -> bool:
    if direction == AlertRule.Direction.HIGHER_IS_WORSE:
        return value >= threshold
    return value <= threshold


def _derive_direction(subscription: MetricSubscription) -> str:
    if subscription.binding_id:
        direction = subscription.binding.binding_params.get('threshold_direction')
        if direction in {AlertRule.Direction.HIGHER_IS_WORSE, AlertRule.Direction.LOWER_IS_WORSE}:
            return direction
    return AlertRule.Direction.LOWER_IS_WORSE


def _has_consecutive_state(recent_samples: list[MetricSample], required: int, threshold: float, direction: str, expect_breach: bool) -> bool:
    if len(recent_samples) < required:
        return False

    for i in range(required):
        sample = recent_samples[i]
        is_breach = _is_breach(direction, float(sample.value_float), threshold)
        if is_breach != expect_breach:
            return False
    return True


def evaluate_subscription_thresholds(sample: MetricSample):
    subscription = sample.subscription
    if sample.value_float is None:
        return

    direction = _derive_direction(subscription)
    thresholds = []
    if subscription.warn_threshold is not None:
        thresholds.append((AlertRule.Severity.WARNING, float(subscription.warn_threshold)))
    if subscription.crit_threshold is not None:
        thresholds.append((AlertRule.Severity.CRITICAL, float(subscription.crit_threshold)))

    if not thresholds:
        return

    # Fetch recent samples once to avoid N+1 queries in the loop
    max_required = max(settings.ALERT_MIN_CONSECUTIVE_BREACH, settings.ALERT_MIN_CONSECUTIVE_RECOVERY)
    recent_samples = list(
        MetricSample.objects
        .filter(subscription=subscription, value_float__isnull=False)
        .order_by('-ts')[:max_required]
    )

    # Pre-fetch open events for this subscription
    open_events = {
        event.severity: event
        for event in AlertEvent.objects.filter(
            subscription=subscription,
            state=AlertEvent.State.OPEN
        )
    }

    for severity, threshold in thresholds:
        breached = _is_breach(direction, sample.value_float, threshold)
        open_event = open_events.get(severity)

        if breached and not open_event:
            required = settings.ALERT_MIN_CONSECUTIVE_BREACH
            if not _has_consecutive_state(recent_samples, required, threshold, direction, expect_breach=True):
                continue
            event = AlertEvent.objects.create(
                subscription=subscription,
                severity=severity,
                state=AlertEvent.State.OPEN,
                last_value=sample.value_float,
                message=f'Threshold breached: value={sample.value_float}, threshold={threshold}',
            )
            notify_alert_event(event)

        elif breached and open_event:
            open_event.last_value = sample.value_float
            open_event.save(update_fields=['last_value'])

        elif not breached and open_event:
            required = settings.ALERT_MIN_CONSECUTIVE_RECOVERY
            if not _has_consecutive_state(recent_samples, required, threshold, direction, expect_breach=False):
                continue
            open_event.state = AlertEvent.State.CLOSED
            open_event.closed_at = timezone.now()
            open_event.last_value = sample.value_float
            open_event.save(update_fields=['state', 'closed_at', 'last_value'])
            notify_alert_event(open_event)
