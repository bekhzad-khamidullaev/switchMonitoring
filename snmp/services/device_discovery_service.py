"""
Service for automatic device discovery and identification using MIB files.
Production-ready implementation for network device auto-discovery.
"""
import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from pysmi import debug
from pysmi.reader import FileReader
from pysmi.searcher import FileSearcher
from pysmi.parser import SmiV1Parser, SmiV2Parser
from pysmi.codegen import PySnmpCodeGen
from pysmi.compiler import MibCompiler
from pysnmp.hlapi import *
from pysnmp.smi import builder, view, compiler

from .base_service import BaseService
from .snmp_service import SNMPService
from ..models import Vendor, SwitchModel, Switch


@dataclass
class DeviceInfo:
    """Device information structure."""
    vendor: str
    model: str
    system_description: str
    enterprise_oid: str
    device_type: str
    capabilities: List[str]
    uplink_ports: List[int]
    optical_oids: Dict[str, str]
    interface_count: int
    firmware_version: Optional[str] = None


@dataclass
class UplinkInfo:
    """Uplink interface information."""
    port_index: int
    interface_name: str
    interface_description: str
    speed: Optional[int]
    operational_status: str
    admin_status: str
    rx_power_oid: Optional[str]
    tx_power_oid: Optional[str]
    rx_power: Optional[float]
    tx_power: Optional[float]
    interface_type: str
    last_change: Optional[int]


