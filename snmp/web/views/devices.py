import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from snmp.forms import DeviceForm, DeviceHostSettingsForm
from snmp.models import Device, DevicePort, DeviceProfile, MetricSample, MetricSubscription
from snmp.services.metrics.interface_filters import is_eligible_optical_ethernet
from snmp.services.discovery.profile_matcher import match_device_profile

from .access import (
    get_permitted_groups,
    user_can_access_device,
    user_has_global_device_access,
)
from .device_operations import refresh_device_status, update_optical_info
from .metrics import (
    METRICS_SETTINGS_ACTIONS,
    build_device_metrics_context,
    handle_device_metrics_post,
)

logger = logging.getLogger("ICMP RESPONSE")

UP_SEARCH_TOKENS = {'up', 'online', 'alive', 'true', '1'}
DOWN_SEARCH_TOKENS = {'down', 'offline', 'dead', 'false', '0'}
HOST_SETTINGS_ACTIONS = {'save', 'apply_profile_preset', 'recommend_profile', 'clear_profile'}
HOST_SETTINGS_HOST_FIELDS = (
    'ip', 'hostname', 'group', 'subgroup', 'device_type',
    'vendor', 'model', 'firmware', 'sys_object_id', 'profile',
)
HOST_SETTINGS_SNMP_FIELDS = (
    'snmp_version', 'snmp_community_ro', 'snmp_community_rw', 'auth_profile', 'status',
    'uptime', 'switch_mac', 'neighbor', 'parent_port', 'soft_version',
    'serial_number', 'last_discovered_at',
)

SNMP_SENTINEL_PREFIX = "__"
METRIC_TOPIC_RULES = (
    ("System", ("sys_", "snmp_")),
    ("ICMP", ("icmp_",)),
    ("Optical", ("optical_", "rx_", "tx_", "sfp_")),
    ("Interface", ("if_", "port_")),
)


def _first_form_error(form):
    non_field_errors = form.non_field_errors()
    if non_field_errors:
        return non_field_errors[0]
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return 'Please correct the errors below.'


def _get_device_for_user_or_404(user, pk):
    device = get_object_or_404(Device, pk=pk)
    if not user_can_access_device(user, device):
        raise Http404
    return device


def _metric_topic(metric_key):
    key = (metric_key or "").strip().lower()
    for topic, prefixes in METRIC_TOPIC_RULES:
        if key.startswith(prefixes):
            return topic
    return "Other"


def _is_snmp_subscription(subscription):
    oid_template = ""
    if subscription.binding_id and subscription.binding:
        oid_template = (subscription.binding.oid_template or "").strip()
    return bool(oid_template) and not oid_template.startswith(SNMP_SENTINEL_PREFIX)


def _group_subscriptions_by_topic(subscriptions):
    grouped = {}
    ordered_topics = []
    for item in subscriptions:
        topic = _metric_topic(item.metric.key)
        if topic not in grouped:
            grouped[topic] = []
            ordered_topics.append(topic)
        grouped[topic].append(item)
    return [{"topic": topic, "items": grouped[topic]} for topic in ordered_topics]


def _build_host_settings_sections(form):
    host_fields = [form[name] for name in HOST_SETTINGS_HOST_FIELDS if name in form.fields]
    snmp_fields = [form[name] for name in HOST_SETTINGS_SNMP_FIELDS if name in form.fields]
    return {
        'host_fields': host_fields,
        'snmp_fields': snmp_fields,
    }


def _render_device_host_settings(request, device, form, error_message):
    context = {
        'form': form,
        'device': device,
        'error_message': error_message,
        'active_tab': (request.GET.get('tab') or request.POST.get('tab') or 'host').strip() or 'host',
        **_build_host_settings_sections(form),
        **build_device_metrics_context(device),
    }
    return render(request, 'device_host_settings.html', context)


