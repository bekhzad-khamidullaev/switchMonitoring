from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from snmp.forms import DeviceProfileForm
from snmp.models import Device, DeviceProfile

from .access import get_permitted_branches, user_has_global_device_access


def _permitted_devices(user):
    if user_has_global_device_access(user):
        return Device.objects.all()
    return Device.objects.filter(branch__in=get_permitted_branches(user))


def _assign_profile_to_device(profile, device_id, user):
    if not device_id:
        return None

    device = get_object_or_404(_permitted_devices(user), pk=device_id)
    if device.profile_id != profile.id:
        device.profile = profile
        device.save(update_fields=['profile'])
    return device


def _build_profile_initial_from_device(device):
    if not device:
        return None
    return {
        'vendor': device.vendor or '',
        'model_pattern': device.model or '',
        'firmware_pattern': device.firmware or '',
        'priority': device.profile.priority if device.profile_id else 100,
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
    device_id = request.GET.get('managed_device', '').strip()
    selected_device = None
    initial = None
    if device_id:
        selected_device = get_object_or_404(_permitted_devices(request.user), pk=device_id)
        initial = _build_profile_initial_from_device(selected_device)

    if request.method == 'POST':
        form = DeviceProfileForm(request.POST)
        assign_device_id = request.POST.get('assign_managed_device_id', '').strip()
        if form.is_valid():
            profile = form.save()
            assigned_device = _assign_profile_to_device(profile, assign_device_id, request.user)
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
            'managed_devices': _permitted_devices(request.user).order_by('hostname', 'ip')[:500],
            'selected_managed_device': selected_device,
        },
    )


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def device_profile_detail(request, pk):
    profile = get_object_or_404(DeviceProfile, pk=pk)
    bindings = profile.metric_bindings.select_related('metric').order_by('priority', 'metric__key')
    attached_devices = Device.objects.filter(profile=profile).order_by('hostname')
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
        assign_device_id = request.POST.get('assign_managed_device_id', '').strip()
        if form.is_valid():
            profile = form.save()
            assigned_device = _assign_profile_to_device(profile, assign_device_id, request.user)
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
            'managed_devices': _permitted_devices(request.user).order_by('hostname', 'ip')[:500],
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
