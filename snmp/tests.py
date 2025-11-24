from django.urls import reverse
from django.test import TestCase
from .models import Switch, SwitchModel, SwitchesNeighbors, Vendor


class NetworkMapDataTest(TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name="Vendor")
        model = SwitchModel.objects.create(vendor=vendor, device_model="M1")
        self.sw1 = Switch.objects.create(model=model, hostname="sw1", switch_mac="aa:bb:cc:dd:ee:01")
        self.sw2 = Switch.objects.create(model=model, hostname="sw2", switch_mac="aa:bb:cc:dd:ee:02")
        SwitchesNeighbors.objects.create(mac1=self.sw1.switch_mac, port1=1, mac2=self.sw2.switch_mac, port2=1)

    def test_network_map_data_structure(self):
        response = self.client.get(reverse('network_map_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('nodes', data)
        self.assertIn('edges', data)
        self.assertEqual(len(data['nodes']), 2)
        self.assertEqual(len(data['edges']), 1)
