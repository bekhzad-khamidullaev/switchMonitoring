import ping3
from django.core.management.base import BaseCommand
from snmp.models import Switch
from snmp.models import Vendor
from snmp.models import SwitchModel
from easysnmp import Session

class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        # Step 2: Query the snmp_switch table to select IP addresses
        ip_addresses = Switch.objects.values_list('device_ip', flat=True)

        for ip in ip_addresses:
            # Step 3: Check if the host is alive using ping3
            host_alive = ping3.ping(ip)

            if host_alive is not None:
                # The host is reachable

                # Step 4: Update the status field to True
                switch = Switch.objects.get(device_ip=ip)
                switch.status = True
                switch.save()

                # Step 5: Select IP addresses where status is True
                selected_switches = Switch.objects.filter(status=True)

                for selected_switch in selected_switches:
                    device_type = selected_switch.device_type
                    if device_type:
                        device_model = device_type.device_model
                        if device_model:
                            vendor_name = device_model.vendor.name

                    # Step 6: Send an SNMP GET request with the OID '1.3.6.1.2.1.1.1.0' to the selected IP address
                    snmp_response = perform_snmpget(selected_switch.device_ip, '1.3.6.1.2.1.1.1.0')

                    # Step 7: Check the response for containing the name from the snmp_vendor table
                    vendor_name = selected_switch.device_type.device_model.vendor.name
                    if vendor_name in snmp_response:
                        # Step 8: Check if the response contains the snmp_switchmodel device_model field
                        device_model_name = selected_switch.device_type.device_model.device_model
                        if device_model_name in snmp_response:
                            # Step 9: Update device_model_id, device_model_local, and device_hostname
                            selected_switch.device_model_id = SwitchModel.objects.get(device_model=device_model_name).pk
                            selected_switch.device_model_local = device_model_name
                            selected_switch.device_hostname = device_model_name
                            selected_switch.save()

def perform_snmpget(device_ip, oid):
    try:
        # Create an SNMP session
        session = Session(hostname=device_ip, community='public', version=2)  # Replace 'public' with your community string

        # Perform an SNMP GET operation
        response = session.get(oid)

        if response.error:
            print(f'Error while performing SNMP GET for OID {oid}: {response.error}')
            return None
        else:
            return response.value
    except Exception as e:
        print(f'An error occurred while performing SNMP GET: {str(e)}')
        return None
