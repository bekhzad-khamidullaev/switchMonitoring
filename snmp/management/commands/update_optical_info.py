# from background_task import background
from django.core.management.base import BaseCommand
from snmp.models import Switch
from pysnmp.hlapi import *
import logging, math


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")

def mw_to_dbm(mw):
    if mw > 0:
        mw /= 1000
        dbm = 10 * math.log10(mw)
        logger.info(f":::::::Input is={mw}, Output is={dbm}:::::::")
        return dbm
    else:
        return None
        
class SNMPUpdater:
    def __init__(self, selected_switch, snmp_community):
        self.selected_switch = selected_switch
        if selected_switch.device_model:
            self.model = selected_switch.device_model.device_model
        else:
            self.model = None
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
        elif self.model == 'Quidway S3328TP-EI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.67240014',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.67240014',
                '',
                '',
            )
        else:
            return (None, None, None, None)

    # def perform_snmpwalk(self, oid):
    #     try:
    #         snmp_walk = getCmd(
    #             SnmpEngine(),
    #             CommunityData(self.snmp_community),
    #             UdpTransportTarget((self.device_ip, 161), timeout=2, retries=2),
    #             ContextData(),
    #             ObjectType(ObjectIdentity(oid)),
    #         )

    #         snmp_response = []
    #         for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
    #             if errorIndication:
    #                 self.logger.error(f"SNMP error: {errorIndication}")
    #                 continue
    #             for varBind in varBinds:
    #                 snmp_response.append(str(varBind))
    #         return snmp_response
    #     except TimeoutError:
    #         self.logger.warning(f"SNMP timeout for IP address: {self.device_ip}")
    #         return []
    #     except Exception as e:
    #         self.logger.error(f"Error during SNMP walk: {e}")
    #         return []
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
                if varBinds:
                    for varBind in varBinds:
                        snmp_response.append(str(varBind))
            return snmp_response
        except TimeoutError:
            self.logger.warning(f"SNMP timeout for IP address: {self.device_ip}")
            return []
        except Exception as e:
            self.logger.error(f"Error during SNMP walk: {e}")
            return []


    # def update_switch_data(self):
    #     TX_SIGNAL_raw = self.perform_snmpwalk(self.TX_SIGNAL_OID)
    #     RX_SIGNAL_raw = self.perform_snmpwalk(self.RX_SIGNAL_OID)

    #     self.logger.info(f"TX_SIGNAL_raw: {TX_SIGNAL_raw}")
    #     self.logger.info(f"RX_SIGNAL_raw: {RX_SIGNAL_raw}")

    #     TX_SIGNAL = self.extract_value(TX_SIGNAL_raw)
    #     RX_SIGNAL = self.extract_value(RX_SIGNAL_raw)

    #     self.logger.info(f"TX_SIGNAL: {TX_SIGNAL}")
    #     self.logger.info(f"RX_SIGNAL: {RX_SIGNAL}")
        
    #     if self.SFP_VENDOR_OID and self.PART_NUMBER_OID is not None:
    #         SFP_VENDOR = self.extract_value(self.perform_snmpwalk(self.SFP_VENDOR_OID))
    #         PART_NUMBER = self.extract_value(self.perform_snmpwalk(self.PART_NUMBER_OID))
    #     else:
    #         SFP_VENDOR = None
    #         PART_NUMBER = None


    #     switch = self.selected_switch
    #     try:
    #         if '3500' in self.model:
    #             switch.tx_signal = float(TX_SIGNAL) / 100.0 if TX_SIGNAL is not None else None
    #             switch.rx_signal = float(RX_SIGNAL) / 100.0 if RX_SIGNAL is not None else None
                
    #         elif 'Quidway' in self.model:
    #             Tx_SIGNAL = mw_to_dbm(float(TX_SIGNAL) / -1000.0)
    #             Rx_SIGNAL = mw_to_dbm(float(RX_SIGNAL) / -1000.0)
    #             logger.info(f":::::::TX SIGNAL={Tx_SIGNAL}, RX SIGNAL={Rx_SIGNAL}:::::::")
           
    #             switch.tx_signal = Tx_SIGNAL
    #             switch.rx_signal = Rx_SIGNAL

    #         else:
    #             switch.tx_signal = float(TX_SIGNAL) / 1000.0 if TX_SIGNAL is not None else None
    #             switch.rx_signal = float(RX_SIGNAL) / 1000.0 if RX_SIGNAL is not None else None
                
    #     except (ValueError, TypeError):
    #         self.logger.error("Invalid values for TX_SIGNAL or RX_SIGNAL")
            
    #     switch.sfp_vendor = SFP_VENDOR if SFP_VENDOR is not None else None
    #     switch.part_number = PART_NUMBER if PART_NUMBER is not None else None

    #     switch.save()

    def update_switch_data(self):
        TX_SIGNAL_raw = self.perform_snmpwalk(self.TX_SIGNAL_OID)
        RX_SIGNAL_raw = self.perform_snmpwalk(self.RX_SIGNAL_OID)

        self.logger.info(f"TX_SIGNAL_raw: {TX_SIGNAL_raw}")
        self.logger.info(f"RX_SIGNAL_raw: {RX_SIGNAL_raw}")
        if TX_SIGNAL_raw is not None and RX_SIGNAL_raw is not None:
            TX_SIGNAL = self.extract_value(TX_SIGNAL_raw)
            RX_SIGNAL = self.extract_value(RX_SIGNAL_raw)
        else:
            print("TX_SIGNAL_raw or RX_SIGNAL_raw is None. Skipping this entry.")
            TX_SIGNAL = None
            RX_SIGNAL = None

        self.logger.info(f"TX_SIGNAL: {TX_SIGNAL}")
        self.logger.info(f"RX_SIGNAL: {RX_SIGNAL}")

        if self.SFP_VENDOR_OID and self.PART_NUMBER_OID is not None:
            SFP_VENDOR_raw = self.perform_snmpwalk(self.SFP_VENDOR_OID)
            PART_NUMBER_raw = self.perform_snmpwalk(self.PART_NUMBER_OID)
            self.logger.info(f"SFP_VENDOR_raw: {SFP_VENDOR_raw}")
            self.logger.info(f"PART_NUMBER_raw: {PART_NUMBER_raw}")
            SFP_VENDOR = self.extract_value(SFP_VENDOR_raw)
            PART_NUMBER = self.extract_value(PART_NUMBER_raw)
        else:
            SFP_VENDOR = None
            PART_NUMBER = None

        switch = self.selected_switch
        try:
            if '3500' in self.model:
                switch.tx_signal = float(TX_SIGNAL) / 100.0 if TX_SIGNAL is not None else None
                switch.rx_signal = float(RX_SIGNAL) / 100.0 if RX_SIGNAL is not None else None

            elif 'Quidway' in self.model:
                self.logger.info(f":::::::TX SIGNAL BEFORE={TX_SIGNAL}, RX SIGNAL BEFORE={RX_SIGNAL}:::::::")
                Tx_SIGNAL = mw_to_dbm(float(TX_SIGNAL))
                Rx_SIGNAL = mw_to_dbm(float(RX_SIGNAL))
                self.logger.info(f":::::::TX SIGNAL={Tx_SIGNAL}, RX SIGNAL={Rx_SIGNAL}:::::::")
                switch.tx_signal = round(Tx_SIGNAL, 2)
                switch.rx_signal = round(Rx_SIGNAL, 2)

            else:
                switch.tx_signal = float(TX_SIGNAL) / 1000.0 if TX_SIGNAL is not None else None
                switch.rx_signal = float(RX_SIGNAL) / 1000.0 if RX_SIGNAL is not None else None

        except (ValueError, TypeError):
            self.logger.warning("Invalid values for TX_SIGNAL or RX_SIGNAL")
            switch.tx_signal = None
            switch.rx_signal = None

        switch.sfp_vendor = SFP_VENDOR if SFP_VENDOR is not None else None
        switch.part_number = PART_NUMBER if PART_NUMBER is not None else None

        switch.save()


    def extract_value(self, snmp_response):
        if snmp_response and len(snmp_response) > 0:
            value_str = snmp_response[0].split('=')[-1].strip()
            return value_str if value_str != 'None' else None
        return None



class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        while True:
            snmp_community = "snmp2netread"
            selected_switches = Switch.objects.filter(status=True).order_by('pk')
            # selected_switches = Switch.objects.filter(device_model__icontains='Quidway').order_by('pk')
            for selected_switch in selected_switches:
                snmp_updater = SNMPUpdater(selected_switch, snmp_community)
                snmp_updater.update_switch_data()
