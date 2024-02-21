from django.core.paginator import Paginator
import concurrent.futures
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel
import math
from snmp.tasks import update_optical_info_task  
import asyncio
import logging
from django.db.models import ObjectDoesNotExist
from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
from snmp.models import SwitchModel

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

def process_signals(model, tx_signal, rx_signal):
    if '3500' in model or 'GS3700' in model:
        factor = 100.0
    elif 'Quidway' in model or 'T2600G' in model:
        tx_signal = mw_to_dbm(float(tx_signal))
        rx_signal = mw_to_dbm(float(rx_signal))
        factor = 1.0
    else:
        factor = 1000.0

    return round(float(tx_signal), 2) / factor if tx_signal is not None else None, \
           round(float(rx_signal), 2) / factor if rx_signal is not None else None

class SNMPUpdater:
    def __init__(self, selected_switch, snmp_community):
        self.selected_switch = selected_switch
        if selected_switch.model:
            self.model = selected_switch.model.device_model
        else:
            self.model = None
        self.device_ip = selected_switch.ip
        self.snmp_community = snmp_community
        self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID = self.get_snmp_oids()
        self.logger = logging.getLogger("SNMP RESPONSE")

    def get_snmp_oids(self):
        try:
            if self.selected_switch.model:
                switch_model = SwitchModel.objects.get(vendor=self.selected_switch.model.vendor,
                                                    device_model=self.selected_switch.model.device_model)
                return (
                    switch_model.tx_oid,
                    switch_model.rx_oid,
                    switch_model.sfp_vendor_oid,
                    switch_model.part_num_oid,
                )
            else:
                return (None, None, None, None)
        except ObjectDoesNotExist:
            return (None, None, None, None)





    async def update_switch_data_async(self):
        loop = asyncio.get_event_loop()

        TX_SIGNAL_raw = await loop.run_in_executor(None, lambda: self.perform_snmpwalk(self.TX_SIGNAL_OID))
        RX_SIGNAL_raw = await loop.run_in_executor(None, lambda: self.perform_snmpwalk(self.RX_SIGNAL_OID))

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
            switch.tx_signal, switch.rx_signal = process_signals(self.model, TX_SIGNAL, RX_SIGNAL)
        except (ValueError, TypeError):
            self.logger.warning("Invalid values for TX_SIGNAL or RX_SIGNAL")
            switch.tx_signal = None
            switch.rx_signal = None

        switch.sfp_vendor = SFP_VENDOR if SFP_VENDOR is not None else None
        switch.part_number = PART_NUMBER if PART_NUMBER is not None else None

        switch.save()
        await update_optical_info_task.delay(switch.id)

        loop.close()

class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        snmp_community = "snmp2netread"
        switches_per_page = 5
        while True:
            selected_switches = Switch.objects.filter(status=True).order_by('-pk')
            paginator = Paginator(selected_switches, switches_per_page)

            with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                futures = []

                for page_number in range(1, paginator.num_pages + 1):
                    switches_page = paginator.page(page_number)
                    for selected_switch in switches_page:
                        snmp_updater = SNMPUpdater(selected_switch, snmp_community)
                        futures.append(executor.submit(asyncio.run, snmp_updater.update_switch_data_async()))


                concurrent.futures.wait(futures, timeout=None, return_when=concurrent.futures.ALL_COMPLETED)