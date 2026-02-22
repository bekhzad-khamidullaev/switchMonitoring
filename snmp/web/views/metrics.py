import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from snmp.models import Device, DeviceProfile, MetricBinding, MetricSample, MetricSubscription
from snmp.services.metrics.interface_filters import is_eligible_optical_ethernet
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError
from snmp.services.metrics.registry import get_active_bindings_for_device
from snmp.services.polling.poller import poll_device_metrics

from .access import user_can_access_device

METRICS_SETTINGS_ACTIONS = {
    'run_discovery',
    'poll_now',
    'assign_profile_preset',
    'apply_profile',
    'set_discovery_monitoring',
}


def _validate_thresholds(subscription: MetricSubscription, warn_value, crit_value):
    threshold_error = subscription.validate_thresholds(warn_value=warn_value, crit_value=crit_value)
    if threshold_error == 'crit_threshold must be >= warn_threshold':
        return 'Critical threshold must be greater than or equal to warning threshold.'
    if threshold_error == 'crit_threshold must be <= warn_threshold':
        return 'Critical threshold must be less than or equal to warning threshold.'
    return threshold_error


def _sync_discovered_metric_subscriptions(device, bindings, interfaces):
    created_count = 0
    updated_count = 0
    seen_subscription_ids = set()

    for binding in bindings:
        targets = [None]
        if binding.index_strategy == MetricBinding.IndexStrategy.IF_INDEX:
            targets = interfaces
            if binding.metric.key in {"optical_rx_power", "optical_tx_power"}:
                targets = [iface for iface in targets if is_eligible_optical_ethernet(iface)]
            if not targets:
                continue

        for interface in targets:
            if interface is None:
                subscription = MetricSubscription.objects.filter(
                    device=device,
                    interface__isnull=True,
                    metric=binding.metric,
                ).first()
            else:
                subscription = MetricSubscription.objects.filter(
                    device=device,
                    interface=interface,
                    metric=binding.metric,
                ).first()

            if subscription is None:
                subscription = MetricSubscription.objects.create(
                    device=device,
                    interface=interface,
                    metric=binding.metric,
                    binding=binding,
                    enabled=binding.enabled_by_default,
                    poll_interval_sec=binding.metric.default_interval_sec,
                )
                created_count += 1
            else:
                update_fields = []
                if subscription.binding_id != binding.id:
                    subscription.binding = binding
                    update_fields.append('binding')
                if subscription.poll_interval_sec is None:
                    subscription.poll_interval_sec = binding.metric.default_interval_sec
                    update_fields.append('poll_interval_sec')
                if update_fields:
                    subscription.save(update_fields=update_fields)
                    updated_count += 1

            seen_subscription_ids.add(subscription.id)

    return {
        'created_count': created_count,
        'updated_count': updated_count,
        'discovered_count': len(seen_subscription_ids),
    }


def _redirect_to_next_or_view(request, device, fallback_view='device_host_settings'):
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback_view, pk=device.pk)


def build_device_metrics_context(device):
    bindings = list(get_active_bindings_for_device(device))
    profile_presets = list(
        DeviceProfile.objects
        .filter(active=True)
        .order_by('priority', 'vendor', 'model_pattern')
    )
    interfaces = list(device.interfaces.order_by('if_index'))
    optical_interfaces = [iface for iface in interfaces if is_eligible_optical_ethernet(iface)]
    subscriptions = (
        MetricSubscription.objects
        .filter(device=device)
        .select_related('metric', 'interface', 'binding')
        .order_by('interface__if_index', 'metric__key')
    )
    has_subscriptions = subscriptions.exists()

    discovered_subscriptions = (
        MetricSubscription.objects
        .filter(device=device, binding__isnull=False)
        .select_related('metric', 'interface', 'binding')
        .order_by('metric__key', 'interface__if_index')
    )
    if device.profile_id:
        discovered_subscriptions = discovered_subscriptions.filter(binding__profile_id=device.profile_id)

    return {
        'bindings': bindings,
        'profile_presets': profile_presets,
        'interfaces': interfaces,
        'optical_interfaces': optical_interfaces,
        'subscriptions': subscriptions,
        'discovered_subscriptions': discovered_subscriptions,
        'has_subscriptions': has_subscriptions,
    }


