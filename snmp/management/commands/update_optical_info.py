import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from snmp.models import Device, DevicePort, Interface
from snmp.services.metrics.interface_filters import is_eligible_optical_ethernet
from pysnmp.hlapi import *
import math
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")


def mw_to_dbm(mw):
    if mw > 0:
        mw /= 1000
        dbm = 10 * math.log10(mw)
        logger.info(f":::::::Input is={mw}, Output is={dbm}:::::::")
        return dbm
    else:
        return float('nan')


class SNMPUpdater:
    def __init__(self, selected_switch, snmp_community):
        self.selected_switch = selected_switch
        if selected_switch.model:
            self.model = selected_switch.model.device_model
        else:
            self.model = None
        self.ip = selected_switch.ip
        self.snmp_community = snmp_community
        self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID = self.get_snmp_oids()
        self.logger = logging.getLogger("SNMP RESPONSE")


        
    def get_snmp_oids(self):
        if self.model == 'MES3500-24S':
            return (
                '1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.4',
                '1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.5',
                '1.3.6.1.4.1.890.1.15.3.84.1.1.1.2.{port}',
                '1.3.6.1.4.1.890.1.15.3.84.1.1.1.4.{port}',
            )
        elif self.model == 'MES2428':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES2408':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES2428B':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES2408B':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES3500-24':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.{port}',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.{port}',
            )
        elif self.model == 'MES3500-10':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.{port}',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.{port}',
            )
        elif self.model == 'GS3700-24HP':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.{port}',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.{port}',
            )
        elif self.model == 'MES1124MB':
            return (
                'iso.3.6.1.4.1.89.90.1.2.1.3.{port}.8',
                'iso.3.6.1.4.1.89.90.1.2.1.3.{port}.9',
                'iso.3.6.1.4.1.35265.1.23.53.1.1.1.5',
                '',
            )
        elif self.model == 'MGS3520-28':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.{port}',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.{port}',
            )
        elif self.model == 'SNR-S2985G-24TC':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.{port}',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.{port}',
                '',
                '',
            )
        elif self.model == 'SNR-S2985G-8T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.{port}',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.{port}',
                '',
                '',
            )
        elif self.model == 'SNR-S2982G-24T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.{port}',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.{port}',
                '',
                '',
            )
        elif self.model == 'T2600G-28TS':
            return (
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.5.{port}',
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.6.{port}',
                '',
                '',
            )
        elif self.model == 'S3328TP-SI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.{port}',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.{port}',
                '',
                '',
            )
        elif self.model == 'S3328TP-EI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.{port}',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.{port}',
                '',
                '',
            )
        else:
            return ('iso.3.6.1.4.1.2011.5.14.6.4.1.4.{port}',
                    'iso.3.6.1.4.1.2011.5.14.6.4.1.5.{port}',
                    None,
                    None)
        
    def perform_snmpwalk(self, oid):
        try:
            snmp_walk = getCmd(
                SnmpEngine(),
                CommunityData(self.snmp_community),
                UdpTransportTarget((self.ip, 161), timeout=2, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )

            snmp_response = []
            for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
                if errorIndication:
                    self.logger.error(f"SNMP error: {errorIndication}")
                    continue
                if varBinds:
                    for varBind in varBinds:
                        snmp_response.append(str(varBind))
            return snmp_response
        except TimeoutError:
            self.logger.warning(f"SNMP timeout for IP address: {self.ip}")
            return []
        except Exception as e:
            self.logger.error(f"Error during SNMP walk: {e}")
            return []

    async def update_switch_data_async(self):
        loop = asyncio.get_event_loop()
        switch = self.selected_switch
        
        # Determine all eligible interfaces
        eligible_interfaces = [
            iface for iface in switch.interfaces.all()
            if is_eligible_optical_ethernet(iface)
        ]
        
        if not eligible_interfaces:
            self.logger.info(f"No eligible optical Ethernet interfaces found for {switch.hostname}")
            return

        tx_template, rx_template, vendor_template, part_template = self.get_snmp_oids()
        
        first_signals = None

        for iface in eligible_interfaces:
            port_index = iface.if_index
            tx_oid = tx_template.replace('{port}', str(port_index)) if tx_template else None
            rx_oid = rx_template.replace('{port}', str(port_index)) if rx_template else None
            vendor_oid = vendor_template.replace('{port}', str(port_index)) if vendor_template else None
            part_oid = part_template.replace('{port}', str(port_index)) if part_template else None
            
            try:
                tx_raw = await loop.run_in_executor(None, lambda: self.perform_snmpwalk(tx_oid)) if tx_oid else []
                rx_raw = await loop.run_in_executor(None, lambda: self.perform_snmpwalk(rx_oid)) if rx_oid else []
                
                self.logger.info(f"Port {port_index} TX_raw: {tx_raw}, RX_raw: {rx_raw}")

                tx_val = self.extract_value(tx_raw)
                rx_val = self.extract_value(rx_raw)
                
                if tx_val is None and rx_val is None:
                    continue

                parsed_tx, parsed_rx = self.parse_signals(tx_val, rx_val)
                
                vendor_val = None
                part_val = None
                if vendor_oid or part_oid:
                    vendor_raw = await loop.run_in_executor(None, lambda: self.perform_snmpwalk(vendor_oid)) if vendor_oid else []
                    part_raw = await loop.run_in_executor(None, lambda: self.perform_snmpwalk(part_oid)) if part_oid else []
                    vendor_val = self.extract_value(vendor_raw)
                    part_val = self.extract_value(part_raw)

                # Update DevicePort
                from django.utils import timezone
                now = timezone.now()
                port_defaults = {
                    'name': iface.if_name or f"Port {port_index}",
                    'alias': iface.if_alias or '',
                    'description': '',
                    'speed': 1000,
                    'duplex': 1,
                    'admin': 1,
                    'oper': 1,
                    'lastchange': 0,
                    'discards_in': 0,
                    'discards_out': 0,
                    'mac_count': 0,
                    'pvid': 0,
                    'port_tagged': '',
                    'port_untagged': '',
                    'data': now,
                    'oct_in': 0,
                    'oct_out': 0,
                }
                
                port_obj, created = await loop.run_in_executor(None, lambda: DevicePort.objects.get_or_create(
                    managed_device=switch, port=port_index,
                    defaults=port_defaults
                ))
                port_obj.tx_signal = parsed_tx
                port_obj.rx_signal = parsed_rx
                port_obj.sfp_vendor = vendor_val
                port_obj.part_number = part_val
                await loop.run_in_executor(None, port_obj.save)
                
                if first_signals is None:
                    first_signals = (parsed_tx, parsed_rx, vendor_val, part_val)
                
            except Exception as e:
                self.logger.error(f"Error updating port {port_index} on {switch.hostname}: {e}")

        if first_signals:
            switch.tx_signal, switch.rx_signal, switch.sfp_vendor, switch.part_number = first_signals
            await loop.run_in_executor(None, switch.save)

    def parse_signals(self, tx_val, rx_val):
        parsed_tx = None
        parsed_rx = None
        try:
            if '3500' in self.model or 'GS3700' in self.model or 'MGS3520-28' in self.model:
                parsed_tx = round(float(tx_val), 2) / 100.0 if tx_val is not None else None
                parsed_rx = round(float(rx_val), 2) / 100.0 if rx_val is not None else None
            elif '3328' in self.model or 'T2600G' in self.model:
                parsed_tx = round(mw_to_dbm(float(tx_val)), 2) if tx_val is not None else None
                parsed_rx = round(mw_to_dbm(float(rx_val)), 2) if rx_val is not None else None
            elif 'SNR' in self.model:
                parsed_tx = round(float(tx_val), 2) if tx_val is not None else None
                parsed_rx = round(float(rx_val), 2) if rx_val is not None else None
            else:
                parsed_tx = round(float(tx_val), 2) / 1000.0 if tx_val is not None else None
                parsed_rx = round(float(rx_val), 2) / 1000.0 if rx_val is not None else None
        except (ValueError, TypeError):
            pass
        return parsed_tx, parsed_rx
        # loop.close()
        
    def update_switch_data(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.update_switch_data_async())
        # loop.close()

    def extract_value(self, snmp_response):
        if snmp_response and len(snmp_response) > 0:
            value_str = snmp_response[0].split('=')[-1].strip()
            return value_str if value_str != 'None' else None
        return None



class Command(BaseCommand):
    help = 'Update device optical data'

    def handle(self, *args, **options):
        snmp_community = settings.SNMP_DEFAULT_COMMUNITY_RO
        selected_switches = Device.objects.filter(status=True).order_by('-pk')
        for selected_switch in selected_switches:
            snmp_updater = SNMPUpdater(selected_switch, snmp_community)
            snmp_updater.update_switch_data()
