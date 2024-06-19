from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from snmp.models import Switch, SwitchModel
from snmp.lib.update_port_info import SNMPUpdater, PortsInfo
from django.views.decorators.csrf import csrf_exempt
from snmp.management.commands.snmp import perform_snmpwalk
import re
import logging
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from .qoshimcha import get_permitted_branches, convert_uptime_to_human_readable
import time
from ping3 import ping

SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_HOSTNAME = 'iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME = 'iso.3.6.1.2.1.1.3.0'
OID_SYSTEM_DESCRIPTION = 'iso.3.6.1.2.1.1.1.0'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")

# @login_required
def update_switch_status(switch):
    ip_addr = switch.ip
    try:
        if ip_addr is None:
            return HttpResponse(status=400)

        start_time = time.time()
        host_alive = ping(ip_addr, unit='ms', size=64, timeout=2)
        elapsed_time = time.time() - start_time

        if host_alive is not None:
            status = bool(host_alive)
            switch.status = status
            switch.save()
            sw_status = 'UP' if switch.status else 'DOWN'
            return JsonResponse({'status': sw_status})
        else:
            return redirect('switch_detail', switch.pk)
    except Exception as e:
        logger.info(f"Error updating switch status for {ip_addr}: {e}")
        return HttpResponse(status=500)


@login_required
@csrf_exempt
def update_optical_info(request, pk):
    if request.method == 'POST':
        switch = get_object_or_404(Switch, pk=pk)
        snmp_community = 'snmp2netread'
        try:
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
    else:
        return HttpResponse(status=405)

@login_required
@csrf_exempt
def update_switch_ports_data(request, pk):
    if request.method == 'POST':
        switch = get_object_or_404(Switch, pk=pk)
        try:
            port_info = PortsInfo()
            port_info.create_switch_ports(switch)
            return JsonResponse({'message': 'Switch ports data updated successfully.'})
        except Exception as e:
            return JsonResponse({'error': f'An error occurred during switch ports update: {str(e)}'}, status=500)
    else:
        return HttpResponse(status=405)


@login_required
def switches_offline(request):
    user_permitted_branches = get_permitted_branches(request.user)
    switches_offline = Switch.objects.filter(status=False, branch__in=user_permitted_branches).order_by('ats')
    search_query = request.GET.get('search')
    if search_query:
        switches_offline = switches_offline.filter(
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

    paginator = Paginator(switches_offline, 25)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)
    return render(request, 'switch_list_offline.html', {
        'down_switches': page_items
    })

@login_required
def switches_high_sig_15(request):
    user_permitted_branches = get_permitted_branches(request.user)
    switches_high_sig = Switch.objects.filter(
        rx_signal__lte=-15, rx_signal__gt=-20, branch__in=user_permitted_branches
    ).order_by('rx_signal')
    search_query = request.GET.get('search')
    if search_query:
        switches_high_sig = switches_high_sig.filter(
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

    paginator = Paginator(switches_high_sig, 100)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)
    return render(request, 'switches_high_sig_15.html', {
        'switches_high_sig': page_items
    })

@login_required
def switches_high_sig_10(request):
    user_permitted_branches = get_permitted_branches(request.user)
    switches_high_sig = Switch.objects.filter(
        rx_signal__lte=-11, rx_signal__gt=-15, branch__in=user_permitted_branches
    ).order_by('rx_signal')
    search_query = request.GET.get('search')
    if search_query:
        switches_high_sig = switches_high_sig.filter(
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

    paginator = Paginator(switches_high_sig, 100)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)
    return render(request, 'switches_high_sig_15.html', {
        'switches_high_sig': page_items
    })

@login_required
def switches_high_sig(request):
    user_permitted_branches = get_permitted_branches(request.user)
    switches_high_sig = Switch.objects.filter(rx_signal__lte=-20, branch__in=user_permitted_branches).order_by('rx_signal')
    search_query = request.GET.get('search')
    if search_query:
        switches_high_sig = switches_high_sig.filter(
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

    paginator = Paginator(switches_high_sig, 25)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)
    return render(request, 'switches_high_sig.html', {
        'switches_high_sig': page_items
    })

@login_required
def update_switch_inventory(request, pk):
        try:
            selected_switch = Switch.objects.get(pk=pk)
        except Switch.DoesNotExist:
            return
        
        snmp_response_hostname = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_HOSTNAME, SNMP_COMMUNITY)
        snmp_response_uptime = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_UPTIME, SNMP_COMMUNITY)
        
        if not snmp_response_hostname or not snmp_response_uptime:
            return


        try:
            match_hostname = re.search(r'SNMPv2-MIB::sysName.0 = (.+)', snmp_response_hostname[0])
            if match_hostname:
                selected_switch.hostname = match_hostname.group(1).strip()
                selected_switch.save()

            else:
                return JsonResponse({'error': f'An error occurred during switch hostname request: {str(e)}'}, status=500)
        except Exception as e:
            logger.error(f"Error processing hostname for {selected_switch.ip}: {e}")


        try:
            match_uptime = re.search(r'SNMPv2-MIB::sysUpTime.0\s*=\s*(\d+)', snmp_response_uptime[0])
            if match_uptime:
                selected_switch.uptime = convert_uptime_to_human_readable(match_uptime.group(1).strip())
                selected_switch.save()
            else:
                return JsonResponse({'error': f'An error occurred during switch uptime request: {str(e)}'}, status=500)
        except Exception as e:
            pass


        snmp_response_description = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_DESCRIPTION, SNMP_COMMUNITY)
        if not snmp_response_description:
            return

        try:
            response_description = str(snmp_response_description[0]).strip().split()
            with transaction.atomic():
                if not selected_switch.model:  # If switch is not associated with any model
                    db_model_instance = SwitchModel.objects.filter(device_model__in=response_description).first()
                    if db_model_instance:
                        selected_switch.model = db_model_instance
                        selected_switch.save()
                elif selected_switch.model.device_model not in response_description:  # If associated model not found in response
                    db_model_instance = SwitchModel.objects.filter(device_model__in=response_description).first()
                    if db_model_instance:
                        selected_switch.model = db_model_instance
                        selected_switch.save()
        
        except Exception as e:
            return JsonResponse({'error': f'An error occurred during switch model request: {str(e)}'}, status=500)

        return redirect('switch_detail', pk=pk)


@login_required
def switches_high_sig_11(request):
    user_permitted_branches = get_permitted_branches(request.user)
    switches_high_sig = Switch.objects.filter(
        rx_signal__lte=-11, branch__in=user_permitted_branches
    ).order_by('rx_signal')
    search_query = request.GET.get('search')
    if search_query:
        switches_high_sig = switches_high_sig.filter(
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

    paginator = Paginator(switches_high_sig, 100)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)
    return render(request, 'switches_high_sig_11.html', {
        'switches_high_sig': page_items
    })
