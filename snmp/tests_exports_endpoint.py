from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from snmp.models import Branch, Device, DevicePort, Mac


class EndpointActivityReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin_endpoint',
            email='admin@example.com',
            password='p1',
        )
        self.client.login(username='admin_endpoint', password='p1')
        self.group = Branch.objects.create(name='HQ')
        self.device = Device.objects.create(hostname='sw-hq-01', ip='10.10.0.1', group=self.group)

        self.printer_port = DevicePort.objects.create(
            id=10,
            managed_device=self.device,
            port=10,
            description='Office printer room',
            speed=1000,
            duplex=2,
            admin=1,
            oper=1,
            lastchange=0,
            discards_in=0,
            discards_out=0,
            mac_count=1,
            pvid=10,
            port_tagged='',
            port_untagged='10',
            data=timezone.now(),
            name='Gi0/10',
            alias='printer-port',
            oct_in=0,
            oct_out=0,
        )
        self.camera_port = DevicePort.objects.create(
            id=11,
            managed_device=self.device,
            port=11,
            description='Hallway camera uplink',
            speed=1000,
            duplex=2,
            admin=1,
            oper=1,
            lastchange=0,
            discards_in=0,
            discards_out=0,
            mac_count=1,
            pvid=20,
            port_tagged='',
            port_untagged='20',
            data=timezone.now(),
            name='Gi0/11',
            alias='camera-port',
            oct_in=0,
            oct_out=0,
        )
        Mac.objects.create(
            managed_device=self.device,
            port=self.printer_port,
            mac='00:aa:bb:cc:dd:10',
            vlan=10,
            ip='10.10.0.210',
        )
        Mac.objects.create(
            managed_device=self.device,
            port=self.camera_port,
            mac='00:aa:bb:cc:dd:11',
            vlan=20,
            ip='10.10.0.211',
        )

    def test_printer_endpoint_report_filters_rows(self):
        response = self.client.get(reverse('endpoint_activity_report', kwargs={'endpoint_type': 'printer'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'printer-port')
        self.assertNotContains(response, 'camera-port')

    def test_unknown_endpoint_type_returns_404(self):
        response = self.client.get(reverse('endpoint_activity_report', kwargs={'endpoint_type': 'unknown'}))
        self.assertEqual(response.status_code, 404)
