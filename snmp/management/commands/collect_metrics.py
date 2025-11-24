"""
Management command for collecting and exporting system metrics.
"""
import json
import csv
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Avg, Q

from snmp.models import Switch, Branch
from snmp.services import MonitoringService


class Command(BaseCommand):
    help = 'Collect and export system metrics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='console',
            choices=['console', 'json', 'csv'],
            help='Output format (default: console)',
        )
        parser.add_argument(
            '--file',
            type=str,
            help='Output file path (for json/csv output)',
        )
        parser.add_argument(
            '--period',
            type=int,
            default=24,
            help='Time period in hours for historical data (default: 24)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f'Collecting metrics at {timezone.now()}')
        )
        
        # Collect metrics
        metrics = self.collect_all_metrics(options['period'])
        
        # Output metrics
        if options['output'] == 'console':
            self.output_console(metrics)
        elif options['output'] == 'json':
            self.output_json(metrics, options.get('file'))
        elif options['output'] == 'csv':
            self.output_csv(metrics, options.get('file'))
        
        self.stdout.write(
            self.style.SUCCESS('Metrics collection completed')
        )
    
    def collect_all_metrics(self, period_hours):
        """Collect all system metrics."""
        monitoring_service = MonitoringService()
        
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'period_hours': period_hours,
            'system_overview': monitoring_service.get_system_overview(),
            'switch_metrics': self.get_switch_metrics(period_hours),
            'performance_metrics': self.get_performance_metrics(),
            'error_metrics': self.get_error_metrics(),
            'branch_metrics': self.get_branch_metrics(),
            'historical_trends': self.get_historical_trends(period_hours)
        }
        
        return metrics
    
    def get_switch_metrics(self, period_hours):
        """Get detailed switch metrics."""
        cutoff_time = timezone.now() - timedelta(hours=period_hours)
        
        # Basic counts
        total_switches = Switch.objects.count()
        online_switches = Switch.objects.filter(status=True).count()
        offline_switches = Switch.objects.filter(status=False).count()
        
        # Signal quality metrics
        high_rx_signal = Switch.objects.filter(rx_signal__gt=-15).count()
        low_rx_signal = Switch.objects.filter(rx_signal__lt=-25).count()
        high_tx_signal = Switch.objects.filter(tx_signal__gt=-15).count()
        low_tx_signal = Switch.objects.filter(tx_signal__lt=-25).count()
        
        # Data freshness
        stale_data = Switch.objects.filter(last_update__lt=cutoff_time).count()
        recent_updates = Switch.objects.filter(last_update__gte=cutoff_time).count()
        
        # Vendor distribution
        vendor_stats = Switch.objects.values('model__vendor__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Model distribution
        model_stats = Switch.objects.values('model__device_model').annotate(
            count=Count('id')
        ).order_by('-count')[:10]  # Top 10 models
        
        return {
            'total_switches': total_switches,
            'online_switches': online_switches,
            'offline_switches': offline_switches,
            'online_percentage': round((online_switches / total_switches * 100) if total_switches > 0 else 0, 2),
            'signal_quality': {
                'high_rx_signal': high_rx_signal,
                'low_rx_signal': low_rx_signal,
                'high_tx_signal': high_tx_signal,
                'low_tx_signal': low_tx_signal,
            },
            'data_freshness': {
                'stale_data': stale_data,
                'recent_updates': recent_updates,
                'stale_percentage': round((stale_data / total_switches * 100) if total_switches > 0 else 0, 2)
            },
            'vendor_distribution': list(vendor_stats),
            'model_distribution': list(model_stats)
        }
    
    def get_performance_metrics(self):
        """Get performance metrics from cache."""
        perf_metrics = cache.get('performance_metrics', {})
        request_metrics = cache.get('request_metrics', {})
        
        # Calculate statistics from response times
        response_times = perf_metrics.get('response_times', [])
        response_stats = {}
        
        if response_times:
            response_stats = {
                'count': len(response_times),
                'avg': round(sum(response_times) / len(response_times), 3),
                'min': round(min(response_times), 3),
                'max': round(max(response_times), 3),
                'p95': round(sorted(response_times)[int(len(response_times) * 0.95)], 3),
                'p99': round(sorted(response_times)[int(len(response_times) * 0.99)], 3),
            }
        
        return {
            'response_times': response_stats,
            'status_codes': perf_metrics.get('status_codes', {}),
            'slow_requests': len(perf_metrics.get('slow_requests', [])),
            'request_counts': request_metrics.get('requests_by_method', {}),
            'popular_paths': request_metrics.get('requests_by_path', {}),
            'hourly_requests': request_metrics.get('requests_by_hour', {})
        }
    
    def get_error_metrics(self):
        """Get error metrics from cache."""
        error_metrics = cache.get('error_metrics', {})
        
        return {
            'total_errors': error_metrics.get('total_errors', 0),
            'errors_by_type': error_metrics.get('errors_by_type', {}),
            'errors_by_path': error_metrics.get('errors_by_path', {}),
            'recent_errors_count': len(error_metrics.get('recent_errors', []))
        }
    
    def get_branch_metrics(self):
        """Get metrics by branch."""
        branch_stats = []
        
        for branch in Branch.objects.all():
            switches = Switch.objects.filter(branch=branch)
            total = switches.count()
            online = switches.filter(status=True).count()
            
            branch_stats.append({
                'branch_name': branch.name,
                'total_switches': total,
                'online_switches': online,
                'offline_switches': total - online,
                'online_percentage': round((online / total * 100) if total > 0 else 0, 2),
                'high_signal_count': switches.filter(
                    Q(rx_signal__gt=-15) | Q(tx_signal__gt=-15)
                ).count()
            })
        
        return sorted(branch_stats, key=lambda x: x['total_switches'], reverse=True)
    
    def get_historical_trends(self, period_hours):
        """Get historical trends (simplified - in real implementation, you'd store historical data)."""
        # This is a simplified version - in production you'd want to store metrics in a time-series database
        cutoff_time = timezone.now() - timedelta(hours=period_hours)
        
        # Recent switch additions
        recent_switches = Switch.objects.filter(created__gte=cutoff_time).count()
        
        # Switches that came back online recently
        recently_online = Switch.objects.filter(
            status=True,
            last_update__gte=cutoff_time
        ).count()
        
        return {
            'period_hours': period_hours,
            'new_switches': recent_switches,
            'recently_online': recently_online,
            'note': 'Historical trends require time-series data storage for full implementation'
        }
    
    def output_console(self, metrics):
        """Output metrics to console."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SYSTEM METRICS REPORT'))
        self.stdout.write('='*60)
        
        # System overview
        overview = metrics['system_overview']
        self.stdout.write(f"\nSYSTEM OVERVIEW:")
        self.stdout.write(f"  Total Switches: {overview['switches']['total']}")
        self.stdout.write(f"  Online: {overview['switches']['online']} ({overview['switches'].get('online_percentage', 0):.1f}%)")
        self.stdout.write(f"  Offline: {overview['switches']['offline']} ({overview['switches'].get('offline_percentage', 0):.1f}%)")
        
        # Switch metrics
        switch_metrics = metrics['switch_metrics']
        self.stdout.write(f"\nSWITCH METRICS:")
        self.stdout.write(f"  Stale Data: {switch_metrics['data_freshness']['stale_data']} switches")
        self.stdout.write(f"  High RX Signal: {switch_metrics['signal_quality']['high_rx_signal']}")
        self.stdout.write(f"  Low RX Signal: {switch_metrics['signal_quality']['low_rx_signal']}")
        
        # Performance metrics
        perf_metrics = metrics['performance_metrics']
        if perf_metrics['response_times']:
            self.stdout.write(f"\nPERFORMANCE METRICS:")
            resp_times = perf_metrics['response_times']
            self.stdout.write(f"  Avg Response Time: {resp_times['avg']}s")
            self.stdout.write(f"  P95 Response Time: {resp_times['p95']}s")
            self.stdout.write(f"  Slow Requests: {perf_metrics['slow_requests']}")
        
        # Top branches
        branch_metrics = metrics['branch_metrics']
        if branch_metrics:
            self.stdout.write(f"\nTOP BRANCHES BY SWITCH COUNT:")
            for branch in branch_metrics[:5]:
                self.stdout.write(
                    f"  {branch['branch_name']}: {branch['total_switches']} "
                    f"({branch['online_percentage']:.1f}% online)"
                )
    
    def output_json(self, metrics, file_path):
        """Output metrics to JSON file."""
        if not file_path:
            file_path = f"metrics_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(file_path, 'w') as f:
                json.dump(metrics, f, indent=2, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f'Metrics exported to {file_path}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error writing JSON file: {e}')
            )
    
    def output_csv(self, metrics, file_path):
        """Output metrics to CSV file."""
        if not file_path:
            file_path = f"metrics_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(['Metric', 'Value', 'Category'])
                
                # System overview
                overview = metrics['system_overview']['switches']
                writer.writerow(['Total Switches', overview['total'], 'System'])
                writer.writerow(['Online Switches', overview['online'], 'System'])
                writer.writerow(['Offline Switches', overview['offline'], 'System'])
                
                # Branch metrics
                for branch in metrics['branch_metrics']:
                    writer.writerow([f"{branch['branch_name']} Total", branch['total_switches'], 'Branch'])
                    writer.writerow([f"{branch['branch_name']} Online", branch['online_switches'], 'Branch'])
                
                # Performance metrics
                if metrics['performance_metrics']['response_times']:
                    resp_times = metrics['performance_metrics']['response_times']
                    writer.writerow(['Avg Response Time', resp_times['avg'], 'Performance'])
                    writer.writerow(['P95 Response Time', resp_times['p95'], 'Performance'])
            
            self.stdout.write(
                self.style.SUCCESS(f'Metrics exported to {file_path}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error writing CSV file: {e}')
            )