from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import logging

from snmp.models import Switch
from snmp.forms import SwitchForm
from snmp.services import SwitchService, MonitoringService
from .qoshimcha import get_permitted_branches
from .update_views import update_switch_status, update_switch_inventory


logger = logging.getLogger("snmp.views.switch")


@login_required
def switches(request):
    """
    List switches using the service layer.
    """
    try:
        switch_service = SwitchService()
        search_query = request.GET.get('search')
        page_number = request.GET.get('page', 1)
        
        # Use service layer for getting paginated switches
        page_items = switch_service.get_paginated_switches(
            user=request.user,
            page_number=page_number,
            search_query=search_query
        )
        
        # Get additional statistics for the dashboard
        stats = switch_service.get_switch_statistics(request.user)
        
        context = {
            'switches': page_items,
            'search_query': search_query,
            'stats': stats,
        }
        
        return render(request, 'switch_list.html', context)
        
    except Exception as e:
        logger.error(f"Error in switches view: {e}")
        messages.error(request, "Error loading switches. Please try again.")
        return render(request, 'switch_list.html', {'switches': None})

@login_required
def switch_detail(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    return render(request, 'switch_detail.html', {'switch': switch})

@login_required
def switch_create(request):
    """
    Create switch using the service layer.
    """
    if request.method == 'POST':
        form = SwitchForm(request.POST)
        if form.is_valid():
            try:
                switch_service = SwitchService()
                switch, error = switch_service.create_switch(form.cleaned_data)
                
                if error:
                    messages.error(request, f"Error creating switch: {error}")
                    return render(request, 'switch_form.html', {'form': form})
                
                messages.success(request, f"Switch '{switch.hostname}' created successfully!")
                logger.info(f"Switch created: {switch.hostname} by user {request.user.username}")
                
                # Redirect to switch detail page
                return redirect('switch_detail', pk=switch.pk)
                
            except Exception as e:
                logger.error(f"Error creating switch: {e}")
                messages.error(request, "An unexpected error occurred. Please try again.")
                return render(request, 'switch_form.html', {'form': form})
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SwitchForm()
    
    return render(request, 'switch_form.html', {'form': form})

@login_required
def switch_update(request, pk):
    """
    Update switch using the service layer.
    """
    switch = get_object_or_404(Switch, pk=pk)
    
    if request.method == 'POST':
        form = SwitchForm(request.POST, instance=switch)
        if form.is_valid():
            try:
                switch_service = SwitchService()
                success, error = switch_service.update_switch(switch, form.cleaned_data)
                
                if not success:
                    messages.error(request, f"Error updating switch: {error}")
                    return render(request, 'switch_form.html', {'form': form, 'switch': switch})
                
                messages.success(request, f"Switch '{switch.hostname}' updated successfully!")
                logger.info(f"Switch updated: {switch.hostname} by user {request.user.username}")
                
                return redirect('switch_detail', pk=switch.pk)
                
            except Exception as e:
                logger.error(f"Error updating switch {pk}: {e}")
                messages.error(request, "An unexpected error occurred. Please try again.")
                return render(request, 'switch_form.html', {'form': form, 'switch': switch})
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SwitchForm(instance=switch)
    
    return render(request, 'switch_form.html', {'form': form, 'switch': switch})

@login_required
def switch_delete(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    if request.method == 'POST':
        switch.delete()
        return redirect('switches')
    return render(request, 'switch_confirm_delete.html', {'switch': switch})

@login_required
def switch_confirm_delete(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    return render(request, 'switch_confirm_delete.html', {'switch': switch})

# @login_required
def switch_status(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    status_response = update_switch_status(switch)
    return status_response