@login_required
def devices(request):
    user_permitted_groups = get_permitted_groups(request.user)
    if user_has_global_device_access(request.user):
        items = Device.objects.all()
    else:
        items = Device.objects.filter(group__in=user_permitted_groups)
    search_query = (request.GET.get('search') or '').strip()
    status_filter = (request.GET.get('status') or '').strip().lower()
    group_filter = (request.GET.get('group') or request.GET.get('branch') or '').strip()
    vendor_filter = (request.GET.get('vendor') or '').strip()

    if status_filter == 'up':
        items = items.filter(status=True)
    elif status_filter == 'down':
        items = items.filter(status=False)

    if group_filter.isdigit():
        items = items.filter(group_id=int(group_filter))

    if vendor_filter.isdigit():
        items = items.filter(device_type__vendor_id=int(vendor_filter))

    if search_query:
        search_filter = (
            Q(pk__icontains=search_query)
            | Q(vendor__icontains=search_query)
            | Q(device_type__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(model__icontains=search_query)
            | Q(device_type__device_model__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
            | Q(switch_ports_reverse__sfp_vendor__icontains=search_query)
            | Q(switch_ports_reverse__part_number__icontains=search_query)
            | Q(switch_ports_reverse__rx_signal__icontains=search_query)
            | Q(switch_ports_reverse__tx_signal__icontains=search_query)
        )
        normalized_query = search_query.lower()
        if normalized_query in UP_SEARCH_TOKENS:
            search_filter |= Q(status=True)
        elif normalized_query in DOWN_SEARCH_TOKENS:
            search_filter |= Q(status=False)
        items = items.filter(search_filter).distinct()

    items = (
        items.select_related('group', 'subgroup', 'device_type__vendor', 'profile')
        .prefetch_related(
            Prefetch(
                'switch_ports_reverse',
                queryset=DevicePort.objects.only('managed_device_id', 'port', 'name', 'rx_signal').order_by('port'),
            )
        )
        .annotate(
            metrics_subscriptions_total=Count('subscriptions', distinct=True),
            metrics_subscriptions_enabled=Count(
                'subscriptions',
                filter=Q(subscriptions__enabled=True),
                distinct=True,
            ),
            metrics_last_sample_ts=Max('subscriptions__samples__ts'),
        )
        .order_by('-pk')
    )

    paginator = Paginator(items, 25)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)

    group_options = sorted(user_permitted_groups, key=lambda group: (group.name or '').lower())
    vendor_base = Device.objects.all() if user_has_global_device_access(request.user) else Device.objects.filter(
        group__in=user_permitted_groups
    )
    vendor_options = (
        vendor_base
        .exclude(device_type__vendor__isnull=True)
        .values('device_type__vendor_id', 'device_type__vendor__name')
        .distinct()
        .order_by('device_type__vendor__name')
    )

    context = {
        'devices': page_items,
        'group_options': group_options,
        'vendor_options': vendor_options,
        'selected_status': status_filter,
        'selected_group': group_filter,
        'selected_vendor': vendor_filter,
        'selected_search': search_query,
    }

    if request.headers.get('HX-Request') == 'true':
        return render(
            request,
            'partials/device_table.html',
            {
                **context,
                'devices_page': page_items,
                'page_title': 'All Devices',
                'page_subtitle': 'Inventory and live status overview',
            },
        )

    return render(request, 'device_list.html', context)


@login_required
def device_detail(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    active_tab = (request.GET.get('tab') or 'overview').strip().lower()
    if active_tab not in {'overview', 'metrics', 'config', 'profile'}:
        active_tab = 'overview'

    latest_sample_query = (
        MetricSample.objects
        .filter(subscription_id=OuterRef('pk'))
        .order_by('-ts', '-id')
    )
    subscriptions = list(
        MetricSubscription.objects
        .filter(device=device)
        .select_related('metric', 'interface', 'binding')
        .annotate(
            last_sample_ts=Subquery(latest_sample_query.values('ts')[:1]),
            last_value_float=Subquery(latest_sample_query.values('value_float')[:1]),
            last_value_text=Subquery(latest_sample_query.values('value_text')[:1]),
            last_quality=Subquery(latest_sample_query.values('quality')[:1]),
        )
        .order_by('interface__if_index', 'metric__key')
    )
    device_level_subscriptions = [item for item in subscriptions if item.interface_id is None]
    interface_level_subscriptions = [item for item in subscriptions if item.interface_id is not None]
    snmp_subscriptions = [item for item in subscriptions if _is_snmp_subscription(item)]
    auxiliary_subscriptions = [item for item in subscriptions if not _is_snmp_subscription(item)]
    snmp_device_level_subscriptions = [item for item in snmp_subscriptions if item.interface_id is None]
    snmp_interface_level_subscriptions = [item for item in snmp_subscriptions if item.interface_id is not None]
    snmp_device_groups = _group_subscriptions_by_topic(snmp_device_level_subscriptions)
    snmp_interface_groups = _group_subscriptions_by_topic(snmp_interface_level_subscriptions)
    auxiliary_groups = _group_subscriptions_by_topic(auxiliary_subscriptions)

    profile_bindings = []
    if device.profile_id:
        profile_bindings = list(
            device.profile.metric_bindings
            .select_related('metric')
            .order_by('priority', 'metric__key')
        )
    optical_port_rows = _build_optical_port_rows(device)
    optical_ports_compact = []
    for row in optical_port_rows:
        port_obj = row['port']
        if_name = row['if_name'] or ''
        rx_value = port_obj.rx_signal if port_obj and port_obj.rx_signal is not None else '-'
        tx_value = port_obj.tx_signal if port_obj and port_obj.tx_signal is not None else '-'
        vendor_value = port_obj.sfp_vendor if port_obj and port_obj.sfp_vendor else ''
        part_value = port_obj.part_number if port_obj and port_obj.part_number else ''
        port_title = f"Port {row['if_index']}"
        if if_name:
            port_title = f"{port_title} · {if_name}"
        compact = f"{port_title}: RX {rx_value} / TX {tx_value} {vendor_value} {part_value}".strip()
        optical_ports_compact.append(compact)
    optical_ports_value = " | ".join(optical_ports_compact) if optical_ports_compact else '-'

    host_config_sections = [
        {
            'title': 'Host identity',
            'items': [
                {'label': 'ID', 'value': device.pk},
                {'label': 'IP', 'value': device.ip},
                {'label': 'Hostname', 'value': device.hostname or '-'},
                {'label': 'Status', 'value': 'Up' if device.status else 'Down'},
                {'label': 'Vendor', 'value': device.display_vendor or '-'},
                {'label': 'Model', 'value': device.display_model or '-'},
                {'label': 'Firmware', 'value': device.firmware or '-'},
                {'label': 'sysObjectID', 'value': device.sys_object_id or '-'},
            ],
        },
        {
            'title': 'Topology and inventory',
            'items': [
                {'label': 'Group', 'value': device.group.name if device.group_id else '-'},
                {'label': 'Subgroup', 'value': device.subgroup.name if device.subgroup_id else '-'},
                {'label': 'Device type', 'value': str(device.device_type) if device.device_type_id else '-'},
                {'label': 'Uptime', 'value': device.uptime or '-'},
                {'label': 'Switch MAC', 'value': device.switch_mac or '-'},
                {'label': 'Neighbor', 'value': str(device.neighbor) if device.neighbor_id else '-'},
                {'label': 'Parent port', 'value': str(device.parent_port) if device.parent_port_id else '-'},
                {'label': 'Serial number', 'value': device.serial_number or '-'},
                {'label': 'Software version', 'value': device.soft_version or '-'},
                {'label': 'Last discovered', 'value': device.last_discovered_at},
                {'label': 'Updated', 'value': device.updated},
            ],
        },
        {
            'title': 'SNMP access',
            'items': [
                {'label': 'SNMP version', 'value': device.get_snmp_version_display()},
                {'label': 'RO community', 'value': device.snmp_community_ro or '-'},
                {'label': 'RW community', 'value': device.snmp_community_rw or '-'},
                {'label': 'Auth profile', 'value': device.auth_profile or '-'},
            ],
        },
        {
            'title': 'Optical and module',
            'items': [
                {'label': 'Optical ports', 'value': optical_ports_value},
                {'label': 'Updated', 'value': device.updated},
            ],
        },
    ]

    metrics_summary = _build_device_metrics_summary(device)
    profile_sections = []
    if device.profile_id:
        profile_sections = [
            {
                'title': 'Profile identity',
                'items': [
                    {'label': 'Profile ID', 'value': device.profile_id},
                    {'label': 'Profile name', 'value': str(device.profile)},
                    {'label': 'Active', 'value': 'Yes' if device.profile.active else 'No'},
                    {'label': 'Priority', 'value': device.profile.priority},
                ],
            },
            {
                'title': 'Matching rules',
                'items': [
                    {'label': 'Vendor', 'value': device.profile.vendor or '-'},
                    {'label': 'Model pattern', 'value': device.profile.model_pattern or '-'},
                    {'label': 'Firmware pattern', 'value': device.profile.firmware_pattern or '-'},
                ],
            },
        ]
    return render(
        request,
        'device_detail.html',
        {
            'device': device,
            'metrics_summary': metrics_summary,
            'active_tab': active_tab,
            'subscriptions': subscriptions,
            'device_level_subscriptions': device_level_subscriptions,
            'interface_level_subscriptions': interface_level_subscriptions,
            'snmp_subscriptions': snmp_subscriptions,
            'snmp_device_groups': snmp_device_groups,
            'snmp_interface_groups': snmp_interface_groups,
            'auxiliary_subscriptions': auxiliary_subscriptions,
            'auxiliary_groups': auxiliary_groups,
            'host_config_sections': host_config_sections,
            'profile_sections': profile_sections,
            'profile_bindings': profile_bindings,
        },
    )


def _build_device_metrics_summary(device):
    metric_subscriptions = MetricSubscription.objects.filter(device=device)
    return {
        'subscriptions_total': metric_subscriptions.count(),
        'subscriptions_enabled': metric_subscriptions.filter(enabled=True).count(),
        'last_sample_ts': (
            MetricSample.objects
            .filter(subscription__device=device)
            .aggregate(last_ts=Max('ts'))
            .get('last_ts')
        ),
    }


def _build_optical_port_rows(device):
    interfaces = list(device.interfaces.all())
    optical_ifaces = [iface for iface in interfaces if is_eligible_optical_ethernet(iface)]
    optical_port_indexes = [iface.if_index for iface in optical_ifaces]
    ports_map = {
        port.port: port
        for port in DevicePort.objects.filter(
            managed_device=device,
            port__in=optical_port_indexes,
        ).order_by('port')
    }
    return [
        {
            'if_index': iface.if_index,
            'if_name': iface.if_name,
            'if_alias': iface.if_alias,
            'port': ports_map.get(iface.if_index),
        }
        for iface in sorted(optical_ifaces, key=lambda item: item.if_index)
    ]


def _render_device_live_panel(request, device):
    optical_port_rows = _build_optical_port_rows(device)
    context = {
        'device': device,
        'metrics_summary': _build_device_metrics_summary(device),
        'optical_port_rows': optical_port_rows,
    }
    return render(request, 'partials/device_live_panel.html', context)


@login_required
@permission_required('snmp.add_device', raise_exception=True)
def device_create(request):
    error_message = None
    if request.method == 'POST':
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save()
            refresh_device_status(device)
            return redirect('device_detail', pk=device.pk)
        error_message = _first_form_error(form)
    else:
        form = DeviceForm()
    return render(request, 'device_form.html', {'form': form, 'error_message': error_message})


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_update(request, pk):
    error_message = None
    device = _get_device_for_user_or_404(request.user, pk)
    if request.method == 'POST':
        form = DeviceForm(request.POST, instance=device)
        if form.is_valid():
            device = form.save()
            return redirect('device_detail', pk=device.pk)
        error_message = _first_form_error(form)
    else:
        form = DeviceForm(instance=device)
    return render(request, 'device_form.html', {'form': form, 'error_message': error_message})


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_host_settings(request, pk):
    error_message = None
    device = _get_device_for_user_or_404(request.user, pk)
    if request.method == 'POST':
        action = (request.POST.get('action') or 'save').strip()
        if action in METRICS_SETTINGS_ACTIONS:
            response = handle_device_metrics_post(request, device)
            if response is not None:
                return response
        elif action not in HOST_SETTINGS_ACTIONS:
            messages.warning(request, f'Unknown settings action: {action}')
            form = DeviceHostSettingsForm(request.POST, instance=device)
            return _render_device_host_settings(request, device, form, error_message)
        if action == 'apply_profile_preset':
            preset_profile_id = (request.POST.get('profile') or '').strip()
            prefill_data = request.POST.copy()
            if preset_profile_id.isdigit():
                profile = get_object_or_404(DeviceProfile, pk=int(preset_profile_id))
                prefill_data['vendor'] = profile.vendor or ''
                prefill_data['model'] = profile.model_pattern or ''
                prefill_data['firmware'] = profile.firmware_pattern or ''
                messages.info(request, 'Preset profile values applied to form. Click "Save settings" to persist.')
            else:
                messages.warning(request, 'Select a preset profile first.')
            form = DeviceHostSettingsForm(prefill_data, instance=device)
            return _render_device_host_settings(request, device, form, error_message)
        if action == 'recommend_profile':
            prefill_data = request.POST.copy()
            vendor = (prefill_data.get('vendor') or '').strip()
            model = (prefill_data.get('model') or '').strip()
            firmware = (prefill_data.get('firmware') or '').strip()
            recommended = match_device_profile(vendor=vendor, model=model, firmware=firmware)
            if recommended:
                prefill_data['profile'] = str(recommended.pk)
                messages.info(
                    request,
                    f'Recommended profile #{recommended.pk} selected '
                    f'({recommended.vendor} / {recommended.model_pattern}). Click "Save settings" to persist.',
                )
            else:
                messages.warning(
                    request,
                    'No active profile matches current vendor/model/firmware. '
                    'Adjust host fields or choose profile manually.',
                )
            form = DeviceHostSettingsForm(prefill_data, instance=device)
            return _render_device_host_settings(request, device, form, error_message)
        if action == 'clear_profile':
            prefill_data = request.POST.copy()
            prefill_data['profile'] = ''
            messages.info(request, 'Profile selection cleared. Click "Save settings" to persist.')
            form = DeviceHostSettingsForm(prefill_data, instance=device)
            return _render_device_host_settings(request, device, form, error_message)

        form = DeviceHostSettingsForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            return redirect('device_detail', pk=device.pk)
        error_message = _first_form_error(form)
    else:
        form = DeviceHostSettingsForm(instance=device)
    return _render_device_host_settings(request, device, form, error_message)


@login_required
@permission_required('snmp.delete_device', raise_exception=True)
def device_delete(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    if request.method == 'POST':
        device.delete()
        if request.headers.get('HX-Request') == 'true':
            response = HttpResponse(status=200)
            response['HX-Redirect'] = reverse('devices')
            return response
        return redirect('devices')
    return render(request, 'device_confirm_delete.html', {'device': device})


@login_required
def device_confirm_delete(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    return render(request, 'device_confirm_delete.html', {'device': device})


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_status(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    return refresh_device_status(device)


@login_required
def device_live_panel(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    return _render_device_live_panel(request, device)


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_refresh_status_panel(request, pk):
    if request.method != 'POST':
        return HttpResponse(status=405)
    device = _get_device_for_user_or_404(request.user, pk)
    refresh_device_status(device)
    device.refresh_from_db()
    return _render_device_live_panel(request, device)


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_refresh_optics_panel(request, pk):
    if request.method != 'POST':
        return HttpResponse(status=405)
    device = _get_device_for_user_or_404(request.user, pk)
    update_response = update_optical_info(request, pk)
    if getattr(update_response, 'status_code', 500) >= 400:
        return HttpResponse(status=502)
    device.refresh_from_db()
    return _render_device_live_panel(request, device)