class DeviceDiscoveryService(BaseService):
    """
    Production service for automatic device discovery and monitoring.
    """
    
    def __init__(self):
        super().__init__()
        self.snmp_service = SNMPService()
        self.mibs_path = Path(settings.BASE_DIR) / 'mibs'
        self.compiled_mibs_path = Path(settings.BASE_DIR) / 'compiled_mibs'
        self._ensure_mib_directories()
        self._setup_mib_compiler()
        self._load_device_patterns()
        
        # Standard OIDs
        self.STANDARD_OIDS = {
            'sysDescr': '1.3.6.1.2.1.1.1.0',
            'sysObjectID': '1.3.6.1.2.1.1.2.0',
            'sysUpTime': '1.3.6.1.2.1.1.3.0',
            'sysName': '1.3.6.1.2.1.1.5.0',
            'ifNumber': '1.3.6.1.2.1.2.1.0',
            'ifDescr': '1.3.6.1.2.1.2.2.1.2',
            'ifType': '1.3.6.1.2.1.2.2.1.3',
            'ifSpeed': '1.3.6.1.2.1.2.2.1.5',
            'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',
            'ifAdminStatus': '1.3.6.1.2.1.2.2.1.7',
            'ifAlias': '1.3.6.1.2.1.31.1.1.1.18',
            'ifName': '1.3.6.1.2.1.31.1.1.1.1',
            'ifHighSpeed': '1.3.6.1.2.1.31.1.1.1.15',
        }
        
        # Enterprise OIDs for major vendors
        self.ENTERPRISE_OIDS = {
            '1.3.6.1.4.1.9': 'Cisco',
            '1.3.6.1.4.1.2011': 'Huawei',
            '1.3.6.1.4.1.25506': 'H3C',
            '1.3.6.1.4.1.6527': 'Nokia',
            '1.3.6.1.4.1.2636': 'Juniper',
            '1.3.6.1.4.1.1991': 'Foundry',
            '1.3.6.1.4.1.1588': 'Brocade',
            '1.3.6.1.4.1.11': 'HP',
            '1.3.6.1.4.1.171': 'D-Link',
            '1.3.6.1.4.1.89': 'Radware',
            '1.3.6.1.4.1.890': 'Zyxel',
        }
    
    def _ensure_mib_directories(self):
        """Ensure MIB directories exist."""
        self.mibs_path.mkdir(exist_ok=True)
        self.compiled_mibs_path.mkdir(exist_ok=True)
        self.log_info(f"MIB directories: {self.mibs_path}, {self.compiled_mibs_path}")
    
    def _setup_mib_compiler(self):
        """Setup MIB compiler for parsing vendor MIB files."""
        try:
            self.mib_builder = builder.MibBuilder()
            self.mib_view = view.MibViewController(self.mib_builder)
            
            # Add standard MIB sources
            self.mib_builder.addMibSources(
                builder.DirMibSource(str(self.mibs_path)),
                builder.DirMibSource(str(self.compiled_mibs_path))
            )
            
            # Load standard MIBs
            standard_mibs = [
                'SNMPv2-MIB',
                'IF-MIB',
                'ENTITY-MIB',
                'CISCO-SMI',
                'HUAWEI-MIB',
            ]
            
            for mib in standard_mibs:
                try:
                    self.mib_builder.loadModules(mib)
                    self.log_debug(f"Loaded MIB: {mib}")
                except Exception as e:
                    self.log_warning(f"Could not load MIB {mib}: {e}")
            
            self.log_info("MIB compiler setup completed")
            
        except Exception as e:
            self.log_error(f"Error setting up MIB compiler: {e}")
            self.mib_builder = None
            self.mib_view = None
    
    def _load_device_patterns(self):
        """Load device identification patterns from configuration."""
        self.device_patterns = {
            'cisco': {
                'patterns': [
                    r'cisco.*catalyst.*(\d+)',
                    r'cisco.*(\d+)\s*series',
                    r'ws-c(\d+)',
                    r'catalyst\s*(\d+)',
                ],
                'optical_oids': {
                    'rx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.5',
                    'tx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.4',
                },
                'uplink_detection': {
                    'interface_patterns': [r'gi\d+/\d+/\d+', r'te\d+/\d+/\d+', r'ethernet\d+/\d+'],
                    'speed_threshold': 1000,  # 1Gbps and above considered uplinks
                }
            },
            'huawei': {
                'patterns': [
                    r'huawei.*s(\d+)',
                    r's(\d+)-.*huawei',
                    r'vrp.*platform.*s(\d+)',
                ],
                'optical_oids': {
                    'rx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.7',
                    'tx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.8',
                },
                'uplink_detection': {
                    'interface_patterns': [r'gi\d+/\d+/\d+', r'xe\d+/\d+/\d+', r'ethernet\d+/\d+'],
                    'speed_threshold': 1000,
                }
            },
            'h3c': {
                'patterns': [
                    r'h3c.*s(\d+)',
                    r'hp.*(\d+)\s*switch',
                    r'comware.*platform.*(\d+)',
                ],
                'optical_oids': {
                    'rx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.2',
                    'tx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.3',
                },
                'uplink_detection': {
                    'interface_patterns': [r'gi\d+/\d+/\d+', r'xe\d+/\d+/\d+'],
                    'speed_threshold': 1000,
                }
            }
        }
    
    def discover_device(self, ip: str, community: str = 'public') -> Optional[DeviceInfo]:
        """
        Comprehensive device discovery and identification.
        
        Args:
            ip: Device IP address
            community: SNMP community string
            
        Returns:
            DeviceInfo object or None if discovery fails
        """
        try:
            self.log_info(f"Starting device discovery for {ip}")
            
            # Test basic connectivity
            if not self.snmp_service.ping_host(ip):
                self.log_warning(f"Device {ip} is not reachable via ping")
                return None
            
            # Get system information
            system_info = self._get_system_information(ip, community)
            if not system_info:
                self.log_warning(f"Could not retrieve system information from {ip}")
                return None
            
            # Identify vendor and model
            device_info = self._identify_device(system_info)
            if not device_info:
                self.log_warning(f"Could not identify device {ip}")
                return None
            
            # Discover interfaces and uplinks
            interfaces = self._discover_interfaces(ip, community)
            uplinks = self._identify_uplinks(interfaces, device_info.vendor.lower())
            device_info.uplink_ports = [uplink.port_index for uplink in uplinks]
            device_info.interface_count = len(interfaces)
            
            # Get optical OIDs for the vendor
            device_info.optical_oids = self._get_optical_oids(device_info.vendor.lower())
            
            # Cache the discovery result
            cache_key = f"device_discovery_{ip}"
            cache.set(cache_key, device_info, 3600)  # Cache for 1 hour
            
            self.log_info(f"Device discovery completed for {ip}: {device_info.vendor} {device_info.model}")
            return device_info
            
        except Exception as e:
            self.log_error(f"Error during device discovery for {ip}: {e}")
            return None
    
    def _get_system_information(self, ip: str, community: str) -> Optional[Dict[str, str]]:
        """Get basic system information via SNMP."""
        try:
            system_info = {}
            
            # Get system description
            sys_descr = self.snmp_service.snmp_get(ip, community, self.STANDARD_OIDS['sysDescr'])
            if sys_descr:
                system_info['sysDescr'] = sys_descr
            
            # Get system object ID (enterprise OID)
            sys_oid = self.snmp_service.snmp_get(ip, community, self.STANDARD_OIDS['sysObjectID'])
            if sys_oid:
                system_info['sysObjectID'] = sys_oid
            
            # Get system name
            sys_name = self.snmp_service.snmp_get(ip, community, self.STANDARD_OIDS['sysName'])
            if sys_name:
                system_info['sysName'] = sys_name
            
            # Get interface count
            if_number = self.snmp_service.snmp_get(ip, community, self.STANDARD_OIDS['ifNumber'])
            if if_number:
                system_info['ifNumber'] = if_number
            
            return system_info if system_info else None
            
        except Exception as e:
            self.log_error(f"Error getting system information from {ip}: {e}")
            return None
    
    def _identify_device(self, system_info: Dict[str, str]) -> Optional[DeviceInfo]:
        """Identify device vendor and model from system information."""
        try:
            sys_descr = system_info.get('sysDescr', '').lower()
            sys_oid = system_info.get('sysObjectID', '')
            
            # Identify vendor from enterprise OID
            vendor = self._identify_vendor(sys_oid, sys_descr)
            if not vendor:
                self.log_warning(f"Could not identify vendor from OID: {sys_oid}")
                return None
            
            # Identify model from system description
            model = self._identify_model(vendor.lower(), sys_descr)
            if not model:
                model = 'Unknown'
            
            # Determine device type
            device_type = self._determine_device_type(sys_descr)
            
            # Extract capabilities
            capabilities = self._extract_capabilities(sys_descr)
            
            device_info = DeviceInfo(
                vendor=vendor,
                model=model,
                system_description=system_info.get('sysDescr', ''),
                enterprise_oid=self._extract_enterprise_oid(sys_oid),
                device_type=device_type,
                capabilities=capabilities,
                uplink_ports=[],
                optical_oids={},
                interface_count=int(system_info.get('ifNumber', 0))
            )
            
            return device_info
            
        except Exception as e:
            self.log_error(f"Error identifying device: {e}")
            return None
    
    def _identify_vendor(self, sys_oid: str, sys_descr: str) -> Optional[str]:
        """Identify vendor from system OID and description."""
        try:
            # First try enterprise OID
            for oid_prefix, vendor in self.ENTERPRISE_OIDS.items():
                if sys_oid.startswith(oid_prefix):
                    return vendor
            
            # Fallback to description parsing
            vendor_keywords = {
                'cisco': ['cisco'],
                'huawei': ['huawei', 'vrp'],
                'h3c': ['h3c', 'hp', 'comware'],
                'juniper': ['juniper', 'junos'],
                'nokia': ['nokia', 'alcatel'],
                'brocade': ['brocade', 'foundry'],
                'd-link': ['d-link'],
                'zyxel': ['zyxel'],
            }
            
            for vendor, keywords in vendor_keywords.items():
                if any(keyword in sys_descr for keyword in keywords):
                    return vendor.title()
            
            return None
            
        except Exception as e:
            self.log_error(f"Error identifying vendor: {e}")
            return None
    
    def _identify_model(self, vendor: str, sys_descr: str) -> Optional[str]:
        """Identify device model from system description."""
        try:
            if vendor not in self.device_patterns:
                return None
            
            patterns = self.device_patterns[vendor]['patterns']
            
            for pattern in patterns:
                match = re.search(pattern, sys_descr, re.IGNORECASE)
                if match:
                    if match.groups():
                        return match.group(1)
                    else:
                        return match.group(0)
            
            return None
            
        except Exception as e:
            self.log_error(f"Error identifying model: {e}")
            return None
    
    def _determine_device_type(self, sys_descr: str) -> str:
        """Determine device type (switch, router, etc.) from description."""
        descr_lower = sys_descr.lower()
        
        if any(keyword in descr_lower for keyword in ['switch', 'catalyst']):
            return 'switch'
        elif any(keyword in descr_lower for keyword in ['router', 'asr', 'isr']):
            return 'router'
        elif any(keyword in descr_lower for keyword in ['firewall', 'asa']):
            return 'firewall'
        else:
            return 'unknown'
    
    def _extract_capabilities(self, sys_descr: str) -> List[str]:
        """Extract device capabilities from system description."""
        capabilities = []
        descr_lower = sys_descr.lower()
        
        capability_keywords = {
            'layer3': ['layer3', 'l3', 'routing'],
            'poe': ['poe', 'power over ethernet'],
            'stacking': ['stack', 'stacking'],
            'optical': ['sfp', 'optical', 'fiber'],
            'managed': ['managed', 'management'],
        }
        
        for capability, keywords in capability_keywords.items():
            if any(keyword in descr_lower for keyword in keywords):
                capabilities.append(capability)
        
        return capabilities
    
    def _extract_enterprise_oid(self, sys_oid: str) -> str:
        """Extract enterprise OID portion."""
        try:
            # Extract enterprise OID (usually first 7-8 parts)
            parts = sys_oid.split('.')
            if len(parts) >= 7:
                return '.'.join(parts[:7])
            return sys_oid
        except:
            return sys_oid
    
    def _discover_interfaces(self, ip: str, community: str) -> List[Dict[str, Any]]:
        """Discover all network interfaces."""
        try:
            interfaces = []
            
            # Walk interface table
            if_descr_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifDescr'])
            if_type_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifType'])
            if_speed_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifSpeed'])
            if_oper_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifOperStatus'])
            if_admin_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifAdminStatus'])
            
            # Get high speed interfaces (64-bit counters)
            if_high_speed_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifHighSpeed'])
            
            # Get interface names and aliases
            if_name_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifName'])
            if_alias_results = self.snmp_service.snmp_walk(ip, community, self.STANDARD_OIDS['ifAlias'])
            
            # Create interface mapping
            interface_data = {}
            
            for oid, descr in if_descr_results:
                if_index = self._extract_index_from_oid(oid)
                interface_data[if_index] = {'description': descr}
            
            # Add other interface information
            for oid, if_type in if_type_results:
                if_index = self._extract_index_from_oid(oid)
                if if_index in interface_data:
                    interface_data[if_index]['type'] = int(if_type)
            
            for oid, speed in if_speed_results:
                if_index = self._extract_index_from_oid(oid)
                if if_index in interface_data:
                    interface_data[if_index]['speed'] = int(speed)
            
            for oid, oper_status in if_oper_results:
                if_index = self._extract_index_from_oid(oid)
                if if_index in interface_data:
                    interface_data[if_index]['oper_status'] = int(oper_status)
            
            for oid, admin_status in if_admin_results:
                if_index = self._extract_index_from_oid(oid)
                if if_index in interface_data:
                    interface_data[if_index]['admin_status'] = int(admin_status)
            
            # Add high speed and names
            for oid, high_speed in if_high_speed_results:
                if_index = self._extract_index_from_oid(oid)
                if if_index in interface_data:
                    interface_data[if_index]['high_speed'] = int(high_speed)
            
            for oid, name in if_name_results:
                if_index = self._extract_index_from_oid(oid)
                if if_index in interface_data:
                    interface_data[if_index]['name'] = name
            
            for oid, alias in if_alias_results:
                if_index = self._extract_index_from_oid(oid)
                if if_index in interface_data:
                    interface_data[if_index]['alias'] = alias
            
            # Convert to list
            for if_index, data in interface_data.items():
                interface_info = {
                    'index': if_index,
                    'description': data.get('description', ''),
                    'name': data.get('name', ''),
                    'alias': data.get('alias', ''),
                    'type': data.get('type', 0),
                    'speed': data.get('speed', 0),
                    'high_speed': data.get('high_speed', 0),
                    'oper_status': data.get('oper_status', 0),
                    'admin_status': data.get('admin_status', 0),
                }
                interfaces.append(interface_info)
            
            self.log_info(f"Discovered {len(interfaces)} interfaces on {ip}")
            return interfaces
            
        except Exception as e:
            self.log_error(f"Error discovering interfaces on {ip}: {e}")
            return []
    
    def _extract_index_from_oid(self, oid: str) -> int:
        """Extract interface index from OID."""
        try:
            return int(oid.split('.')[-1])
        except:
            return 0
    
    def _identify_uplinks(self, interfaces: List[Dict[str, Any]], vendor: str) -> List[UplinkInfo]:
        """Identify uplink interfaces based on vendor-specific patterns."""
        try:
            uplinks = []
            
            if vendor not in self.device_patterns:
                # Generic uplink detection
                uplinks = self._generic_uplink_detection(interfaces)
            else:
                # Vendor-specific detection
                patterns = self.device_patterns[vendor]['uplink_detection']
                interface_patterns = patterns['interface_patterns']
                speed_threshold = patterns['speed_threshold']
                
                for interface in interfaces:
                    is_uplink = False
                    
                    # Check interface name/description patterns
                    interface_text = f"{interface.get('description', '')} {interface.get('name', '')}".lower()
                    
                    for pattern in interface_patterns:
                        if re.search(pattern, interface_text, re.IGNORECASE):
                            is_uplink = True
                            break
                    
                    # Check speed threshold
                    speed = max(interface.get('speed', 0), interface.get('high_speed', 0) * 1000000)
                    if speed >= speed_threshold * 1000000:  # Convert to bps
                        is_uplink = True
                    
                    # Check interface type (6 = ethernetCsmacd, 117 = gigabitEthernet)
                    if interface.get('type') in [6, 117]:
                        if speed >= speed_threshold * 1000000:
                            is_uplink = True
                    
                    if is_uplink:
                        uplink = UplinkInfo(
                            port_index=interface['index'],
                            interface_name=interface.get('name', ''),
                            interface_description=interface.get('description', ''),
                            speed=speed,
                            operational_status=self._status_to_string(interface.get('oper_status', 0)),
                            admin_status=self._status_to_string(interface.get('admin_status', 0)),
                            rx_power_oid=None,
                            tx_power_oid=None,
                            rx_power=None,
                            tx_power=None,
                            interface_type=self._interface_type_to_string(interface.get('type', 0)),
                            last_change=None
                        )
                        uplinks.append(uplink)
            
            self.log_info(f"Identified {len(uplinks)} uplink interfaces for vendor {vendor}")
            return uplinks
            
        except Exception as e:
            self.log_error(f"Error identifying uplinks: {e}")
            return []
    
    def _generic_uplink_detection(self, interfaces: List[Dict[str, Any]]) -> List[UplinkInfo]:
        """Generic uplink detection for unknown vendors."""
        uplinks = []
        
        for interface in interfaces:
            # Consider high-speed interfaces as potential uplinks
            speed = max(interface.get('speed', 0), interface.get('high_speed', 0) * 1000000)
            
            # 1Gbps or higher
            if speed >= 1000000000:
                uplink = UplinkInfo(
                    port_index=interface['index'],
                    interface_name=interface.get('name', ''),
                    interface_description=interface.get('description', ''),
                    speed=speed,
                    operational_status=self._status_to_string(interface.get('oper_status', 0)),
                    admin_status=self._status_to_string(interface.get('admin_status', 0)),
                    rx_power_oid=None,
                    tx_power_oid=None,
                    rx_power=None,
                    tx_power=None,
                    interface_type=self._interface_type_to_string(interface.get('type', 0)),
                    last_change=None
                )
                uplinks.append(uplink)
        
        return uplinks
    
    def _status_to_string(self, status: int) -> str:
        """Convert SNMP status integer to string."""
        status_map = {
            1: 'up',
            2: 'down',
            3: 'testing',
            4: 'unknown',
            5: 'dormant',
            6: 'notPresent',
            7: 'lowerLayerDown'
        }
        return status_map.get(status, 'unknown')
    
    def _interface_type_to_string(self, if_type: int) -> str:
        """Convert interface type to string."""
        type_map = {
            6: 'ethernet',
            117: 'gigabitEthernet',
            161: 'ieee8023adLag',
            131: 'tunnel',
        }
        return type_map.get(if_type, 'other')
    
    def _get_optical_oids(self, vendor: str) -> Dict[str, str]:
        """Get optical power monitoring OIDs for vendor."""
        if vendor in self.device_patterns:
            return self.device_patterns[vendor].get('optical_oids', {})
        return {}
    
    def auto_update_device_in_db(self, switch: Switch) -> bool:
        """
        Automatically update device information in database.
        
        Args:
            switch: Switch object to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            device_info = self.discover_device(switch.ip, switch.snmp_community_ro)
            if not device_info:
                return False
            
            # Get or create vendor
            vendor, created = Vendor.objects.get_or_create(
                name=device_info.vendor
            )
            if created:
                self.log_info(f"Created new vendor: {device_info.vendor}")
            
            # Get or create switch model
            switch_model, created = SwitchModel.objects.get_or_create(
                vendor=vendor,
                device_model=device_info.model,
                defaults={
                    'rx_oid': device_info.optical_oids.get('rx_power'),
                    'tx_oid': device_info.optical_oids.get('tx_power'),
                }
            )
            if created:
                self.log_info(f"Created new switch model: {device_info.vendor} {device_info.model}")
            
            # Update switch
            switch.model = switch_model
            switch.soft_version = device_info.firmware_version
            switch.save()
            
            self.log_info(f"Updated switch {switch.hostname} with discovered information")
            return True
            
        except Exception as e:
            self.log_error(f"Error updating device {switch.hostname} in database: {e}")
            return False