import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from snmp.forms import DeviceForm, DeviceHostSettingsForm
from snmp.models import Device, DeviceProfile
from snmp.services.discovery.profile_matcher import match_device_profile

from .access import (
    get_permitted_groups,
    user_can_access_device,
    user_has_global_device_access,
)
from .device_operations import refresh_device_status

logger = logging.getLogger("ICMP RESPONSE")


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


@login_required
def devices(request):
    user_permitted_groups = get_permitted_groups(request.user)
    if user_has_global_device_access(request.user):
        items = Device.objects.all().order_by('-pk')
    else:
        items = Device.objects.filter(group__in=user_permitted_groups).order_by('-pk')
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
        items = items.filter(
            Q(pk__icontains=search_query)
            | Q(device_type__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(device_type__device_model__icontains=search_query)
            | Q(status__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
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

    return render(
        request,
        'device_list.html',
        {
            'devices': page_items,
            'group_options': group_options,
            'vendor_options': vendor_options,
            'selected_status': status_filter,
            'selected_group': group_filter,
            'selected_vendor': vendor_filter,
            'selected_search': search_query,
        },
    )


@login_required
def device_detail(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    return render(request, 'device_detail.html', {'device': device})


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
            return render(
                request,
                'device_host_settings.html',
                {'form': form, 'device': device, 'error_message': error_message},
            )
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
            return render(
                request,
                'device_host_settings.html',
                {'form': form, 'device': device, 'error_message': error_message},
            )
        if action == 'clear_profile':
            prefill_data = request.POST.copy()
            prefill_data['profile'] = ''
            messages.info(request, 'Profile selection cleared. Click "Save settings" to persist.')
            form = DeviceHostSettingsForm(prefill_data, instance=device)
            return render(
                request,
                'device_host_settings.html',
                {'form': form, 'device': device, 'error_message': error_message},
            )

        form = DeviceHostSettingsForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            return redirect('device_detail', pk=device.pk)
        error_message = _first_form_error(form)
    else:
        form = DeviceHostSettingsForm(instance=device)
    return render(
        request,
        'device_host_settings.html',
        {'form': form, 'device': device, 'error_message': error_message},
    )


@login_required
@permission_required('snmp.delete_device', raise_exception=True)
def device_delete(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    if request.method == 'POST':
        device.delete()
        return redirect('devices')
    return render(request, 'device_confirm_delete.html', {'device': device})


@login_required
def device_confirm_delete(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    return render(request, 'device_confirm_delete.html', {'device': device})


@login_required
@permission_required('snmp.change_switch', raise_exception=True)
def device_status(request, pk):
    device = _get_device_for_user_or_404(request.user, pk)
    return refresh_device_status(device)
