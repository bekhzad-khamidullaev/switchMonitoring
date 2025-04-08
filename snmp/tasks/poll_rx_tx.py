from celery import shared_task
from snmp.snmp_client import snmp_get
from snmp.models import SwitchPort, SwitchPortStats
import logging

logger = logging.getLogger("RXTX POLL")

@shared_task
def poll_port_traffic():
    for port in SwitchPort.objects.select_related('switch'):
        ip = port.switch.ip
        community = port.switch.snmp_community_ro or "public"
        index = port.port_index

        try:
            in_octets = snmp_get(ip, community, "IF-MIB", "ifInOctets", index)
            out_octets = snmp_get(ip, community, "IF-MIB", "ifOutOctets", index)
            rx_signal = snmp_get(ip, community, "IF-MIB", "ifInUcastPkts", index)
            tx_signal = snmp_get(ip, community, "IF-MIB", "ifOutUcastPkts", index)

            if in_octets and out_octets:
                stats = SwitchPortStats.objects.create(
                    port=port,
                    octets_in=int(in_octets),
                    octets_out=int(out_octets),
                    rx_signal=rx_signal,
                    tx_signal=tx_signal,
                )
                logger.info(f"Saved RX/TX for port {port} on {ip}")
        except Exception as e:
            logger.warning(f"Polling error {port}: {e}")
