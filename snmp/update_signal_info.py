from pysnmp.hlapi import *
import math
from django.core.paginator import Paginator

def mw_to_dbm(mw):
    if mw > 0:
        mw /= 1000
        dbm = 10 * math.log10(mw)
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
        elif self.model == 'GS3700-24HP':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.25',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.28',
            )
        elif self.model == 'MES1124':
            return (
                'iso.3.6.1.4.1.89.90.1.2.1.3.49.8',
                'iso.3.6.1.4.1.89.90.1.2.1.3.49.9',
                'iso.3.6.1.4.1.35265.1.23.53.1.1.1.5',
                '',
            )
        elif self.model == 'MGS3520-28':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.25',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.25',
            )
        elif self.model == 'SNR-S2985G-24TC':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.25',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.25',
                '',
                '',

            )
        elif self.model == 'SNR-S2985G-8T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.9',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.9',
                '',
                '',
            )
        elif self.model == 'SNR-S2982G-24T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.25',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.25',
                '',
                '',
            )
        elif self.model == 'T2600G-28TS':
            return (
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.5.49177',
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.6.49177',
                '',
                '',
            )
        elif self.model == 'Quidway S3328TP-SI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.67240014',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.67240014',
                '',
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
                    continue
                if varBinds:
                    for varBind in varBinds:
                        snmp_response.append(str(varBind))
            return snmp_response
        except TimeoutError:
            return []
        except Exception as e:
            return []

    def update_switch_data(self):
        TX_SIGNAL_raw = self.perform_snmpwalk(self.TX_SIGNAL_OID)
        RX_SIGNAL_raw = self.perform_snmpwalk(self.RX_SIGNAL_OID)

        if TX_SIGNAL_raw is not None and RX_SIGNAL_raw is not None:
            TX_SIGNAL = self.extract_value(TX_SIGNAL_raw)
            RX_SIGNAL = self.extract_value(RX_SIGNAL_raw)
        else:
            TX_SIGNAL = None
            RX_SIGNAL = None

        if self.SFP_VENDOR_OID and self.PART_NUMBER_OID is not None:
            SFP_VENDOR_raw = self.perform_snmpwalk(self.SFP_VENDOR_OID)
            PART_NUMBER_raw = self.perform_snmpwalk(self.PART_NUMBER_OID)
            SFP_VENDOR = self.extract_value(SFP_VENDOR_raw)
            PART_NUMBER = self.extract_value(PART_NUMBER_raw)
        else:
            SFP_VENDOR = None
            PART_NUMBER = None

        switch = self.selected_switch
        try:
            if '3500' in self.model or 'GS3700' in self.model or 'MGS3520-28' in self.model:
                switch.tx_signal = round(float(TX_SIGNAL), 2) / 100.0 if TX_SIGNAL is not None else None
                switch.rx_signal = round(float(RX_SIGNAL), 2) / 100.0 if RX_SIGNAL is not None else None

            elif 'Quidway' in self.model or 'T2600G' in self.model:
                Tx_SIGNAL = mw_to_dbm(float(TX_SIGNAL))
                Rx_SIGNAL = mw_to_dbm(float(RX_SIGNAL))
                switch.tx_signal = round(Tx_SIGNAL, 2)
                switch.rx_signal = round(Rx_SIGNAL, 2)

            elif 'SNR' in self.model:
                switch.tx_signal = round(float(TX_SIGNAL), 2)
                switch.rx_signal = round(float(RX_SIGNAL), 2)

            else:
                switch.tx_signal = round(float(TX_SIGNAL), 2) / 1000.0 if TX_SIGNAL is not None else None
                switch.rx_signal = round(float(RX_SIGNAL), 2) / 1000.0 if RX_SIGNAL is not None else None

        except (ValueError, TypeError):
            switch.tx_signal = None
            switch.rx_signal = None

        switch.sfp_vendor = SFP_VENDOR if SFP_VENDOR is not None else None
        switch.part_number = PART_NUMBER if PART_NUMBER is not None else None

        try:
            switch.save()
        except Exception as e:
            pass

    def extract_value(self, snmp_response):
        if snmp_response and len(snmp_response) > 0:
            value_str = snmp_response[0].split('=')[-1].strip()
            return value_str if value_str != 'None' else None
        return None