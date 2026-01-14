"""
Service for network discovery operations.
Handles subnet scanning and device discovery.
"""
import ipaddress
import concurrent.futures
import logging
from typing import List, Dict
from django.db import transaction

from snmp.models import Switch, SwitchModel, NeighborLink as SwitchNeighbor
from snmp.services.snmp_client import SnmpClient as SNMPClient
from snmp.api.exceptions import SNMPConnectionError

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Service for discovering network devices."""
    
    @staticmethod
    def discover_subnet(subnet: str, snmp_community: str = 'public',
                       snmp_version: str = '2c', timeout: int = 2,
                       max_workers: int = 50) -> Dict:
        """
        Discover switches in a subnet.
        
        Args:
            subnet: Network subnet in CIDR notation (e.g., 192.168.1.0/24)
            snmp_community: SNMP community string
            snmp_version: SNMP version (1, 2c, 3)
            timeout: SNMP timeout in seconds
            max_workers: Maximum concurrent workers
            
        Returns:
            Dictionary with discovery results
        """
        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except ValueError as e:
            logger.error(f"Invalid subnet format: {subnet}")
            raise ValueError(f"Invalid subnet: {e}")
        
        results = {
            'subnet': subnet,
            'total_ips': network.num_addresses,
            'scanned': 0,
            'discovered': 0,
            'devices': [],
            'errors': []
        }
        
        # Get list of IPs to scan
        ips_to_scan = [str(ip) for ip in network.hosts()]
        
        # Scan IPs concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ip = {
                executor.submit(
                    DiscoveryService._probe_device,
                    ip, snmp_community, snmp_version, timeout
                ): ip for ip in ips_to_scan
            }
            
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                results['scanned'] += 1
                
                try:
                    device_info = future.result()
                    if device_info:
                        results['discovered'] += 1
                        results['devices'].append(device_info)
                        logger.info(f"Discovered device at {ip}: {device_info.get('sysName')}")
                except Exception as e:
                    results['errors'].append({
                        'ip': ip,
                        'error': str(e)
                    })
        
        return results
    
    @staticmethod
    def _probe_device(ip: str, community: str, version: str, timeout: int) -> Dict:
        """
        Probe a single IP for SNMP device.
        
        Args:
            ip: IP address to probe
            community: SNMP community
            version: SNMP version
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with device info or None if not reachable
        """
        try:
            client = SNMPClient(ip, community, version=version, timeout=timeout)
            
            # Try to get system information
            sys_descr = client.get('1.3.6.1.2.1.1.1.0')
            if not sys_descr:
                return None
            
            sys_name = client.get('1.3.6.1.2.1.1.5.0')
            sys_uptime = client.get('1.3.6.1.2.1.1.3.0')
            sys_contact = client.get('1.3.6.1.2.1.1.4.0')
            sys_location = client.get('1.3.6.1.2.1.1.6.0')
            
            # Try to get MAC address
            mac_address = None
            try:
                if_phys_address = client.get('1.3.6.1.2.1.2.2.1.6.1')
                if if_phys_address:
                    mac_address = ':'.join([f'{b:02x}' for b in if_phys_address])
            except:
                pass
            
            return {
                'ip_address': ip,
                'sysDescr': sys_descr,
                'sysName': sys_name or ip,
                'sysUpTime': sys_uptime,
                'sysContact': sys_contact,
                'sysLocation': sys_location,
                'mac_address': mac_address,
                'snmp_community': community,
                'snmp_version': version,
            }
            
        except Exception as e:
            # Device not reachable or not responding to SNMP
            return None
    
    @staticmethod
    def auto_create_switches(discovered_devices: List[Dict],
                           default_ats=None, default_branch=None,
                           default_host_group=None) -> Dict:
        """
        Automatically create Switch objects from discovered devices.
        
        Args:
            discovered_devices: List of discovered device dictionaries
            default_ats: Default ATS to assign
            default_branch: Default branch to assign
            default_host_group: Default host group to assign
            
        Returns:
            Dictionary with creation results
        """
        results = {
            'total': len(discovered_devices),
            'created': 0,
            'skipped': 0,
            'errors': []
        }
        
        for device in discovered_devices:
            try:
                ip_address = device['ip_address']
                
                # Check if switch already exists
                if Switch.objects.filter(ip_address=ip_address).exists():
                    results['skipped'] += 1
                    logger.info(f"Switch with IP {ip_address} already exists, skipping")
                    continue
                
                # Try to determine device model
                device_model = DiscoveryService._identify_device_model(device['sysDescr'])
                
                # Create switch
                with transaction.atomic():
                    switch = Switch.objects.create(
                        name=device['sysName'] or ip_address,
                        ip_address=ip_address,
                        mac_address=device.get('mac_address'),
                        ats=default_ats,
                        branch=default_branch,
                        host_group=default_host_group,
                        device_model=device_model,
                        location=device.get('sysLocation'),
                        contact=device.get('sysContact'),
                        snmp_community_ro=device['snmp_community'],
                        snmp_version=device['snmp_version'],
                        status='online',
                        is_active=True,
                        is_monitored=False,  # Don't monitor by default
                    )
                    
                    results['created'] += 1
                    logger.info(f"Created switch: {switch.name} ({ip_address})")
                    
            except Exception as e:
                results['errors'].append({
                    'ip': device.get('ip_address'),
                    'error': str(e)
                })
                logger.error(f"Failed to create switch from device {device.get('ip_address')}: {e}")
        
        return results
    
    @staticmethod
    def _identify_device_model(sys_descr: str):
        """
        Try to identify device model from sysDescr.
        
        Args:
            sys_descr: System description string
            
        Returns:
            SwitchModel instance or None
        """
        if not sys_descr:
            return None
        
        sys_descr_lower = sys_descr.lower()
        
        # Try to match against known models
        for model in SwitchModel.objects.all():
            if model.vendor.lower() in sys_descr_lower and model.model.lower() in sys_descr_lower:
                return model
        
        # Try to create a new model based on description
        vendor = None
        if 'cisco' in sys_descr_lower:
            vendor = 'Cisco'
        elif 'huawei' in sys_descr_lower:
            vendor = 'Huawei'
        elif 'hp' in sys_descr_lower or 'hewlett' in sys_descr_lower:
            vendor = 'HP'
        elif 'juniper' in sys_descr_lower:
            vendor = 'Juniper'
        elif 'mikrotik' in sys_descr_lower:
            vendor = 'MikroTik'
        
        if vendor:
            # Try to find or create a generic model
            model, created = SwitchModel.objects.get_or_create(
                vendor=vendor,
                model='Generic',
                defaults={'description': 'Auto-detected generic model'}
            )
            return model
        
        return None
    
    @staticmethod
    def discover_neighbors(switch_id: int, protocol: str = 'lldp') -> Dict:
        """
        Discover neighbors for a switch using LLDP or CDP.
        
        Args:
            switch_id: ID of switch to discover neighbors for
            protocol: Protocol to use (lldp or cdp)
            
        Returns:
            Dictionary with neighbor information
        """
        from snmp.models import SwitchNeighbor
        
        switch = Switch.objects.get(id=switch_id)
        
        client = SNMPClient(
            switch.ip_address,
            switch.snmp_community_ro,
            version=switch.snmp_version,
            port=switch.snmp_port
        )
        
        results = {
            'switch_id': switch_id,
            'protocol': protocol,
            'neighbors_found': 0,
            'neighbors': []
        }
        
        try:
            if protocol.lower() == 'lldp':
                neighbors = DiscoveryService._discover_lldp_neighbors(switch, client)
            elif protocol.lower() == 'cdp':
                neighbors = DiscoveryService._discover_cdp_neighbors(switch, client)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")
            
            # Save neighbors to database
            for neighbor_data in neighbors:
                neighbor, created = SwitchNeighbor.objects.update_or_create(
                    switch=switch,
                    port=neighbor_data.get('port'),
                    neighbor_chassis_id=neighbor_data.get('chassis_id'),
                    defaults={
                        'neighbor_device_id': neighbor_data.get('device_id'),
                        'neighbor_port_id': neighbor_data.get('port_id'),
                        'neighbor_system_name': neighbor_data.get('system_name'),
                        'neighbor_system_description': neighbor_data.get('system_description'),
                        'neighbor_management_address': neighbor_data.get('mgmt_address'),
                        'protocol': protocol,
                        'last_seen': timezone.now()
                    }
                )
                results['neighbors'].append(neighbor_data)
            
            results['neighbors_found'] = len(neighbors)
            
        except Exception as e:
            logger.error(f"Failed to discover neighbors for switch {switch_id}: {e}")
            raise
        
        return results
    
    @staticmethod
    def _discover_lldp_neighbors(switch, client) -> List[Dict]:
        """Discover LLDP neighbors."""
        neighbors = []
        
        try:
            # LLDP Remote Systems Data
            # lldpRemChassisId - 1.0.8802.1.1.2.1.4.1.1.5
            chassis_ids = client.walk('1.0.8802.1.1.2.1.4.1.1.5')
            
            # Get more LLDP data if available
            # This is a simplified version - full implementation would walk all LLDP MIB tables
            
            for chassis_id in chassis_ids:
                neighbors.append({
                    'chassis_id': chassis_id,
                    'device_id': chassis_id,
                    'system_name': 'Unknown',
                    'port': None,
                })
        except Exception as e:
            logger.error(f"Error discovering LLDP neighbors: {e}")
        
        return neighbors
    
    @staticmethod
    def _discover_cdp_neighbors(switch, client) -> List[Dict]:
        """Discover CDP neighbors."""
        neighbors = []
        
        try:
            # CDP is Cisco-specific
            # cdpCacheDeviceId - 1.3.6.1.4.1.9.9.23.1.2.1.1.6
            device_ids = client.walk('1.3.6.1.4.1.9.9.23.1.2.1.1.6')
            
            for device_id in device_ids:
                neighbors.append({
                    'device_id': device_id,
                    'chassis_id': device_id,
                    'system_name': device_id,
                    'port': None,
                })
        except Exception as e:
            logger.error(f"Error discovering CDP neighbors: {e}")
        
        return neighbors
