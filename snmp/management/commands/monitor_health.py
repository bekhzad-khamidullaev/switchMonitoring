"""
Management command for running health checks on all switches.
"""
import time
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q

from snmp.models import Switch
from snmp.services import MonitoringService


class Command(BaseCommand):
    help = 'Run health checks on all switches'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--switch-id',
            type=int,
            help='Check specific switch by ID',
        )
        parser.add_argument(
            '--branch',
            type=str,
            help='Check switches in specific branch',
        )
        parser.add_argument(
            '--offline-only',
            action='store_true',
            help='Check only offline switches',
        )
        parser.add_argument(
            '--parallel',
            action='store_true',
            help='Run checks in parallel (faster but more resource intensive)',
        )
        parser.add_argument(
            '--send-alerts',
            action='store_true',
            help='Send alert notifications for critical issues',
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=5,
            help='Maximum number of parallel workers (default: 5)',
        )
    
    def handle(self, *args, **options):
        start_time = time.time()
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting health check at {timezone.now()}')
        )
        
        # Initialize monitoring service
        monitoring_service = MonitoringService()
        
        # Get switches to check
        switches = self.get_switches_to_check(options)
        
        if not switches.exists():
            self.stdout.write(
                self.style.WARNING('No switches found matching criteria')
            )
            return
        
        self.stdout.write(f'Found {switches.count()} switches to check')
        
        # Run health checks
        if options['parallel']:
            health_reports = self.run_parallel_checks(switches, monitoring_service, options['max_workers'])
        else:
            health_reports = self.run_sequential_checks(switches, monitoring_service)
        
        # Analyze results
        self.analyze_results(health_reports)
        
        # Send alerts if requested
        if options['send_alerts'] and health_reports:
            notifications = monitoring_service.generate_alert_notifications(health_reports)
            if notifications.get('email_sent'):
                self.stdout.write(
                    self.style.SUCCESS(f"Alert notifications sent: {notifications['total_alerts']} alerts")
                )
        
        execution_time = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f'Health check completed in {execution_time:.2f} seconds'
            )
        )
    
    def get_switches_to_check(self, options):
        """Get queryset of switches to check based on options."""
        queryset = Switch.objects.all()
        
        if options['switch_id']:
            queryset = queryset.filter(id=options['switch_id'])
        
        if options['branch']:
            queryset = queryset.filter(branch__name__icontains=options['branch'])
        
        if options['offline_only']:
            queryset = queryset.filter(status=False)
        
        return queryset.select_related('model', 'model__vendor', 'branch')
    
    def run_sequential_checks(self, switches, monitoring_service):
        """Run health checks sequentially."""
        health_reports = []
        total = switches.count()
        
        for i, switch in enumerate(switches, 1):
            self.stdout.write(f'[{i}/{total}] Checking {switch.hostname} ({switch.ip})')
            
            try:
                health_report = monitoring_service.check_switch_health(switch)
                health_reports.append(health_report)
                
                # Show status
                status = health_report['overall_status']
                if status == 'healthy':
                    self.stdout.write(f'  ✓ {status}', self.style.SUCCESS)
                elif status == 'warning':
                    self.stdout.write(f'  ⚠ {status}', self.style.WARNING)
                else:
                    self.stdout.write(f'  ✗ {status}', self.style.ERROR)
                
                # Show alerts
                alerts = health_report.get('alerts', [])
                for alert in alerts:
                    level_style = self.style.ERROR if alert['level'] == 'critical' else self.style.WARNING
                    self.stdout.write(f'    {alert["level"]}: {alert["message"]}', level_style)
                
            except Exception as e:
                self.stdout.write(f'  ✗ Error: {e}', self.style.ERROR)
        
        return health_reports
    
    def run_parallel_checks(self, switches, monitoring_service, max_workers):
        """Run health checks in parallel using thread pool."""
        import concurrent.futures
        import threading
        
        health_reports = []
        total = switches.count()
        completed = 0
        lock = threading.Lock()
        
        def check_switch(switch):
            nonlocal completed
            try:
                health_report = monitoring_service.check_switch_health(switch)
                
                with lock:
                    completed += 1
                    self.stdout.write(
                        f'[{completed}/{total}] Completed {switch.hostname}: {health_report["overall_status"]}'
                    )
                
                return health_report
            except Exception as e:
                with lock:
                    completed += 1
                    self.stdout.write(f'[{completed}/{total}] Error {switch.hostname}: {e}', self.style.ERROR)
                return None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_switch = {executor.submit(check_switch, switch): switch for switch in switches}
            
            for future in concurrent.futures.as_completed(future_to_switch):
                result = future.result()
                if result:
                    health_reports.append(result)
        
        return health_reports
    
    def analyze_results(self, health_reports):
        """Analyze and display health check results."""
        if not health_reports:
            return
        
        # Count by status
        status_counts = {'healthy': 0, 'warning': 0, 'unhealthy': 0, 'error': 0}
        alert_counts = {'critical': 0, 'warning': 0}
        
        for report in health_reports:
            status = report.get('overall_status', 'error')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            for alert in report.get('alerts', []):
                level = alert['level']
                alert_counts[level] = alert_counts.get(level, 0) + 1
        
        # Display summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('HEALTH CHECK SUMMARY'))
        self.stdout.write('='*50)
        
        self.stdout.write(f'Total switches checked: {len(health_reports)}')
        self.stdout.write(f'Healthy: {status_counts["healthy"]}', self.style.SUCCESS)
        self.stdout.write(f'Warning: {status_counts["warning"]}', self.style.WARNING)
        self.stdout.write(f'Unhealthy: {status_counts["unhealthy"]}', self.style.ERROR)
        self.stdout.write(f'Errors: {status_counts["error"]}', self.style.ERROR)
        
        if alert_counts['critical'] > 0 or alert_counts['warning'] > 0:
            self.stdout.write(f'\nAlerts generated:')
            self.stdout.write(f'Critical: {alert_counts["critical"]}', self.style.ERROR)
            self.stdout.write(f'Warning: {alert_counts["warning"]}', self.style.WARNING)
        
        # Calculate health percentage
        total_checked = len(health_reports)
        healthy_count = status_counts['healthy'] + status_counts['warning']
        health_percentage = (healthy_count / total_checked * 100) if total_checked > 0 else 0
        
        self.stdout.write(f'\nOverall health: {health_percentage:.1f}%')