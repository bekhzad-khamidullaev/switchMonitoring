"""
Management command for automatic device discovery and database updates.
Production-ready command for continuous device discovery and monitoring.
"""
import time
import argparse
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from snmp.models import Switch, Branch, Ats
from snmp.services import DeviceDiscoveryService, UplinkMonitoringService


class Command(BaseCommand):
    help = 'Automatically discover network devices and update database with device information and uplink monitoring'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--ip-range',
            type=str,
            help='IP range to scan (e.g., 192.168.1.0/24)',
        )
        parser.add_argument(
            '--ip-list',
            type=str,
            nargs='+',
            help='Specific IP addresses to scan',
        )
        parser.add_argument(
            '--switch-id',
            type=int,
            help='Update specific switch by ID',
        )
        parser.add_argument(
            '--branch',
            type=str,
            help='Update switches in specific branch',
        )
        parser.add_argument(
            '--community',
            type=str,
            default='public',
            help='SNMP community string (default: public)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=5,
            help='SNMP timeout in seconds (default: 5)',
        )
        parser.add_argument(
            '--parallel',
            action='store_true',
            help='Run discovery in parallel (faster but more resource intensive)',
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=10,
            help='Maximum number of parallel workers (default: 10)',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing switches with new discovery data',
        )
        parser.add_argument(
            '--monitor-uplinks',
            action='store_true',
            help='Also monitor uplink ports and optical signals',
        )
        parser.add_argument(
            '--auto-assign-branch',
            action='store_true',
            help='Automatically assign switches to branches based on IP subnet',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be discovered without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
    
    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        
        start_time = time.time()
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting device discovery at {timezone.now()}')
        )
        
        # Initialize services
        self.discovery_service = DeviceDiscoveryService()
        self.uplink_service = UplinkMonitoringService() if options['monitor_uplinks'] else None
        
        try:
            if options['switch_id']:
                # Discover specific switch
                self.discover_specific_switch(options)
            elif options['ip_range']:
                # Discover IP range
                self.discover_ip_range(options)
            elif options['ip_list']:
                # Discover specific IPs
                self.discover_ip_list(options)
            elif options['branch']:
                # Discover switches in branch
                self.discover_branch_switches(options)
            else:
                # Discover all existing switches
                self.discover_existing_switches(options)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nDiscovery cancelled by user'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Discovery failed: {e}'))
            raise CommandError(f'Discovery failed: {e}')
        
        execution_time = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(f'Discovery completed in {execution_time:.2f} seconds')
        )
    
    def discover_specific_switch(self, options):
        """Discover specific switch by ID."""
        try:
            switch = Switch.objects.get(id=options['switch_id'])
            self.stdout.write(f'Discovering switch: {switch.hostname} ({switch.ip})')
            
            self.discover_and_update_switch(switch, options)
            
        except Switch.DoesNotExist:
            raise CommandError(f'Switch with ID {options["switch_id"]} not found')
    
    def discover_ip_range(self, options):
        """Discover devices in IP range."""
        import ipaddress
        
        try:
            network = ipaddress.IPv4Network(options['ip_range'], strict=False)
            self.stdout.write(f'Scanning IP range: {network} ({network.num_addresses} addresses)')
            
            discovered_count = 0
            total_ips = network.num_addresses
            
            for i, ip in enumerate(network.hosts(), 1):
                if i % 50 == 0:  # Progress indicator
                    self.stdout.write(f'Progress: {i}/{total_ips} IPs scanned')
                
                ip_str = str(ip)
                
                # Skip if switch already exists
                if Switch.objects.filter(ip=ip_str).exists() and not options['update_existing']:
                    continue
                
                # Discover device
                device_info = self.discovery_service.discover_device(
                    ip_str, 
                    options['community']
                )
                
                if device_info:
                    if options['dry_run']:
                        self.stdout.write(f'Would discover: {ip_str} - {device_info.vendor} {device_info.model}')
                    else:
                        switch = self.create_or_update_switch(ip_str, device_info, options)
                        if switch:
                            discovered_count += 1
                            self.stdout.write(f'Discovered: {ip_str} - {device_info.vendor} {device_info.model}')
            
            self.stdout.write(
                self.style.SUCCESS(f'IP range scan completed. Discovered {discovered_count} devices.')
            )
            
        except ValueError as e:
            raise CommandError(f'Invalid IP range: {e}')
    
    def discover_ip_list(self, options):
        """Discover specific IP addresses."""
        ip_list = options['ip_list']
        self.stdout.write(f'Scanning {len(ip_list)} IP addresses')
        
        discovered_count = 0
        
        for ip in ip_list:
            # Skip if switch already exists
            if Switch.objects.filter(ip=ip).exists() and not options['update_existing']:
                self.stdout.write(f'Switch {ip} already exists, skipping')
                continue
            
            # Discover device
            device_info = self.discovery_service.discover_device(
                ip, 
                options['community']
            )
            
            if device_info:
                if options['dry_run']:
                    self.stdout.write(f'Would discover: {ip} - {device_info.vendor} {device_info.model}')
                else:
                    switch = self.create_or_update_switch(ip, device_info, options)
                    if switch:
                        discovered_count += 1
                        self.stdout.write(f'Discovered: {ip} - {device_info.vendor} {device_info.model}')
            else:
                self.stdout.write(f'No response from {ip}')
        
        self.stdout.write(
            self.style.SUCCESS(f'IP list scan completed. Discovered {discovered_count} devices.')
        )
    
    def discover_branch_switches(self, options):
        """Discover switches in specific branch."""
        try:
            branch = Branch.objects.get(name__icontains=options['branch'])
            switches = Switch.objects.filter(branch=branch)
            
            self.stdout.write(f'Discovering {switches.count()} switches in branch: {branch.name}')
            
            for switch in switches:
                self.discover_and_update_switch(switch, options)
            
        except Branch.DoesNotExist:
            raise CommandError(f'Branch "{options["branch"]}" not found')
    
    def discover_existing_switches(self, options):
        """Discover all existing switches."""
        switches = Switch.objects.all()
        
        if not switches.exists():
            self.stdout.write(self.style.WARNING('No switches found in database'))
            return
        
        self.stdout.write(f'Discovering {switches.count()} existing switches')
        
        for switch in switches:
            self.discover_and_update_switch(switch, options)
    
    def discover_and_update_switch(self, switch, options):
        """Discover and update a single switch."""
        try:
            if self.verbose:
                self.stdout.write(f'Discovering switch: {switch.hostname} ({switch.ip})')
            
            # Discover device information
            device_info = self.discovery_service.discover_device(
                switch.ip,
                switch.snmp_community_ro or options['community']
            )
            
            if not device_info:
                self.stdout.write(
                    self.style.WARNING(f'Could not discover device: {switch.hostname}')
                )
                return
            
            if options['dry_run']:
                self.stdout.write(
                    f'Would update {switch.hostname}: {device_info.vendor} {device_info.model}'
                )
                return
            
            # Update switch in database
            updated = self.update_switch_with_discovery(switch, device_info, options)
            
            if updated:
                # Monitor uplinks if requested
                if options['monitor_uplinks'] and self.uplink_service:
                    uplink_statuses = self.uplink_service.monitor_switch_uplinks(switch)
                    self.stdout.write(
                        f'  Monitored {len(uplink_statuses)} uplinks'
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(f'Updated: {switch.hostname} - {device_info.vendor} {device_info.model}')
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error discovering switch {switch.hostname}: {e}')
            )
    
    def create_or_update_switch(self, ip, device_info, options):
        """Create or update switch with discovery information."""
        try:
            # Check if switch exists
            switch = Switch.objects.filter(ip=ip).first()
            
            if switch and not options['update_existing']:
                return None
            
            if not switch:
                # Create new switch
                switch = Switch(ip=ip, hostname=device_info.system_description[:50])
            
            # Update with discovery data
            updated = self.update_switch_with_discovery(switch, device_info, options)
            
            if updated:
                # Monitor uplinks if requested
                if options['monitor_uplinks'] and self.uplink_service:
                    uplink_statuses = self.uplink_service.monitor_switch_uplinks(switch)
                    if self.verbose:
                        self.stdout.write(f'  Monitored {len(uplink_statuses)} uplinks')
                
                return switch
            
            return None
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating/updating switch {ip}: {e}')
            )
            return None
    
    def update_switch_with_discovery(self, switch, device_info, options):
        """Update switch object with discovered information."""
        try:
            with transaction.atomic():
                # Update device information
                updated = self.discovery_service.auto_update_device_in_db(switch)
                
                if not updated:
                    return False
                
                # Auto-assign branch if requested
                if options['auto_assign_branch']:
                    branch = self.auto_assign_branch(switch.ip)
                    if branch:
                        switch.branch = branch
                        switch.save()
                        if self.verbose:
                            self.stdout.write(f'  Assigned to branch: {branch.name}')
                
                # Update additional fields
                if device_info.firmware_version:
                    switch.soft_version = device_info.firmware_version
                
                # Set status to online if discovered
                switch.status = True
                switch.last_update = timezone.now()
                switch.save()
                
                return True
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating switch database record: {e}')
            )
            return False
    
    def auto_assign_branch(self, ip):
        """Automatically assign switch to branch based on IP subnet."""
        try:
            import ipaddress
            
            switch_ip = ipaddress.IPv4Address(ip)
            
            # Check ATS subnets first
            for ats in Ats.objects.filter(subnet__isnull=False):
                try:
                    if ats.contains_ip(str(switch_ip)):
                        return ats.branch
                except:
                    continue
            
            # Fallback to generic branch assignment based on IP ranges
            ip_parts = ip.split('.')
            if len(ip_parts) >= 3:
                subnet_prefix = '.'.join(ip_parts[:3])
                
                # Look for existing switches in same subnet
                similar_switches = Switch.objects.filter(
                    ip__startswith=subnet_prefix,
                    branch__isnull=False
                ).first()
                
                if similar_switches:
                    return similar_switches.branch
            
            return None
            
        except Exception as e:
            if self.verbose:
                self.stdout.write(f'Error auto-assigning branch for {ip}: {e}')
            return None
    
    def get_discovery_statistics(self):
        """Get discovery statistics."""
        stats = {
            'total_switches': Switch.objects.count(),
            'switches_with_models': Switch.objects.filter(model__isnull=False).count(),
            'vendors': Switch.objects.values('model__vendor__name').distinct().count(),
            'online_switches': Switch.objects.filter(status=True).count(),
            'recent_updates': Switch.objects.filter(
                last_update__gte=timezone.now() - timezone.timedelta(hours=24)
            ).count()
        }
        return stats
    
    def display_statistics(self):
        """Display discovery statistics."""
        stats = self.get_discovery_statistics()
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('DISCOVERY STATISTICS'))
        self.stdout.write('='*50)
        
        self.stdout.write(f'Total switches: {stats["total_switches"]}')
        self.stdout.write(f'Switches with models: {stats["switches_with_models"]}')
        self.stdout.write(f'Unique vendors: {stats["vendors"]}')
        self.stdout.write(f'Online switches: {stats["online_switches"]}')
        self.stdout.write(f'Recent updates (24h): {stats["recent_updates"]}')
        
        # Model distribution
        model_stats = Switch.objects.values(
            'model__vendor__name', 'model__device_model'
        ).annotate(count=models.Count('id')).order_by('-count')[:10]
        
        if model_stats:
            self.stdout.write('\nTop device models:')
            for stat in model_stats:
                vendor = stat['model__vendor__name'] or 'Unknown'
                model = stat['model__device_model'] or 'Unknown'
                count = stat['count']
                self.stdout.write(f'  {vendor} {model}: {count}')