"""
Views for monitoring and health checks.
"""
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.contrib import messages

from ..services import MonitoringService, SwitchService
from ..models import Switch


@login_required
def monitoring_dashboard(request):
    """
    Main monitoring dashboard view.
    """
    try:
        monitoring_service = MonitoringService()
        switch_service = SwitchService()
        
        # Get system overview
        system_overview = monitoring_service.get_system_overview()
        
        # Get switch statistics for current user
        user_stats = switch_service.get_switch_statistics(request.user)
        
        # Get cached metrics
        performance_metrics = cache.get('performance_metrics', {})
        error_metrics = cache.get('error_metrics', {})
        
        # Recent alerts (simplified - in production, you'd store these)
        recent_alerts = []
        
        context = {
            'system_overview': system_overview,
            'user_stats': user_stats,
            'performance_metrics': performance_metrics,
            'error_metrics': error_metrics,
            'recent_alerts': recent_alerts,
            'last_updated': timezone.now(),
        }
        
        return render(request, 'monitoring/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading monitoring dashboard: {e}")
        return render(request, 'monitoring/dashboard.html', {})


@login_required
def health_check_view(request):
    """
    Health check interface view.
    """
    if request.method == 'POST':
        try:
            # Get switches to check
            switch_ids = request.POST.getlist('switch_ids')
            branch_id = request.POST.get('branch_id')
            offline_only = request.POST.get('offline_only') == 'on'
            
            monitoring_service = MonitoringService()
            switch_service = SwitchService()
            
            # Build queryset
            if switch_ids:
                switches = Switch.objects.filter(id__in=switch_ids)
            elif branch_id:
                switches = Switch.objects.filter(branch_id=branch_id)
            else:
                switches = switch_service.get_switches_for_user(request.user)
            
            if offline_only:
                switches = switches.filter(status=False)
            
            # Limit to prevent overload
            switches = switches[:20]
            
            # Run health checks
            health_reports = []
            for switch in switches:
                health_report = monitoring_service.check_switch_health(switch)
                health_reports.append(health_report)
            
            # Store results in session for display
            request.session['health_check_results'] = {
                'reports': health_reports,
                'timestamp': timezone.now().isoformat(),
            }
            
            messages.success(request, f"Health check completed for {len(health_reports)} switches")
            
        except Exception as e:
            messages.error(request, f"Error running health checks: {e}")
    
    # Get available switches and branches for the form
    switch_service = SwitchService()
    user_switches = switch_service.get_switches_for_user(request.user)
    branches = user_switches.values_list('branch__id', 'branch__name').distinct()
    
    # Get previous results if any
    health_results = request.session.get('health_check_results')
    
    context = {
        'switches': user_switches[:100],  # Limit for UI
        'branches': branches,
        'health_results': health_results,
    }
    
    return render(request, 'monitoring/health_check.html', context)


@login_required
def metrics_view(request):
    """
    System metrics view.
    """
    try:
        # Get cached metrics
        request_metrics = cache.get('request_metrics', {})
        performance_metrics = cache.get('performance_metrics', {})
        error_metrics = cache.get('error_metrics', {})
        
        # Calculate some statistics
        response_times = performance_metrics.get('response_times', [])
        response_stats = {}
        
        if response_times:
            response_stats = {
                'count': len(response_times),
                'avg': round(sum(response_times) / len(response_times), 3),
                'min': round(min(response_times), 3),
                'max': round(max(response_times), 3),
            }
        
        context = {
            'request_metrics': request_metrics,
            'performance_metrics': performance_metrics,
            'error_metrics': error_metrics,
            'response_stats': response_stats,
            'last_updated': timezone.now(),
        }
        
        return render(request, 'monitoring/metrics.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading metrics: {e}")
        return render(request, 'monitoring/metrics.html', {})


@login_required
def ajax_switch_status(request, switch_id):
    """
    AJAX endpoint for getting switch status.
    """
    try:
        switch = Switch.objects.get(id=switch_id)
        monitoring_service = MonitoringService()
        
        # Get cached health report or run quick check
        cached_report = cache.get(f'health_report_{switch_id}')
        if cached_report:
            status_data = {
                'status': cached_report['overall_status'],
                'last_check': cached_report['timestamp'],
                'cached': True
            }
        else:
            # Run quick connectivity check
            health_report = monitoring_service.check_switch_health(switch)
            status_data = {
                'status': health_report['overall_status'],
                'last_check': health_report['timestamp'],
                'execution_time': health_report['execution_time'],
                'cached': False
            }
        
        return JsonResponse(status_data)
        
    except Switch.DoesNotExist:
        return JsonResponse({'error': 'Switch not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def ajax_system_stats(request):
    """
    AJAX endpoint for getting real-time system statistics.
    """
    try:
        monitoring_service = MonitoringService()
        system_overview = monitoring_service.get_system_overview()
        
        # Add timestamp for real-time updates
        system_overview['timestamp'] = timezone.now().isoformat()
        
        return JsonResponse(system_overview)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def export_health_report(request):
    """
    Export health check results to JSON/CSV.
    """
    try:
        health_results = request.session.get('health_check_results')
        if not health_results:
            messages.error(request, "No health check results available to export")
            return redirect('health_check')
        
        export_format = request.GET.get('format', 'json')
        
        if export_format == 'json':
            response = JsonResponse(health_results)
            response['Content-Disposition'] = f'attachment; filename="health_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response
        
        elif export_format == 'csv':
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="health_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Switch ID', 'Hostname', 'IP', 'Status', 'Execution Time', 'Alerts'])
            
            for report in health_results['reports']:
                alerts_str = '; '.join([f"{alert['level']}: {alert['message']}" for alert in report.get('alerts', [])])
                writer.writerow([
                    report['switch_id'],
                    report['hostname'],
                    report['ip'],
                    report['overall_status'],
                    report['execution_time'],
                    alerts_str
                ])
            
            return response
        
        else:
            messages.error(request, "Invalid export format")
            return redirect('health_check')
            
    except Exception as e:
        messages.error(request, f"Error exporting report: {e}")
        return redirect('health_check')