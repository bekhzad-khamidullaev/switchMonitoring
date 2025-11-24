"""
Service for managing MIB files and vendor-specific OID discovery.
Production-ready MIB management and OID resolution service.
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.core.cache import cache

# Optional MIB imports; system will work without them in production
try:
    from pysnmp.smi import builder, view
except Exception:
    builder = None
    view = None

# pysmi toolchain is optional; if missing, we skip compilation features
try:
    from pysmi import debug as pysmi_debug  # noqa: F401
    from pysmi.parser import SmiV1Parser, SmiV2Parser  # noqa: F401
    from pysmi.codegen import PySnmpCodeGen  # noqa: F401
    from pysmi.compiler import MibCompiler  # noqa: F401
    from pysmi.reader import FileReader  # noqa: F401
except Exception:
    SmiV1Parser = SmiV2Parser = PySnmpCodeGen = MibCompiler = FileReader = None
    pysmi_debug = None

from .base_service import BaseService


class MibManagerService(BaseService):
    """
    Production service for MIB management and vendor OID discovery.
    """
    
    def __init__(self):
        super().__init__()
        self.base_dir = Path(settings.BASE_DIR)
        self.mibs_path = self.base_dir / 'mibs'
        self.compiled_mibs_path = self.base_dir / 'compiled_mibs'
        
        # Ensure directories exist
        self.mibs_path.mkdir(exist_ok=True)
        self.compiled_mibs_path.mkdir(exist_ok=True)
        
        self._setup_mib_compiler()
        self._load_vendor_mib_mappings()
        
        # Cache for compiled MIB data
        self.mib_cache = {}
        
        # Vendor-specific OID patterns
        self.vendor_oid_patterns = self._initialize_vendor_patterns()
    
    def _setup_mib_compiler(self):
        """Initialize MIB compiler and builder."""
        try:
            # Setup MIB builder
            if builder and view:
                self.mib_builder = builder.MibBuilder()
                self.mib_view = view.MibViewController(self.mib_builder)
            else:
                self.mib_builder = None
                self.mib_view = None
            
            # Add MIB sources
            mib_sources = [
                builder.DirMibSource(str(self.mibs_path)),
                builder.DirMibSource(str(self.compiled_mibs_path)),
            ]
            
            # Add vendor-specific directories
            for vendor_dir in ['cisco', 'huawei', 'h3c', 'juniper', 'standard']:
                vendor_path = self.mibs_path / vendor_dir
                if vendor_path.exists():
                    mib_sources.append(builder.DirMibSource(str(vendor_path)))
            
            self.mib_builder.addMibSources(*mib_sources)
            
            # Setup MIB compiler
            # Initialize compiler only if pysmi is available
            if MibCompiler and SmiV1Parser and SmiV2Parser and PySnmpCodeGen and FileReader:
                self.mib_compiler = MibCompiler(
                    SmiV1Parser(), SmiV2Parser(),
                    PySnmpCodeGen(),
                    FileReader(str(self.mibs_path)),
                    FileReader(str(self.mibs_path)),
                )
            else:
                self.mib_compiler = None
            
            # Load essential MIBs
            self._load_essential_mibs()
            
            self.log_info("MIB compiler initialized successfully")
            
        except Exception as e:
            self.log_warning(f"MIB toolchain not available, continuing without MIB compilation: {e}")
            self.mib_builder = None
            self.mib_view = None
            self.mib_compiler = None
    
    def _load_essential_mibs(self):
        """Load essential MIBs for device discovery."""
        essential_mibs = [
            'SNMPv2-SMI',
            'SNMPv2-TC',
            'SNMPv2-MIB',
            'IF-MIB',
            'ENTITY-MIB',
        ]
        
        for mib_name in essential_mibs:
            try:
                self.mib_builder.loadModules(mib_name)
                self.log_debug(f"Loaded essential MIB: {mib_name}")
            except Exception as e:
                self.log_warning(f"Could not load essential MIB {mib_name}: {e}")
    
    def _load_vendor_mib_mappings(self):
        """Load vendor-specific MIB mappings and OID patterns."""
        self.vendor_mibs = {
            'cisco': {
                'mibs': [
                    'CISCO-SMI',
                    'CISCO-OPTICAL-MONITOR-MIB',
                    'CISCO-ENTITY-FRU-CONTROL-MIB',
                    'CISCO-ENTITY-VENDORTYPE-OID-MIB',
                    'CISCO-PRODUCTS-MIB',
                ],
                'optical_base_oids': {
                    'rx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.5',
                    'tx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.4',
                    'temperature': '1.3.6.1.4.1.9.9.92.1.1.1.1.3',
                    'voltage': '1.3.6.1.4.1.9.9.92.1.1.1.1.6',
                    'current': '1.3.6.1.4.1.9.9.92.1.1.1.1.7',
                }
            },
            'huawei': {
                'mibs': [
                    'HUAWEI-MIB',
                    'HUAWEI-ENTITY-EXTENT-MIB',
                    'HUAWEI-OPTICAL-MIB',
                    'HUAWEI-DEVICE-MIB',
                ],
                'optical_base_oids': {
                    'rx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.7',
                    'tx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.8',
                    'temperature': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.5',
                    'voltage': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.6',
                }
            },
            'h3c': {
                'mibs': [
                    'H3C-ENTITY-EXT-MIB',
                    'H3C-TRANSCEIVER-INFO-MIB',
                    'H3C-OID-MIB',
                ],
                'optical_base_oids': {
                    'rx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.2',
                    'tx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.3',
                    'temperature': '1.3.6.1.4.1.25506.8.35.18.4.3.1.4',
                }
            }
        }
    
    def _initialize_vendor_patterns(self) -> Dict[str, Any]:
        """Initialize vendor-specific OID and model detection patterns."""
        return {
            'cisco': {
                'enterprise_oids': ['1.3.6.1.4.1.9'],
                'model_patterns': [
                    (r'catalyst.*(\d{4})', r'Catalyst \1'),
                    (r'ws-c(\d{4})', r'Catalyst \1'),
                    (r'cisco.*(\d{4})', r'Cisco \1'),
                ],
                'interface_patterns': {
                    'gigabit': [r'gi\d+/\d+(/\d+)?', r'gigabitethernet\d+/\d+(/\d+)?'],
                    'tengigabit': [r'te\d+/\d+(/\d+)?', r'tengigabitethernet\d+/\d+(/\d+)?'],
                    'uplink': [r'gi\d+/0/\d+', r'te\d+/0/\d+'],  # Common uplink patterns
                }
            },
            'huawei': {
                'enterprise_oids': ['1.3.6.1.4.1.2011'],
                'model_patterns': [
                    (r's(\d{4})', r'S\1'),
                    (r'huawei.*s(\d{4})', r'S\1'),
                    (r'vrp.*s(\d{4})', r'S\1'),
                ],
                'interface_patterns': {
                    'gigabit': [r'gi\d+/\d+/\d+', r'gigabitethernet\d+/\d+/\d+'],
                    'tengigabit': [r'xe\d+/\d+/\d+', r'10ge\d+/\d+/\d+'],
                    'uplink': [r'gi0/0/\d+', r'xe0/0/\d+'],
                }
            },
            'h3c': {
                'enterprise_oids': ['1.3.6.1.4.1.25506'],
                'model_patterns': [
                    (r'h3c.*s(\d{4})', r'S\1'),
                    (r'hp.*(\d{4})', r'HP \1'),
                    (r'comware.*(\d{4})', r'S\1'),
                ],
                'interface_patterns': {
                    'gigabit': [r'gi\d+/\d+/\d+', r'gigabitethernet\d+/\d+/\d+'],
                    'tengigabit': [r'xe\d+/\d+/\d+', r'ten-gigabitethernet\d+/\d+/\d+'],
                    'uplink': [r'gi1/0/\d+', r'xe1/0/\d+'],
                }
            }
        }
    
    def discover_vendor_oids(self, vendor: str, device_model: str) -> Dict[str, str]:
        """
        Discover vendor-specific OIDs for optical monitoring.
        
        Args:
            vendor: Device vendor name
            device_model: Device model
            
        Returns:
            Dictionary of OID mappings
        """
        try:
            vendor_lower = vendor.lower()
            cache_key = f"vendor_oids_{vendor_lower}_{device_model}"
            
            # Check cache first
            cached_oids = cache.get(cache_key)
            if cached_oids:
                return cached_oids
            
            # Get base OIDs for vendor
            if vendor_lower not in self.vendor_mibs:
                self.log_warning(f"No MIB mapping found for vendor: {vendor}")
                return {}
            
            vendor_config = self.vendor_mibs[vendor_lower]
            base_oids = vendor_config.get('optical_base_oids', {})
            
            # Try to load vendor-specific MIBs
            discovered_oids = base_oids.copy()
            
            # Attempt to discover model-specific OIDs
            model_oids = self._discover_model_specific_oids(vendor_lower, device_model)
            if model_oids:
                discovered_oids.update(model_oids)
            
            # Cache the result
            cache.set(cache_key, discovered_oids, 3600)  # Cache for 1 hour
            
            self.log_info(f"Discovered {len(discovered_oids)} OIDs for {vendor} {device_model}")
            return discovered_oids
            
        except Exception as e:
            self.log_error(f"Error discovering vendor OIDs for {vendor}: {e}")
            return {}
    
    def _discover_model_specific_oids(self, vendor: str, model: str) -> Dict[str, str]:
        """Discover model-specific OIDs by analyzing MIB files."""
        try:
            model_oids = {}
            
            # Model-specific OID discovery logic
            if vendor == 'cisco':
                model_oids = self._discover_cisco_model_oids(model)
            elif vendor == 'huawei':
                model_oids = self._discover_huawei_model_oids(model)
            elif vendor == 'h3c':
                model_oids = self._discover_h3c_model_oids(model)
            
            return model_oids
            
        except Exception as e:
            self.log_error(f"Error discovering model-specific OIDs for {vendor} {model}: {e}")
            return {}
    
    def _discover_cisco_model_oids(self, model: str) -> Dict[str, str]:
        """Discover Cisco model-specific OIDs."""
        # Cisco Catalyst switches often use different OIDs based on series
        model_oids = {}
        
        # Extract model number
        model_number = re.search(r'(\d{4})', model)
        if not model_number:
            return model_oids
        
        series = model_number.group(1)
        
        # Series-specific OID mappings
        if series in ['2960', '3560', '3750']:
            # Older Catalyst series
            model_oids.update({
                'rx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.5',
                'tx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.4',
            })
        elif series in ['9200', '9300', '9500']:
            # Newer Catalyst series
            model_oids.update({
                'rx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.5',
                'tx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.4',
                'dom_temperature': '1.3.6.1.4.1.9.9.92.1.1.1.1.3',
                'dom_voltage': '1.3.6.1.4.1.9.9.92.1.1.1.1.6',
            })
        
        return model_oids
    
    def _discover_huawei_model_oids(self, model: str) -> Dict[str, str]:
        """Discover Huawei model-specific OIDs."""
        model_oids = {}
        
        # Extract series information
        series_match = re.search(r's(\d{4})', model.lower())
        if not series_match:
            return model_oids
        
        series = series_match.group(1)
        
        # Series-specific OID mappings
        if series in ['5700', '6700']:
            # Campus switches
            model_oids.update({
                'rx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.7',
                'tx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.8',
                'temperature': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.5',
                'bias_current': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.9',
            })
        elif series in ['9300', '9700']:
            # Data center switches
            model_oids.update({
                'rx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.7',
                'tx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.8',
            })
        
        return model_oids
    
    def _discover_h3c_model_oids(self, model: str) -> Dict[str, str]:
        """Discover H3C model-specific OIDs."""
        model_oids = {}
        
        # H3C typically uses consistent OIDs across models
        model_oids.update({
            'rx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.2',
            'tx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.3',
            'temperature': '1.3.6.1.4.1.25506.8.35.18.4.3.1.4',
            'bias_current': '1.3.6.1.4.1.25506.8.35.18.4.3.1.5',
        })
        
        return model_oids
    
    def identify_uplink_interfaces(self, vendor: str, interfaces: List[Dict[str, Any]]) -> List[int]:
        """
        Identify uplink interfaces based on vendor-specific patterns.
        
        Args:
            vendor: Device vendor
            interfaces: List of interface information
            
        Returns:
            List of interface indices that are uplinks
        """
        try:
            vendor_lower = vendor.lower()
            uplink_indices = []
            
            if vendor_lower not in self.vendor_oid_patterns:
                # Generic uplink detection
                return self._generic_uplink_detection(interfaces)
            
            vendor_patterns = self.vendor_oid_patterns[vendor_lower]
            uplink_patterns = vendor_patterns.get('interface_patterns', {}).get('uplink', [])
            
            for interface in interfaces:
                interface_name = interface.get('name', '').lower()
                interface_desc = interface.get('description', '').lower()
                interface_speed = interface.get('speed', 0)
                
                # Check interface name patterns
                is_uplink = False
                
                for pattern in uplink_patterns:
                    if re.search(pattern, interface_name, re.IGNORECASE):
                        is_uplink = True
                        break
                    if re.search(pattern, interface_desc, re.IGNORECASE):
                        is_uplink = True
                        break
                
                # Check speed threshold (1Gbps or higher)
                if interface_speed >= 1000000000:  # 1 Gbps in bps
                    is_uplink = True
                
                # Vendor-specific logic
                if vendor_lower == 'cisco':
                    # Cisco uplink detection
                    if any(pattern in interface_name for pattern in ['gi0/0/', 'te0/0/', 'gi1/0/', 'te1/0/']):
                        is_uplink = True
                elif vendor_lower == 'huawei':
                    # Huawei uplink detection
                    if any(pattern in interface_name for pattern in ['gi0/0/', 'xe0/0/', '10ge0/0/']):
                        is_uplink = True
                elif vendor_lower == 'h3c':
                    # H3C uplink detection
                    if any(pattern in interface_name for pattern in ['gi1/0/', 'xe1/0/', 'ten-gi1/0/']):
                        is_uplink = True
                
                if is_uplink:
                    uplink_indices.append(interface['index'])
            
            self.log_info(f"Identified {len(uplink_indices)} uplink interfaces for {vendor}")
            return uplink_indices
            
        except Exception as e:
            self.log_error(f"Error identifying uplink interfaces for {vendor}: {e}")
            return self._generic_uplink_detection(interfaces)
    
    def _generic_uplink_detection(self, interfaces: List[Dict[str, Any]]) -> List[int]:
        """Generic uplink detection based on speed and interface type."""
        uplink_indices = []
        
        for interface in interfaces:
            # Consider high-speed interfaces as uplinks
            interface_speed = interface.get('speed', 0)
            interface_type = interface.get('type', 0)
            
            # Gigabit Ethernet or faster
            if interface_speed >= 1000000000:  # 1 Gbps
                uplink_indices.append(interface['index'])
            # Interface type 117 (gigabitEthernet) or 6 (ethernetCsmacd) with high speed
            elif interface_type in [6, 117] and interface_speed >= 100000000:  # 100 Mbps
                uplink_indices.append(interface['index'])
        
        return uplink_indices
    
    def compile_mib(self, mib_path: str) -> bool:
        """
        Compile a MIB file for use with pysnmp.
        
        Args:
            mib_path: Path to the MIB file
            
        Returns:
            True if compilation successful, False otherwise
        """
        try:
            if not self.mib_compiler:
                self.log_error("MIB compiler not initialized")
                return False
            
            mib_file = Path(mib_path)
            if not mib_file.exists():
                self.log_error(f"MIB file not found: {mib_path}")
                return False
            
            # Extract MIB name
            mib_name = mib_file.stem
            
            # Compile MIB
            compiled_data = self.mib_compiler.compile(
                mib_name,
                genTexts=True,
                textFilter=lambda x: x,
                genDebug=False
            )
            
            if compiled_data:
                # Save compiled MIB
                output_file = self.compiled_mibs_path / f"{mib_name}.py"
                with open(output_file, 'w') as f:
                    f.write(compiled_data)
                
                self.log_info(f"Successfully compiled MIB: {mib_name}")
                return True
            else:
                self.log_error(f"Failed to compile MIB: {mib_name}")
                return False
                
        except Exception as e:
            self.log_error(f"Error compiling MIB {mib_path}: {e}")
            return False
    
    def load_vendor_mibs(self, vendor: str) -> bool:
        """
        Load all MIBs for a specific vendor.
        
        Args:
            vendor: Vendor name
            
        Returns:
            True if at least one MIB was loaded successfully
        """
        try:
            vendor_lower = vendor.lower()
            
            if vendor_lower not in self.vendor_mibs:
                self.log_warning(f"No MIB configuration found for vendor: {vendor}")
                return False
            
            vendor_config = self.vendor_mibs[vendor_lower]
            mibs_to_load = vendor_config.get('mibs', [])
            
            loaded_count = 0
            
            for mib_name in mibs_to_load:
                try:
                    self.mib_builder.loadModules(mib_name)
                    loaded_count += 1
                    self.log_debug(f"Loaded {vendor} MIB: {mib_name}")
                except Exception as e:
                    self.log_warning(f"Could not load {vendor} MIB {mib_name}: {e}")
            
            if loaded_count > 0:
                self.log_info(f"Loaded {loaded_count}/{len(mibs_to_load)} MIBs for {vendor}")
                return True
            else:
                self.log_error(f"Failed to load any MIBs for {vendor}")
                return False
                
        except Exception as e:
            self.log_error(f"Error loading vendor MIBs for {vendor}: {e}")
            return False
    
    def get_mib_info(self) -> Dict[str, Any]:
        """Get information about loaded MIBs."""
        try:
            if not self.mib_builder:
                return {"error": "MIB builder not initialized"}
            
            loaded_mibs = []
            available_mibs = []
            
            # Get loaded MIBs
            for mib_name in self.mib_builder.mibSymbols:
                loaded_mibs.append(str(mib_name))
            
            # Get available MIB files
            for mib_file in self.mibs_path.rglob('*.mib'):
                available_mibs.append(mib_file.name)
            
            for vendor_dir in ['cisco', 'huawei', 'h3c', 'juniper']:
                vendor_path = self.mibs_path / vendor_dir
                if vendor_path.exists():
                    for mib_file in vendor_path.glob('*.mib'):
                        available_mibs.append(f"{vendor_dir}/{mib_file.name}")
            
            info = {
                'loaded_mibs': sorted(loaded_mibs),
                'available_mib_files': sorted(available_mibs),
                'vendor_configs': list(self.vendor_mibs.keys()),
                'mibs_path': str(self.mibs_path),
                'compiled_mibs_path': str(self.compiled_mibs_path),
            }
            
            return info
            
        except Exception as e:
            self.log_error(f"Error getting MIB info: {e}")
            return {"error": str(e)}