def handle_device_metrics_post(request, device):
    action = (request.POST.get('action') or '').strip()
    if not action or action not in METRICS_SETTINGS_ACTIONS:
        return None
    if not request.user.has_perm('snmp.change_device'):
        return HttpResponse(status=403)

    bindings = list(get_active_bindings_for_device(device))
    interfaces = list(device.interfaces.order_by('if_index'))
    has_subscriptions = MetricSubscription.objects.filter(device=device).exists()

    if action == 'run_discovery':
        community = request.POST.get('community', '').strip() or device.snmp_community_ro or 'public'
        try:
            result = run_device_discovery(ip=str(device.ip), community=community, managed_device=device)
            device.refresh_from_db()
            refreshed_bindings = list(get_active_bindings_for_device(device))
            refreshed_interfaces = list(device.interfaces.order_by('if_index'))
            sync_stats = _sync_discovered_metric_subscriptions(
                device=device,
                bindings=refreshed_bindings,
                interfaces=refreshed_interfaces,
            )
            messages.success(
                request,
                (
                    "Discovery completed: "
                    f"vendor={result.get('vendor', '-') or '-'} "
                    f"model={result.get('model', '-') or '-'} "
                    f"profile_id={result.get('profile_id', 0)} "
                    f"interfaces={result.get('interfaces_count', 0)} "
                    f"metrics={sync_stats.get('discovered_count', 0)}"
                ),
            )
            if not result.get('profile_id'):
                messages.warning(request, 'No exact profile was matched; generic fallback was used if available.')
        except SnmpReadError as exc:
            messages.error(request, f'Discovery failed: {exc}')
        return _redirect_to_next_or_view(request, device)

    if action == 'poll_now':
        if not has_subscriptions:
            messages.warning(request, 'No active subscriptions yet. Apply profile metrics first.')
            return _redirect_to_next_or_view(request, device)
        saved_count = poll_device_metrics(device.id)
        messages.success(request, f'Polling completed. Saved samples: {saved_count}.')
        return _redirect_to_next_or_view(request, device)

    if action == 'assign_profile_preset':
        profile_id = (request.POST.get('profile_id') or '').strip()
        if not profile_id.isdigit():
            messages.warning(request, 'Select a profile preset first.')
            return _redirect_to_next_or_view(request, device)

        profile = DeviceProfile.objects.filter(pk=int(profile_id), active=True).first()
        if not profile:
            messages.error(request, 'Selected profile preset was not found or is inactive.')
            return _redirect_to_next_or_view(request, device)

        if device.profile_id == profile.id:
            messages.info(request, f'Profile preset "{profile}" is already assigned to this host.')
            return _redirect_to_next_or_view(request, device)

        device.profile = profile
        device.save(update_fields=['profile'])
        messages.success(request, f'Profile preset "{profile}" assigned to host.')
        return _redirect_to_next_or_view(request, device)

    if action == 'apply_profile':
        selected_binding_ids = request.POST.getlist('binding_ids')
        scope = request.POST.get('scope', 'optical')

        selected_bindings = [binding for binding in bindings if str(binding.id) in selected_binding_ids]
        if not selected_bindings:
            messages.warning(request, 'Select at least one metric binding.')
            return _redirect_to_next_or_view(request, device)

        if scope == 'device':
            target_interfaces = [None]
        elif scope == 'all':
            target_interfaces = interfaces
        else:
            target_interfaces = [iface for iface in interfaces if is_eligible_optical_ethernet(iface)]

        created_or_updated = 0
        for binding in selected_bindings:
            binding_interfaces = target_interfaces
            if (
                binding.index_strategy == MetricBinding.IndexStrategy.IF_INDEX
                and binding.metric.key in {"optical_rx_power", "optical_tx_power"}
            ):
                binding_interfaces = [iface for iface in target_interfaces if iface and is_eligible_optical_ethernet(iface)]
            for interface in binding_interfaces:
                defaults = {
                    'binding': binding,
                    'enabled': True,
                    'poll_interval_sec': binding.metric.default_interval_sec,
                }
                if interface is None:
                    MetricSubscription.objects.update_or_create(
                        device=device,
                        interface__isnull=True,
                        metric=binding.metric,
                        defaults={**defaults, 'interface': None},
                    )
                else:
                    MetricSubscription.objects.update_or_create(
                        device=device,
                        interface=interface,
                        metric=binding.metric,
                        defaults=defaults,
                    )
                created_or_updated += 1

        messages.success(request, f'Applied {created_or_updated} metric subscriptions.')
        return _redirect_to_next_or_view(request, device)

    if action == 'set_discovery_monitoring':
        selected_ids = {
            int(item)
            for item in request.POST.getlist('enabled_subscription_ids')
            if str(item).isdigit()
        }
        discovered_qs = MetricSubscription.objects.filter(device=device, binding__isnull=False)
        if device.profile_id:
            discovered_qs = discovered_qs.filter(binding__profile_id=device.profile_id)

        discovered_ids = list(discovered_qs.values_list('id', flat=True))
        if not discovered_ids:
            messages.warning(request, 'No discovered metrics found to update.')
            return _redirect_to_next_or_view(request, device)

        with transaction.atomic():
            MetricSubscription.objects.filter(id__in=discovered_ids).update(enabled=False)
            if selected_ids:
                selected_discovered_ids = [item for item in discovered_ids if item in selected_ids]
                MetricSubscription.objects.filter(id__in=selected_discovered_ids).update(enabled=True)

        enabled_count = MetricSubscription.objects.filter(id__in=discovered_ids, enabled=True).count()
        messages.success(
            request,
            f'Monitoring updated for discovered metrics: enabled={enabled_count}, disabled={len(discovered_ids) - enabled_count}.',
        )
        return _redirect_to_next_or_view(request, device)

    return None


