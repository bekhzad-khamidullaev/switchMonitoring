import nmap
import asyncio
import logging
from ipaddress import IPv4Network
from django.core.management.base import BaseCommand
from django.core.management import call_command
from snmp.models import Switch, SwitchModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP DISCOVERY")

class Command(BaseCommand):
    help = 'Auto-discover switches within multiple /25 subnets of 10.101.0.0/16 range using nmap'

    def check_host_reachability(self, ip_address):
        try:
            nm = nmap.PortScanner()
            nm_args = f'-sn {ip_address}'
            nm.scan(hosts=ip_address, arguments=nm_args)
            return nm[ip_address].state() == 'up'
        except Exception as e:
            logger.error(f"Error while checking host {ip_address} reachability: {e}")
            return False

    async def handle_subnet(self, subnet, models):
        hosts = [str(host) for host in list(subnet.hosts())[1:]]
        tasks = []
        for ip_address in hosts:
            is_reachable = self.check_host_reachability(ip_address)

            if is_reachable:
                switch, created = Switch.objects.get_or_create(device_ip=ip_address)

                logger.info(f"Processing switch at IP: {ip_address}")

                tasks.append(self.perform_snmp_operations(switch, models))
            else:
                logger.warning(f"Host {ip_address} is not reachable.")

        await asyncio.gather(*tasks)

    async def process_subnets(self):
        main_subnet = IPv4Network('10.101.0.0/16')
        subnets = list(main_subnet.subnets(new_prefix=25))
        models = SwitchModel.objects.all()

        tasks = []
        for subnet in subnets:
            tasks.append(self.handle_subnet(subnet, models))

        await asyncio.gather(*tasks)

    def handle(self, *args, **options):
        logger.info("Starting SNMP discovery process...")
        asyncio.run(self.process_subnets())

def main():
    call_command('subnet_discovery')

if __name__ == "__main__":
    main()