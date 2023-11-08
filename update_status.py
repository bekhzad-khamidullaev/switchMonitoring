import os
import ping3
import logging
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()

from snmp.models import Switch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")

def update_switch_status_main():
    ip_addresses = Switch.objects.values_list('device_ip', flat=True)
    for ip in ip_addresses:
        host_alive = ping3.ping(ip)
        logger.info(host_alive)
        if host_alive is not None:
            switches = Switch.objects.filter(device_ip=ip)
            for switch in switches:
                switch.status = True
                switch.save()

if __name__ == "__main__":
    update_switch_status_main()