@login_required
def device_metrics(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if not user_can_access_device(request.user, device):
        return HttpResponse(status=403)
    if request.method == 'POST':
        response = handle_device_metrics_post(request, device)
        if response is not None:
            return response
    return redirect(f"{reverse('device_host_settings', args=[device.pk])}?tab=metrics")


@login_required
@permission_required('snmp.change_metricsubscription', raise_exception=True)
@require_POST
def update_metric_subscription(request, subscription_id):
    subscription = get_object_or_404(MetricSubscription, pk=subscription_id)
    if not user_can_access_device(request.user, subscription.device):
        return HttpResponse(status=403)

    subscription.enabled = request.POST.get('enabled') == 'on'

    warn = request.POST.get('warn_threshold', '').strip()
    crit = request.POST.get('crit_threshold', '').strip()
    poll = request.POST.get('poll_interval_sec', '').strip()

    try:
        subscription.warn_threshold = float(warn) if warn else None
        subscription.crit_threshold = float(crit) if crit else None
        subscription.poll_interval_sec = int(poll) if poll else None
    except ValueError:
        messages.error(request, 'Invalid numeric value in thresholds or poll interval.')
        return _redirect_to_next_or_view(request, subscription.device)

    threshold_error = _validate_thresholds(
        subscription=subscription,
        warn_value=subscription.warn_threshold,
        crit_value=subscription.crit_threshold,
    )
    if threshold_error:
        messages.error(request, threshold_error)
        return _redirect_to_next_or_view(request, subscription.device)

    subscription.save(update_fields=['enabled', 'warn_threshold', 'crit_threshold', 'poll_interval_sec'])

    messages.success(request, 'Subscription updated.')
    return _redirect_to_next_or_view(request, subscription.device)


@login_required
@permission_required('snmp.view_metricsample', raise_exception=True)
def export_device_metrics_csv(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if not user_can_access_device(request.user, device):
        return HttpResponse(status=403)

    metric = request.GET.get('metric', '').strip()
    if_index = request.GET.get('if_index', '').strip()
    limit = request.GET.get('limit', '1000').strip()

    try:
        limit_value = max(1, min(int(limit), 10000))
    except ValueError:
        limit_value = 1000

    queryset = (
        MetricSample.objects
        .filter(device=device)
        .select_related('subscription', 'subscription__metric', 'subscription__interface')
    )
    if metric:
        queryset = queryset.filter(subscription__metric__key=metric)
    if if_index:
        try:
            if_index_value = int(if_index)
        except ValueError:
            if_index_value = None
        if if_index_value is not None:
            queryset = queryset.filter(subscription__interface__if_index=if_index_value)

    samples = queryset.order_by('-ts', '-id')[:limit_value]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="device_{device.id}_metrics.csv"'
    writer = csv.writer(response)
    writer.writerow(['ts', 'metric', 'if_index', 'value_float', 'value_text', 'quality', 'raw_value'])
    for sample in samples:
        subscription = sample.subscription
        writer.writerow([
            sample.ts.isoformat(),
            subscription.metric.key,
            subscription.interface.if_index if subscription.interface_id else '',
            sample.value_float if sample.value_float is not None else '',
            sample.value_text,
            sample.quality,
            sample.raw_value,
        ])

    return response


@login_required
@permission_required('snmp.view_metricsample', raise_exception=True)
def device_metrics_timeseries_table(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if not user_can_access_device(request.user, device):
        return HttpResponse(status=403)

    metric = (request.GET.get('metric') or '').strip()
    if_index = (request.GET.get('if_index') or '').strip()
    limit = (request.GET.get('limit') or '50').strip()
    try:
        limit_value = max(10, min(int(limit), 500))
    except ValueError:
        limit_value = 50

    queryset = (
        MetricSample.objects
        .filter(device=device)
        .select_related('subscription', 'subscription__metric', 'subscription__interface')
    )
    if metric:
        queryset = queryset.filter(subscription__metric__key=metric)
    if if_index:
        try:
            if_index_value = int(if_index)
            queryset = queryset.filter(subscription__interface__if_index=if_index_value)
        except ValueError:
            if_index_value = None
    else:
        if_index_value = None

    samples = list(queryset.order_by('-ts', '-id')[:limit_value])

    return render(
        request,
        'partials/metric_timeseries_table.html',
        {
            'device': device,
            'samples': samples,
            'selected_metric': metric,
            'selected_if_index': if_index_value,
        },
    )
