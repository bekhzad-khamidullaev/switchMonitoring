from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from snmp.forms import DeviceProfileForm
from snmp.models import Device, DeviceProfile, ManagedDevice as ManagedDeviceModel

from .access import get_permitted_branches, user_has_global_device_access


def _permitted_managed_devices(user):
    if user_has_global_device_access(user):
        return ManagedDeviceModel.objects.all()
    return ManagedDeviceModel.objects.filter(branch__in=get_permitted_branches(user))


def _assign_profile_to_managed_device(profile, managed_device_id, user):
    if not managed_device_id:
        return None

    managed_device = get_object_or_404(_permitted_managed_devices(user), pk=managed_device_id)
    telemetry_device, _ = Device.objects.get_or_create(
        ip=managed_device.ip,
        defaults={
            'managed_device': managed_device,
            'hostname': managed_device.hostname or '',
            'status': bool(managed_device.status),
        },
    )
    fields_to_update = []
    if telemetry_device.managed_device_id != managed_device.id:
        telemetry_device.managed_device = managed_device
        fields_to_update.append('managed_device')
    if telemetry_device.profile_id != profile.id:
        telemetry_device.profile = profile
        fields_to_update.append('profile')
    if fields_to_update:
        telemetry_device.save(update_fields=fields_to_update)
    return managed_device


def _build_profile_initial_from_managed_device(managed_device):
    if not managed_device:
        return None
    telemetry_device = Device.objects.filter(managed_device=managed_device).first()
    if not telemetry_device:
        return None
    return {
        'vendor': telemetry_device.vendor or '',
        'model_pattern': telemetry_device.model or '',
        'firmware_pattern': telemetry_device.firmware or '',
        'priority': telemetry_device.profile.priority if telemetry_device.profile_id else 100,
        'active': True,
    }


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_profiles(request):
    search_query = request.GET.get('q', '').strip()
    profiles = (
        DeviceProfile.objects
        .annotate(bindings_count=Count('metric_bindings'), devices_count=Count('device', distinct=True))
    )

    if search_query:
        profiles = profiles.filter(
            Q(vendor__icontains=search_query) |
            Q(model_pattern__icontains=search_query)
        )

    profiles = profiles.order_by('priority', 'vendor', 'model_pattern')

    paginator = Paginator(profiles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request, 
        'device_profiles.html', 
        {
            'profiles': page_obj,
            'search_query': search_query,
            'is_paginated': page_obj.has_other_pages(),
            'page_obj': page_obj,
        }
    )


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_profile_create(request):
    managed_device_id = request.GET.get('managed_device', '').strip()
    selected_managed_device = None
    initial = None
    if managed_device_id:
        selected_managed_device = get_object_or_404(_permitted_managed_devices(request.user), pk=managed_device_id)
        initial = _build_profile_initial_from_managed_device(selected_managed_device)

    if request.method == 'POST':
        form = DeviceProfileForm(request.POST)
        assign_managed_device_id = request.POST.get('assign_managed_device_id', '').strip()
        if form.is_valid():
            profile = form.save()
            assigned_device = _assign_profile_to_managed_device(profile, assign_managed_device_id, request.user)
            if assigned_device:
                messages.success(request, f'Profile created and assigned to {assigned_device.hostname or assigned_device.ip}.')
            else:
                messages.success(request, 'Profile created.')
            return redirect('device_profile_detail', pk=profile.pk)
    else:
        form = DeviceProfileForm(initial=initial)

    return render(
        request,
        'device_profile_form.html',
        {
            'form': form,
            'title': 'Create Profile',
            'submit_label': 'Create',
            'managed_devices': _permitted_managed_devices(request.user).order_by('hostname', 'ip')[:500],
            'selected_managed_device': selected_managed_device,
        },
    )


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_profile_detail(request, pk):
    profile = get_object_or_404(DeviceProfile, pk=pk)
    bindings = profile.metric_bindings.select_related('metric').order_by('priority', 'metric__key')
    attached_devices = Device.objects.filter(profile=profile).select_related('managed_device').order_by('hostname')
    return render(
        request,
        'device_profile_detail.html',
        {
            'profile': profile,
            'bindings': bindings,
            'attached_devices': attached_devices,
        },
    )


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_profile_update(request, pk):
    profile = get_object_or_404(DeviceProfile, pk=pk)
    if request.method == 'POST':
        form = DeviceProfileForm(request.POST, instance=profile)
        assign_managed_device_id = request.POST.get('assign_managed_device_id', '').strip()
        if form.is_valid():
            profile = form.save()
            assigned_device = _assign_profile_to_managed_device(profile, assign_managed_device_id, request.user)
            if assigned_device:
                messages.success(request, f'Profile updated and assigned to {assigned_device.hostname or assigned_device.ip}.')
            else:
                messages.success(request, 'Profile updated.')
            return redirect('device_profile_detail', pk=profile.pk)
    else:
        form = DeviceProfileForm(instance=profile)

    return render(
        request,
        'device_profile_form.html',
        {
            'form': form,
            'profile': profile,
            'title': f'Edit Profile #{profile.pk}',
            'submit_label': 'Save',
            'managed_devices': _permitted_managed_devices(request.user).order_by('hostname', 'ip')[:500],
            'selected_managed_device': None,
        },
    )


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_profile_delete(request, pk):
    profile = get_object_or_404(DeviceProfile, pk=pk)
    if request.method == 'POST':
        profile.delete()
        messages.success(request, 'Profile deleted.')
        return redirect('device_profiles')
    return render(request, 'device_profile_confirm_delete.html', {'profile': profile})
