# from background_task import background
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel, Vendor
from pysnmp.hlapi import *
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")

class SNMPUpdater:
    def __init__(self, selected_switch, snmp_community):
        self.selected_switch = selected_switch
        self.model = selected_switch.device_model_local
        self.device_ip = selected_switch.device_ip
        self.snmp_community = snmp_community
        self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID = self.get_snmp_oids()
        self.logger = logging.getLogger("SNMP RESPONSE")

    def get_snmp_oids(self):
        if self.model == 'MES2428':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.25.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.25.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.25',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.25',
            )
        elif self.model == 'MES2408':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.9.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.9.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.9',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.9',
            )
        elif self.model == 'MES3500-24':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.25.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.25.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.25',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.25',
            )
        elif self.model == 'MES3500-10':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.9.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.9.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.9',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.9',
            )
        elif self.model == 'MES1124':
            return (
                'iso.3.6.1.4.1.89.90.1.2.1.3.49.8',
                'iso.3.6.1.4.1.89.90.1.2.1.3.49.9',
                'iso.3.6.1.4.1.35265.1.23.53.1.1.1.5',
                '',
            )
        
        else:
            return (None, None, None, None)

    def perform_snmpwalk(self, oid):
        try:
            snmp_walk = getCmd(
                SnmpEngine(),
                CommunityData(self.snmp_community),
                UdpTransportTarget((self.device_ip, 161), timeout=2, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )

            snmp_response = []
            for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
                if errorIndication:
                    self.logger.error(f"SNMP error: {errorIndication}")
                    continue
                for varBind in varBinds:
                    snmp_response.append(str(varBind))
            return snmp_response
        except TimeoutError:
            self.logger.warning(f"SNMP timeout for IP address: {self.device_ip}")
            return []
        except Exception as e:
            self.logger.error(f"Error during SNMP walk: {e}")
            return []

    def update_switch_data(self):
        self.logger.info(
            "TX_SIGNAL_OID: %s, RX_SIGNAL_OID: %s, SFP_VENDOR_OID: %s, PART_NUMBER_OID: %s",
            self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID,
        )

        TX_SIGNAL = self.extract_value(self.perform_snmpwalk(self.TX_SIGNAL_OID))
        RX_SIGNAL = self.extract_value(self.perform_snmpwalk(self.RX_SIGNAL_OID))
        SFP_VENDOR = self.extract_value(self.perform_snmpwalk(self.SFP_VENDOR_OID))
        PART_NUMBER = self.extract_value(self.perform_snmpwalk(self.PART_NUMBER_OID))

        # Assuming Switch instance has been created and passed to SNMPUpdater
        switch_instance = self.selected_switch

        # Handle the case where TX_SIGNAL and RX_SIGNAL are not valid floats
        try:
            if '3500' in self.model:
                switch_instance.tx_signal = float(TX_SIGNAL) / 100.0 if TX_SIGNAL is not None else None
                switch_instance.rx_signal = float(RX_SIGNAL) / 100.0 if RX_SIGNAL is not None else None
            else:
                switch_instance.tx_signal = float(TX_SIGNAL) / 1000.0 if TX_SIGNAL is not None else None
                switch_instance.rx_signal = float(RX_SIGNAL) / 1000.0 if RX_SIGNAL is not None else None
        except (ValueError, TypeError):
            self.logger.error("Invalid values for TX_SIGNAL or RX_SIGNAL")
        switch_instance.sfp_vendor = SFP_VENDOR
        switch_instance.part_number = PART_NUMBER

        # Save the Switch model instance
        switch_instance.save()

        response = [TX_SIGNAL, RX_SIGNAL, SFP_VENDOR, PART_NUMBER]
        self.logger.info(response)

    def extract_value(self, snmp_response):
        if snmp_response and len(snmp_response) > 0:
            value_str = snmp_response[0].split('=')[-1].strip()
            return value_str if value_str != 'None' else None
        return None


class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        snmp_community = "snmp2netread"  # Replace with your desired community string
        selected_switches = Switch.objects.filter(status=True)

        for selected_switch in selected_switches:
            snmp_updater = SNMPUpdater(selected_switch, snmp_community)
            
            snmp_updater.update_switch_data()
