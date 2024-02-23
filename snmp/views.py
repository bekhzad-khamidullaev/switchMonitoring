from django.shortcuts import render, get_object_or_404, redirect
from .models import Switch, SwitchesPorts, SwitchesNeighbors
from .forms import SwitchForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .update_signal_info import SNMPUpdater
from django.views.decorators.cache import cache_control

def switch_status(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    status = 'UP' if switch.status else 'DOWN'
    return JsonResponse({'status': status})

def switches(request):
    items = Switch.objects.all().order_by('-pk')

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

def switch_detail(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    return render(request, 'switch_detail.html', {'switch': switch})

def switch_create(request):
    if request.method == 'POST':
        form = SwitchForm(request.POST)
        if form.is_valid():
            switch = form.save()
            return redirect('switch_detail', pk=switch.pk)
    else:
        form = SwitchForm()
    return render(request, 'switch_form.html', {'form': form})

def switch_update(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    if request.method == 'POST':
        form = SwitchForm(request.POST, instance=switch)
        if form.is_valid():
            switch = form.save()
            return redirect('switch_detail', pk=switch.pk)
    else:
        form = SwitchForm(instance=switch)
    return render(request, 'switch_form.html', {'form': form})

def switch_delete(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    if request.method == 'POST':
        switch.delete()
        return redirect('switches')
    return render(request, 'switch_confirm_delete.html', {'switch': switch})


def neighbor_switches_map(request):
    switches = Switch.objects.all()
    neighbors = SwitchesNeighbors.objects.all()

    context = {
        'switches': switches,
        'neighbors': neighbors,
    }

    return render(request, 'neighbor_switches_map.html', context)

@csrf_exempt
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def update_optical_info(request, pk):
    snmp_community = 'snmp2netread'
    try:
        switch = Switch.objects.get(pk=pk)
        snmp_updater = SNMPUpdater(switch, snmp_community)
        snmp_updater.update_switch_data()

        return JsonResponse({
            'rx_signal': switch.rx_signal,
            'tx_signal': switch.tx_signal,
            'sfp_vendor': switch.sfp_vendor,
            'part_number': switch.part_number
        })
    except Exception as e:
        return JsonResponse({'error': 'An error occurred during SNMP update.'}, status=500)