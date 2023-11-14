# from background_task import background
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel, Vendor
from pysnmp.hlapi import *
import logging, math, re
import telnetlib





logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")


interface_name = "GigabitEthernet0/0/1"
username = "bekhzad"
password = "adminadmin"
port = 23

def establish_telnet_connection(host, port, username, password):
    try:
        tn = telnetlib.Telnet(host, port, timeout=1)
        tn.read_until(b"Username: ", timeout=1)
        tn.write(username.encode('utf-8') + b"\n")
        tn.read_until(b"Password: ", timeout=1)
        tn.write(password.encode('utf-8') + b"\n")
        
        tn.read_until(b">", timeout=1)
        logger.info("Telnet connection established.")
        return tn
    except Exception as e:
        logger.error(f"Failed to establish Telnet connection: {str(e)}")
        return None


def send_telnet_command(tn, command):
    try:
        tn.write(command.encode('utf-8') + b"\n")
        index, match, response = tn.expect([b'[>#]'])
        response = response.decode('utf-8', errors='replace')
        if index == -1:
            logger.error(f"Failed to match the expected pattern: [>#]")
            return None
        logger.info(f'Sent command: {command}\nResponse: {response}')
        return response
    except Exception as e:
        logger.error(f"Error while sending Telnet command: {str(e)}")
        return None

def extract_transceiver_info(output, interface_name):
    transceiver_info = []

    transceiver_sections = re.findall(rf'{interface_name} transceiver information:[\s\S]*?(?=(?:\nInterface Name|$))', output)
    for section in transceiver_sections:
        info = {}
        info['Interface Name'] = re.search(r'(\S+) transceiver information:', section).group(1)
        vendor_match = re.search(r'Vendor Name\s+:(.*?)\n', section)
        rx_power_match = re.search(r'RX Power\(dBM\)\s+:(.*?)\n', section)
        tx_power_match = re.search(r'TX Power\(dBM\)\s+:(.*?)\n', section)
        info['Vendor Name'] = vendor_match.group(1).strip() if vendor_match else "N/A"
        info['RX Power (dBm)'] = rx_power_match.group(1).strip() if rx_power_match else "N/A"
        info['TX Power (dBm)'] = tx_power_match.group(1).strip() if tx_power_match else "N/A"
        transceiver_info.append(info)

    return transceiver_info


def get_required_transceiver_info(ip, port, username, password, interface_name):
    try:
        tn = establish_telnet_connection(ip, port, username, password)
        if tn:
            output = send_telnet_command(tn, f"display transceiver interface {interface_name} verbose")
            tn.write(b"quit\n")
            tn.close()

            if output:
                transceiver_info = extract_transceiver_info(output, interface_name)
                if transceiver_info:
                    return transceiver_info[0]  # Return the first element of the list as a dictionary
                else:
                    logger.error("Failed to retrieve transceiver info.")
            else:
                logger.error("Failed to retrieve transceiver info.")
        else:
            logger.error("Error: Failed to establish a Telnet connection.")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    return {}


class SNMPUpdater:
    def __init__(self, selected_switch, snmp_community):
        self.selected_switch = selected_switch
        self.model = selected_switch.device_model_local
        self.device_ip = selected_switch.device_ip
        self.snmp_community = snmp_community
        self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID = self.get_snmp_oids()
        self.logger = logging.getLogger("SNMP RESPONSE")
    
    def mw_to_dbm(mw):
        if mw > 0:
            dbm = 10 * math.log10(mw)
            return dbm
        else:
            return float('-inf')

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
        switch_instance = self.selected_switch

        self.logger.info(
            "TX_SIGNAL_OID: %s, RX_SIGNAL_OID: %s, SFP_VENDOR_OID: %s, PART_NUMBER_OID: %s",
            self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID,
        )

        result = get_required_transceiver_info(self.device_ip, port, username, password, interface_name)

        if 'TX Power (dBm)' in result:
            TX_SIGNAL = result['TX Power (dBm)']
        else:
            self.logger.error("TX Power (dBm) not found in the result dictionary.")
            TX_SIGNAL = None

        if 'RX Power (dBm)' in result:
            RX_SIGNAL = result['RX Power (dBm)']
        else:
            self.logger.error("RX Power (dBm) not found in the result dictionary.")
            RX_SIGNAL = None

        if 'Vendor Name' in result:
            SFP_VENDOR = result['Vendor Name']
        else:
            self.logger.error("Vendor Name not found in the result dictionary.")
            SFP_VENDOR = None

        # Assuming 'PART_NUMBER' is a key in the result dictionary
        PART_NUMBER = result.get('PART_NUMBER', None)

        try:
            if '3500' in self.model:
                switch_instance.tx_signal = float(TX_SIGNAL) / 100.0 if TX_SIGNAL is not None else None
                switch_instance.rx_signal = float(RX_SIGNAL) / 100.0 if RX_SIGNAL is not None else None
            elif '3328' in self.model:
                switch_instance.tx_signal = float(TX_SIGNAL)
                switch_instance.rx_signal = float(RX_SIGNAL)
            else:
                switch_instance.tx_signal = float(TX_SIGNAL) / 1000.0 if TX_SIGNAL is not None else None
                switch_instance.rx_signal = float(RX_SIGNAL) / 1000.0 if RX_SIGNAL is not None else None
        except (ValueError, TypeError):
            self.logger.error("Invalid values for TX_SIGNAL or RX_SIGNAL")

        switch_instance.sfp_vendor = SFP_VENDOR if SFP_VENDOR is not None else None
        switch_instance.part_number = PART_NUMBER if PART_NUMBER is not None else None

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
        while True:
            snmp_community = "snmp2netread"  # Replace with your desired community string
            selected_switches = Switch.objects.filter(status=True)

            for selected_switch in selected_switches:
                snmp_updater = SNMPUpdater(selected_switch, snmp_community)
                
                snmp_updater.update_switch_data()
