from django.test import TestCase
from monitoring.models import Vendor, DeviceModel, Device, Interface


class DeviceModelTestCase(TestCase):
    def test_create_device(self):
        vendor = Vendor.objects.create(name='TestVendor')
        model = DeviceModel.objects.create(vendor=vendor, name='ModelX', sys_object_id='1.3.6.1.4', max_ports=2)
        device = Device.objects.create(ip='192.0.2.1', model=model)
        Interface.objects.create(device=device, index=1)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(device.interfaces.count(), 1)
