"""
Management command for continuous uplink monitoring with optical signal analysis.
Production-ready command for automated uplink health monitoring.
"""
import time
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q

from snmp.models import Switch, Branch
from snmp.services import UplinkMonitoringService


class Command(BaseCommand):
    help = 'Monitor uplink ports and optical signal levels on network devices'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--switch-id',
            type=int,
            help='Monitor specific switch by ID',
        )
        parser.add_argument(
            '--switch-ip',
            type=str,
            help='Monitor specific switch by IP address',
        )
        parser.add_argument(
            '--branch',
            type=str,
            help='Monitor switches in specific branch',
        )
        parser.add_argument(
            '--vendor',
            type=str,
            help='Monitor switches from specific vendor',
        )
        parser.add_argument(
            '--parallel',
            action='store_true',
            help='Run monitoring in parallel (faster but more resource intensive)',
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=10,
            help='Maximum number of parallel workers (default: 10)',
        )
        parser.add_argument(
            '--send-alerts',
            action='store_true',
            help='Send email alerts for critical issues',
        )
        parser.add_argument(
            '--critical-only',
            action='store_true',
            help='Show only critical issues',
        )
        parser.add_argument(
            '--warning-threshold',
            type=float,
            default=-20.0,
            help='Warning threshold for optical power (dBm, default: -20.0)',
        )
        parser.add_argument(
            '--critical-threshold',
            type=float,
            default=-25.0,
            help='Critical threshold for optical power (dBm, default: -25.0)',
        )
        parser.add_argument(
            '--output-format',
            type=str,
            choices=['console', 'json', 'csv'],
            default='console',
            help='Output format (default: console)',
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file path (for json/csv formats)',
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuous monitoring (Ctrl+C to stop)',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=300,
            help='Monitoring interval in seconds for continuous mode (default: 300)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
    
    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        self.uplink_service = UplinkMonitoringService()
        
        # Update thresholds if provided
        if options['warning_threshold'] != -20.0 or options['critical_threshold'] != -25.0:
            self.update_thresholds(options)
        
        if options['continuous']:
            self.run_continuous_monitoring(options)
        else:
            self.run_single_monitoring(options)
    
    def run_single_monitoring(self, options):
        """Run single monitoring cycle."""
        start_time = time.time()
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting uplink monitoring at {timezone.now()}')
        )
        
        try:
            if options['switch_id']:
                report = self.monitor_specific_switch(options)
            elif options['switch_ip']:
                report = self.monitor_switch_by_ip(options)
            elif options['branch']:
                report = self.monitor_branch_switches(options)
            elif options['vendor']:
                report = self.monitor_vendor_switches(options)
            else:
                report = self.monitor_all_switches(options)
            
            # Display results
            self.display_monitoring_results(report, options)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nMonitoring cancelled by user'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Monitoring failed: {e}'))
            raise CommandError(f'Monitoring failed: {e}')
        
        execution_time = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(f'Monitoring completed in {execution_time:.2f} seconds')
        )
    
    def run_continuous_monitoring(self, options):
        """Run continuous monitoring with specified interval."""
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting continuous uplink monitoring (interval: {options["interval"]}s)'
            )
        )
        self.stdout.write('Press Ctrl+C to stop...\n')
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                cycle_start = time.time()
                
                self.stdout.write(
                    f'\n{"="*60}'
                )
                self.stdout.write(
                    f'MONITORING CYCLE #{cycle_count} - {timezone.now()}'
                )
                self.stdout.write(
                    f'{"="*60}'
                )
                
                try:
                    # Run monitoring
                    if options['switch_id']:
                        report = self.monitor_specific_switch(options)
                    else:
                        report = self.monitor_all_switches(options)
                    
                    # Display summary
                    self.display_monitoring_summary(report, options)
                    
                    # Show critical issues immediately
                    if report.critical_uplinks > 0:
                        self.display_critical_issues(report)
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Cycle {cycle_count} failed: {e}')
                    )
                
                # Wait for next cycle
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, options['interval'] - cycle_time)
                
                if sleep_time > 0:
                    self.stdout.write(
                        f'Cycle completed in {cycle_time:.1f}s. Sleeping for {sleep_time:.1f}s...'
                    )
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING(f'\nContinuous monitoring stopped after {cycle_count} cycles')
            )
    
    def monitor_specific_switch(self, options):
        """Monitor specific switch by ID."""
        try:
            switch = Switch.objects.get(id=options['switch_id'])
            self.stdout.write(f'Monitoring switch: {switch.hostname} ({switch.ip})')
            
            uplink_statuses = self.uplink_service.monitor_switch_uplinks(switch)
            
            # Create mini report
            report = self.create_switch_report(switch, uplink_statuses)
            return report
            
        except Switch.DoesNotExist:
            raise CommandError(f'Switch with ID {options["switch_id"]} not found')
    
    def monitor_switch_by_ip(self, options):
        """Monitor specific switch by IP address."""
        try:
            switch = Switch.objects.get(ip=options['switch_ip'])
            self.stdout.write(f'Monitoring switch: {switch.hostname} ({switch.ip})')
            
            uplink_statuses = self.uplink_service.monitor_switch_uplinks(switch)
            
            # Create mini report
            report = self.create_switch_report(switch, uplink_statuses)
            return report
            
        except Switch.DoesNotExist:
            raise CommandError(f'Switch with IP {options["switch_ip"]} not found')
    
    def monitor_branch_switches(self, options):
        """Monitor switches in specific branch."""
        try:
            branch = Branch.objects.get(name__icontains=options['branch'])
            switches = Switch.objects.filter(
                branch=branch,
                status=True,
                model__isnull=False
            )
            
            if not switches.exists():
                self.stdout.write(
                    self.style.WARNING(f'No active switches found in branch: {branch.name}')
                )
                return self.create_empty_report()
            
            self.stdout.write(f'Monitoring {switches.count()} switches in branch: {branch.name}')
            
            return self.uplink_service.monitor_all_uplinks(
                parallel=options['parallel'],
                max_workers=options['max_workers']
            )
            
        except Branch.DoesNotExist:
            raise CommandError(f'Branch "{options["branch"]}" not found')
    
    def monitor_vendor_switches(self, options):
        """Monitor switches from specific vendor."""
        switches = Switch.objects.filter(
            model__vendor__name__icontains=options['vendor'],
            status=True,
            model__isnull=False
        )
        
        if not switches.exists():
            self.stdout.write(
                self.style.WARNING(f'No active switches found for vendor: {options["vendor"]}')
            )
            return self.create_empty_report()
        
        self.stdout.write(f'Monitoring {switches.count()} {options["vendor"]} switches')
        
        return self.uplink_service.monitor_all_uplinks(
            parallel=options['parallel'],
            max_workers=options['max_workers']
        )
    
    def monitor_all_switches(self, options):
        """Monitor all active switches."""
        return self.uplink_service.monitor_all_uplinks(
            parallel=options['parallel'],
            max_workers=options['max_workers']
        )
    
    def create_switch_report(self, switch, uplink_statuses):
        """Create report for single switch monitoring."""
        from snmp.services.uplink_monitoring_service import UplinkMonitoringReport
        
        # Count statuses
        healthy_count = sum(1 for status in uplink_statuses if status.status_severity == "normal")
        warning_count = sum(1 for status in uplink_statuses if status.status_severity == "warning")
        critical_count = sum(1 for status in uplink_statuses if status.status_severity == "critical")
        offline_count = sum(1 for status in uplink_statuses if status.operational_status == "down")
        
        # Count alerts
        total_alerts = sum(len(status.alerts) for status in uplink_statuses)
        
        report = UplinkMonitoringReport(
            timestamp=timezone.now(),
            total_uplinks_monitored=len(uplink_statuses),
            healthy_uplinks=healthy_count,
            warning_uplinks=warning_count,
            critical_uplinks=critical_count,
            offline_uplinks=offline_count,
            switches_with_issues=1 if (warning_count > 0 or critical_count > 0) else 0,
            uplink_statuses=uplink_statuses,
            execution_time=0,
            alerts_generated=total_alerts,
            notifications_sent=0
        )
        
        return report
    
    def create_empty_report(self):
        """Create empty report."""
        from snmp.services.uplink_monitoring_service import UplinkMonitoringReport
        
        return UplinkMonitoringReport(
            timestamp=timezone.now(),
            total_uplinks_monitored=0,
            healthy_uplinks=0,
            warning_uplinks=0,
            critical_uplinks=0,
            offline_uplinks=0,
            switches_with_issues=0,
            uplink_statuses=[],
            execution_time=0,
            alerts_generated=0,
            notifications_sent=0
        )
    
    def update_thresholds(self, options):
        """Update monitoring thresholds."""
        warning_threshold = options['warning_threshold']
        critical_threshold = options['critical_threshold']
        
        # Update service thresholds
        self.uplink_service.thresholds['rx_power']['warning_low'] = warning_threshold
        self.uplink_service.thresholds['rx_power']['critical_low'] = critical_threshold
        self.uplink_service.thresholds['tx_power']['warning_low'] = warning_threshold
        self.uplink_service.thresholds['tx_power']['critical_low'] = critical_threshold
        
        if self.verbose:
            self.stdout.write(f'Updated thresholds: Warning={warning_threshold}dBm, Critical={critical_threshold}dBm')
    
    def display_monitoring_results(self, report, options):
        """Display monitoring results based on format."""
        if options['output_format'] == 'console':
            self.display_console_results(report, options)
        elif options['output_format'] == 'json':
            self.output_json_results(report, options)
        elif options['output_format'] == 'csv':
            self.output_csv_results(report, options)
    
    def display_console_results(self, report, options):
        """Display results in console format."""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('UPLINK MONITORING REPORT'))
        self.stdout.write('='*80)
        
        # Summary
        self.stdout.write(f'Timestamp: {report.timestamp}')
        self.stdout.write(f'Execution Time: {report.execution_time}s')
        self.stdout.write(f'Total Uplinks Monitored: {report.total_uplinks_monitored}')
        self.stdout.write(f'Healthy: {report.healthy_uplinks}', self.style.SUCCESS)
        self.stdout.write(f'Warning: {report.warning_uplinks}', self.style.WARNING)
        self.stdout.write(f'Critical: {report.critical_uplinks}', self.style.ERROR)
        self.stdout.write(f'Offline: {report.offline_uplinks}', self.style.ERROR)
        self.stdout.write(f'Switches with Issues: {report.switches_with_issues}')
        self.stdout.write(f'Total Alerts: {report.alerts_generated}')
        
        if options['critical_only']:
            # Show only critical issues
            critical_uplinks = [
                status for status in report.uplink_statuses 
                if status.status_severity == "critical"
            ]
            self.display_uplink_details(critical_uplinks, "CRITICAL ISSUES")
        else:
            # Show all issues
            warning_uplinks = [
                status for status in report.uplink_statuses 
                if status.status_severity == "warning"
            ]
            critical_uplinks = [
                status for status in report.uplink_statuses 
                if status.status_severity == "critical"
            ]
            
            if critical_uplinks:
                self.display_uplink_details(critical_uplinks, "CRITICAL ISSUES")
            
            if warning_uplinks and not options['critical_only']:
                self.display_uplink_details(warning_uplinks, "WARNING ISSUES")
            
            if self.verbose:
                healthy_uplinks = [
                    status for status in report.uplink_statuses 
                    if status.status_severity == "normal"
                ]
                if healthy_uplinks:
                    self.display_uplink_details(healthy_uplinks, "HEALTHY UPLINKS")
    
    def display_monitoring_summary(self, report, options):
        """Display brief monitoring summary for continuous mode."""
        status_text = []
        
        if report.critical_uplinks > 0:
            status_text.append(f"{report.critical_uplinks} CRITICAL")
        if report.warning_uplinks > 0:
            status_text.append(f"{report.warning_uplinks} WARNING")
        if report.offline_uplinks > 0:
            status_text.append(f"{report.offline_uplinks} OFFLINE")
        
        if not status_text:
            status_text.append("ALL HEALTHY")
        
        self.stdout.write(
            f'Monitored {report.total_uplinks_monitored} uplinks in {report.execution_time}s - '
            f'{", ".join(status_text)}'
        )
    
    def display_critical_issues(self, report):
        """Display critical issues immediately."""
        critical_uplinks = [
            status for status in report.uplink_statuses 
            if status.status_severity == "critical"
        ]
        
        if critical_uplinks:
            self.stdout.write(
                self.style.ERROR(f'\n🚨 {len(critical_uplinks)} CRITICAL ISSUES DETECTED:')
            )
            
            for uplink in critical_uplinks:
                self.stdout.write(
                    f'  • {uplink.switch_hostname} ({uplink.switch_ip}) - '
                    f'Port {uplink.port_name}: {", ".join(uplink.alerts)}',
                    self.style.ERROR
                )
    
    def display_uplink_details(self, uplinks, title):
        """Display detailed uplink information."""
        if not uplinks:
            return
        
        self.stdout.write(f'\n{title}:')
        self.stdout.write('-' * 80)
        
        for uplink in uplinks:
            # Format signal levels
            rx_power_str = f"{uplink.rx_power:.2f}dBm" if uplink.rx_power is not None else "N/A"
            tx_power_str = f"{uplink.tx_power:.2f}dBm" if uplink.tx_power is not None else "N/A"
            
            # Format speed
            speed_mbps = uplink.interface_speed / 1000000 if uplink.interface_speed else 0
            speed_str = f"{speed_mbps:.0f}Mbps" if speed_mbps else "N/A"
            
            self.stdout.write(
                f'Switch: {uplink.switch_hostname} ({uplink.switch_ip})'
            )
            self.stdout.write(
                f'  Port: {uplink.port_name} ({uplink.port_description})'
            )
            self.stdout.write(
                f'  Status: Admin={uplink.admin_status}, Oper={uplink.operational_status}, Speed={speed_str}'
            )
            self.stdout.write(
                f'  Optical: RX={rx_power_str}, TX={tx_power_str}'
            )
            
            if uplink.alerts:
                for alert in uplink.alerts:
                    alert_style = self.style.ERROR if "critical" in alert.lower() else self.style.WARNING
                    self.stdout.write(f'  ⚠️  {alert}', alert_style)
            
            self.stdout.write('')  # Empty line between uplinks
    
    def output_json_results(self, report, options):
        """Output results in JSON format."""
        import json
        from dataclasses import asdict
        
        # Convert report to dict
        report_dict = asdict(report)
        
        # Convert datetime objects to strings
        report_dict['timestamp'] = report.timestamp.isoformat()
        for uplink in report_dict['uplink_statuses']:
            if uplink['last_update']:
                uplink['last_update'] = uplink['last_update'].isoformat()
        
        if options['output_file']:
            with open(options['output_file'], 'w') as f:
                json.dump(report_dict, f, indent=2)
            self.stdout.write(f'Results saved to {options["output_file"]}')
        else:
            self.stdout.write(json.dumps(report_dict, indent=2))
    
    def output_csv_results(self, report, options):
        """Output results in CSV format."""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Switch ID', 'Switch Hostname', 'Switch IP', 'Port Index', 'Port Name',
            'Port Description', 'Speed (Mbps)', 'Admin Status', 'Operational Status',
            'RX Power (dBm)', 'TX Power (dBm)', 'Status Severity', 'Alerts',
            'Last Update'
        ])
        
        # Write data
        for uplink in report.uplink_statuses:
            speed_mbps = uplink.interface_speed / 1000000 if uplink.interface_speed else 0
            alerts_str = '; '.join(uplink.alerts)
            
            writer.writerow([
                uplink.switch_id,
                uplink.switch_hostname,
                uplink.switch_ip,
                uplink.port_index,
                uplink.port_name,
                uplink.port_description,
                f"{speed_mbps:.0f}" if speed_mbps else '',
                uplink.admin_status,
                uplink.operational_status,
                f"{uplink.rx_power:.2f}" if uplink.rx_power is not None else '',
                f"{uplink.tx_power:.2f}" if uplink.tx_power is not None else '',
                uplink.status_severity,
                alerts_str,
                uplink.last_update.isoformat() if uplink.last_update else ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        if options['output_file']:
            with open(options['output_file'], 'w') as f:
                f.write(csv_content)
            self.stdout.write(f'Results saved to {options["output_file"]}')
        else:
            self.stdout.write(csv_content)