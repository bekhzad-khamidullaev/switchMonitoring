"""
Service layer for SNMP operations.
"""
from typing import Optional, Dict, Any, List
import socket
from ping3 import ping
from pysnmp.hlapi import *
from django.core.cache import cache

from .base_service import BaseService


class SNMPService(BaseService):
    """
    Service for handling SNMP operations.
    """
    
    # Standard SNMP OIDs
    OID_SYSTEM_DESCRIPTION = '1.3.6.1.2.1.1.1.0'
    OID_SYSTEM_UPTIME = '1.3.6.1.2.1.1.3.0'
    OID_SYSTEM_NAME = '1.3.6.1.2.1.1.5.0'
    OID_INTERFACES_NUMBER = '1.3.6.1.2.1.2.1.0'
    
    def __init__(self):
        super().__init__()
        self.timeout = 5
        self.retries = 2
    
    def ping_host(self, host: str) -> bool:
        """
        Ping a host to check if it's reachable.
        """
        try:
            result = ping(host, timeout=self.timeout)
            is_reachable = result is not None
            
            self.log_debug(f"Ping {host}: {'successful' if is_reachable else 'failed'}")
            return is_reachable
            
        except Exception as e:
            self.log_error(f"Error pinging {host}: {e}")
            return False
    
    def get_snmp_client(self, host: str, community: str) -> Optional[Any]:
        """
        Create SNMP client for the given host and community.
        """
        try:
            # Test SNMP connectivity with a simple get
            test_result = self.snmp_get(host, community, self.OID_SYSTEM_DESCRIPTION)
            if test_result:
                self.log_debug(f"SNMP connection successful to {host}")
                return {'host': host, 'community': community}
            else:
                self.log_warning(f"SNMP connection failed to {host}")
                return None
                
        except Exception as e:
            self.log_error(f"Error creating SNMP client for {host}: {e}")
            return None
    
    def snmp_get(self, host: str, community: str, oid: str) -> Optional[str]:
        """
        Perform SNMP GET operation.
        """
        try:
            # Create cache key
            cache_key = f"snmp_get_{host}_{oid}"
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((host, 161), timeout=self.timeout, retries=self.retries),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication:
                self.log_error(f"SNMP error indication for {host}: {errorIndication}")
                return None
            elif errorStatus:
                self.log_error(f"SNMP error status for {host}: {errorStatus.prettyPrint()}")
                return None
            else:
                result = str(varBinds[0][1])
                # Cache result for 5 minutes
                cache.set(cache_key, result, 300)
                return result
                
        except Exception as e:
            self.log_error(f"SNMP GET error for {host}, OID {oid}: {e}")
            return None
    
    def snmp_walk(self, host: str, community: str, oid: str) -> List[tuple]:
        """
        Perform SNMP WALK operation.
        """
        try:
            results = []
            
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((host, 161), timeout=self.timeout, retries=self.retries),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                
                if errorIndication:
                    self.log_error(f"SNMP walk error indication for {host}: {errorIndication}")
                    break
                elif errorStatus:
                    self.log_error(f"SNMP walk error status for {host}: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_result = str(varBind[0])
                        value_result = str(varBind[1])
                        results.append((oid_result, value_result))
            
            self.log_debug(f"SNMP walk for {host}, OID {oid}: {len(results)} results")
            return results
            
        except Exception as e:
            self.log_error(f"SNMP WALK error for {host}, OID {oid}: {e}")
            return []
    
    def get_system_description(self, snmp_client: Dict[str, str]) -> Optional[str]:
        """
        Get system description from SNMP.
        """
        return self.snmp_get(
            snmp_client['host'], 
            snmp_client['community'], 
            self.OID_SYSTEM_DESCRIPTION
        )
    
    def get_system_uptime(self, snmp_client: Dict[str, str]) -> Optional[str]:
        """
        Get system uptime from SNMP.
        """
        uptime_ticks = self.snmp_get(
            snmp_client['host'], 
            snmp_client['community'], 
            self.OID_SYSTEM_UPTIME
        )
        
        if uptime_ticks:
            try:
                # Convert timeticks to readable format
                ticks = int(uptime_ticks)
                seconds = ticks // 100
                days = seconds // 86400
                hours = (seconds % 86400) // 3600
                minutes = (seconds % 3600) // 60
                
                return f"{days}d {hours}h {minutes}m"
            except ValueError:
                return uptime_ticks
        
        return None
    
    def get_system_name(self, snmp_client: Dict[str, str]) -> Optional[str]:
        """
        Get system name from SNMP.
        """
        return self.snmp_get(
            snmp_client['host'], 
            snmp_client['community'], 
            self.OID_SYSTEM_NAME
        )
    
    def get_interface_count(self, snmp_client: Dict[str, str]) -> Optional[int]:
        """
        Get number of interfaces from SNMP.
        """
        result = self.snmp_get(
            snmp_client['host'], 
            snmp_client['community'], 
            self.OID_INTERFACES_NUMBER
        )
        
        if result:
            try:
                return int(result)
            except ValueError:
                return None
        
        return None
    
    def get_optical_signal_levels(self, snmp_client: Dict[str, str], 
                                rx_oid: str, tx_oid: str) -> Dict[str, Optional[float]]:
        """
        Get optical signal levels (RX/TX power) from SNMP.
        """
        result = {
            'rx_signal': None,
            'tx_signal': None
        }
        
        try:
            if rx_oid:
                rx_raw = self.snmp_get(snmp_client['host'], snmp_client['community'], rx_oid)
                if rx_raw:
                    result['rx_signal'] = self._convert_optical_power(rx_raw)
            
            if tx_oid:
                tx_raw = self.snmp_get(snmp_client['host'], snmp_client['community'], tx_oid)
                if tx_raw:
                    result['tx_signal'] = self._convert_optical_power(tx_raw)
            
            return result
            
        except Exception as e:
            self.log_error(f"Error getting optical signal levels: {e}")
            return result
    
    def _convert_optical_power(self, raw_value: str) -> Optional[float]:
        """
        Convert raw SNMP optical power value to dBm.
        """
        try:
            # This is a simplified conversion - actual conversion depends on device
            # Some devices return values in different units (mW, µW, etc.)
            value = float(raw_value)
            
            # If value is very large, it might be in µW, convert to dBm
            if value > 1000:
                # Convert µW to mW then to dBm
                mw = value / 1000
                if mw > 0:
                    dbm = 10 * math.log10(mw)
                    return round(dbm, 2)
            else:
                # Assume it's already in a reasonable range
                return round(value, 2)
            
            return None
            
        except (ValueError, TypeError):
            return None
    
    def test_connectivity(self, host: str, community: str) -> Dict[str, Any]:
        """
        Test connectivity to a device (both ping and SNMP).
        """
        result = {
            'host': host,
            'ping_success': False,
            'snmp_success': False,
            'ping_time': None,
            'system_description': None,
            'error_message': None
        }
        
        try:
            # Test ping first
            ping_result = ping(host, timeout=self.timeout)
            if ping_result is not None:
                result['ping_success'] = True
                result['ping_time'] = round(ping_result * 1000, 2)  # Convert to ms
            
            # Test SNMP
            if result['ping_success']:
                sys_descr = self.snmp_get(host, community, self.OID_SYSTEM_DESCRIPTION)
                if sys_descr:
                    result['snmp_success'] = True
                    result['system_description'] = sys_descr
                else:
                    result['error_message'] = "SNMP connection failed"
            else:
                result['error_message'] = "Host unreachable"
            
            return result
            
        except Exception as e:
            result['error_message'] = str(e)
            self.log_error(f"Error testing connectivity to {host}: {e}")
            return result