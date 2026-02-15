import logging

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from snmp.forms import ManagedDeviceForm
from snmp.models import ManagedDevice as ManagedDeviceModel

from .access import get_permitted_branches, user_can_access_managed_device
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


def _get_managed_device_for_user_or_404(user, pk):
    managed_device = get_object_or_404(ManagedDeviceModel, pk=pk)
    if not user_can_access_managed_device(user, managed_device):
        raise Http404
    return managed_device


@login_required
def devices(request):
    user_permitted_branches = get_permitted_branches(request.user)
    items = ManagedDeviceModel.objects.filter(branch__in=user_permitted_branches).order_by('-pk')
    search_query = (request.GET.get('search') or '').strip()
    status_filter = (request.GET.get('status') or '').strip().lower()
    branch_filter = (request.GET.get('branch') or '').strip()
    vendor_filter = (request.GET.get('vendor') or '').strip()

    if status_filter == 'up':
        items = items.filter(status=True)
    elif status_filter == 'down':
        items = items.filter(status=False)

    if branch_filter.isdigit():
        items = items.filter(branch_id=int(branch_filter))

    if vendor_filter.isdigit():
        items = items.filter(model__vendor_id=int(vendor_filter))

    if search_query:
        items = items.filter(
            Q(pk__icontains=search_query)
            | Q(model__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(model__device_model__icontains=search_query)
            | Q(status__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
        )

    paginator = Paginator(items, 25)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)

    branch_options = sorted(user_permitted_branches, key=lambda branch: (branch.name or '').lower())
    vendor_options = (
        ManagedDeviceModel.objects.filter(branch__in=user_permitted_branches)
        .exclude(model__vendor__isnull=True)
        .values('model__vendor_id', 'model__vendor__name')
        .distinct()
        .order_by('model__vendor__name')
    )

    return render(
        request,
        'device_list.html',
        {
            'devices': page_items,
            'branch_options': branch_options,
            'vendor_options': vendor_options,
            'selected_status': status_filter,
            'selected_branch': branch_filter,
            'selected_vendor': vendor_filter,
            'selected_search': search_query,
        },
    )


@login_required
def device_detail(request, pk):
    managed_device = _get_managed_device_for_user_or_404(request.user, pk)
    return render(request, 'device_detail.html', {'managed_device': managed_device})


@login_required
@permission_required('snmp.add_switch', raise_exception=True)
def device_create(request):
    error_message = None
    if request.method == 'POST':
        form = ManagedDeviceForm(request.POST)
        if form.is_valid():
            managed_device = form.save()
            refresh_device_status(managed_device)
            return redirect('device_detail', pk=managed_device.pk)
        error_message = _first_form_error(form)
    else:
        form = ManagedDeviceForm()
    return render(request, 'device_form.html', {'form': form, 'error_message': error_message})


@login_required
@permission_required('snmp.change_switch', raise_exception=True)
def device_update(request, pk):
    error_message = None
    managed_device = _get_managed_device_for_user_or_404(request.user, pk)
    if request.method == 'POST':
        form = ManagedDeviceForm(request.POST, instance=managed_device)
        if form.is_valid():
            managed_device = form.save()
            return redirect('device_detail', pk=managed_device.pk)
        error_message = _first_form_error(form)
    else:
        form = ManagedDeviceForm(instance=managed_device)
    return render(request, 'device_form.html', {'form': form, 'error_message': error_message})


@login_required
@permission_required('snmp.delete_switch', raise_exception=True)
def device_delete(request, pk):
    managed_device = _get_managed_device_for_user_or_404(request.user, pk)
    if request.method == 'POST':
        managed_device.delete()
        return redirect('devices')
    return render(request, 'device_confirm_delete.html', {'managed_device': managed_device})


@login_required
def device_confirm_delete(request, pk):
    managed_device = _get_managed_device_for_user_or_404(request.user, pk)
    return render(request, 'device_confirm_delete.html', {'managed_device': managed_device})


@login_required
@permission_required('snmp.change_switch', raise_exception=True)
def device_status(request, pk):
    managed_device = _get_managed_device_for_user_or_404(request.user, pk)
    return refresh_device_status(managed_device)
