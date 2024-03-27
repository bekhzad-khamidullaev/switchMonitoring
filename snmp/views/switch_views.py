from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from snmp.models import Switch
from snmp.forms import SwitchForm
import logging
from .qoshimcha import get_permitted_branches
from .update_views import update_switch_status


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")


@login_required
def switches(request):
    user_permitted_branches = get_permitted_branches(request.user)
    items = Switch.objects.filter(branch__in=user_permitted_branches).order_by('pk')
    search_query = request.GET.get('search')
    if search_query:
        items = items.filter(
            Q(pk__icontains=search_query) |
            Q(model__vendor__name__icontains=search_query) |
            Q(hostname__icontains=search_query) |
            Q(ip__icontains=search_query) |
            Q(model__device_model__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(sfp_vendor__icontains=search_query) |
            Q(part_number__icontains=search_query) |
            Q(rx_signal__icontains=search_query) |
            Q(tx_signal__icontains=search_query)
        )

    paginator = Paginator(items, 25)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)

    return render(request, 'switch_list.html', {'switches': page_items})

@login_required
def switch_detail(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    return render(request, 'switch_detail.html', {'switch': switch})

@login_required
def switch_create(request):
    error_message = None
    if request.method == 'POST':
        form = SwitchForm(request.POST)
        if form.is_valid():
            switch = form.save()
            return redirect('switch_detail', pk=switch.pk)
        else:
            error_message = "Please correct the errors below."
    else:
        form = SwitchForm()
    return render(request, 'switch_form.html', {'form': form, 'error_message': error_message})

@login_required
def switch_update(request, pk):
    error_message = None
    switch = get_object_or_404(Switch, pk=pk)
    if request.method == 'POST':
        form = SwitchForm(request.POST, instance=switch)
        if form.is_valid():
            switch = form.save()
            return redirect('switch_detail', pk=switch.pk)
        else:
            error_message = "Please correct the errors below."
    else:
        form = SwitchForm(instance=switch)
    return render(request, 'switch_form.html', {'form': form, 'error_message': error_message})

@login_required
def switch_delete(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    if request.method == 'POST':
        switch.delete()
        return redirect('switches')
    return render(request, 'switch_confirm_delete.html', {'switch': switch})

# @login_required
def switch_status(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    status_response = update_switch_status(switch)
    return status_response
