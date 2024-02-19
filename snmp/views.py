from django.shortcuts import render, get_object_or_404, redirect
from .models import Switch
from .forms import SwitchForm
from django.core.paginator import Paginator
from django.shortcuts import render
from django.db.models import Q
from django.http import JsonResponse


def switch_status(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    status = 'UP' if switch.status else 'DOWN'
    return JsonResponse({'status': status})

def switches(request):
    items = Switch.objects.all()


    items = items.order_by('ip')

    search_query = request.GET.get('search')
    if search_query:
        items = items.filter(
            Q(pk__icontains=search_query) |
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
        return redirect('switch_list')
    return render(request, 'switch_confirm_delete.html', {'switch': switch})