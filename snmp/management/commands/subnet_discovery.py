import nmap
import logging
from ipaddress import IPv4Network
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel, Ats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP DISCOVERY")

class Command(BaseCommand):
    help = 'Auto-discover switches within multiple /25 subnets of 10.101.0.0/16 range using nmap'

    def check_host_reachability(self, ip):
        try:
            nm = nmap.PortScanner()
            nm_args = f'-sn {ip}'
            nm.scan(hosts=ip, arguments=nm_args)
            return nm[ip].state() == 'up'
        except Exception as e:
            logger.error(f"Error while checking host {ip} reachability: {e}")
            return False

    def handle_subnet(self, subnet, models):
        hosts = [str(host) for host in list(subnet.hosts())[1:]]
        for ip_address in hosts:
            is_reachable = self.check_host_reachability(ip_address)
            if is_reachable:
                switch, created = Switch.objects.get_or_create(ip=ip_address, snmp_community_ro='eriwpirt', snmp_community_rw='pirteriw')
                logger.info(f"Processing switch at IP: {ip_address}")
                switch.save()
                if switch.save:
                    logger.info(f"Save switch with IP: {ip_address}")
            else:
                logger.warning(f"Host {ip_address} is not reachable.")

    def process_subnets(self):
        ats_subnets = Ats.objects.values_list('subnet', flat=True).order_by('-pk')
        models = SwitchModel.objects.all()
        # subnet_str = "10.47.64.0/19"
        # subnet = IPv4Network(subnet_str)
        # print(f'Subnet: {subnet}')
        # subnets = list(subnet.subnets(new_prefix=25))
        # for sub in subnets:
        #     print(f'Converted subnet: {sub}')
        #     self.handle_subnet(sub, models)
        for subnet_str in ats_subnets:
            subnet = IPv4Network(subnet_str)
            # Change the new_prefix to a value larger than the original prefix (e.g., 26)
            subnets = list(subnet.subnets(new_prefix=25))
            for sub in subnets:
                self.handle_subnet(sub, models)


    def handle(self, *args, **options):
        logger.info("Starting SNMP discovery process...")
        self.process_subnets()

def main():
    Command().handle()

if __name__ == "__main__":
    main()
