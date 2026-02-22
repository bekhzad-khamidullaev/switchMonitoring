from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from snmp.models import Device, DevicePort, Mac


class MacIpSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="search_user", password="p1")
        self.device = Device.objects.create(hostname="sw-edge-01", ip="10.0.0.10")
        self.port = DevicePort.objects.create(
            managed_device=self.device,
            port=1,
            description="uplink",
            speed=1000,
            duplex=2,
            admin=1,
            oper=1,
            lastchange=0,
            discards_in=0,
            discards_out=0,
            mac_count=1,
            pvid=10,
            port_tagged="",
            port_untagged="10",
            data=timezone.now(),
            name="Gi0/1",
            alias="",
            oct_in=0,
            oct_out=0,
        )
        self.mac = Mac.objects.create(
            managed_device=self.device,
            port=self.port,
            mac="00:11:22:33:44:55",
            vlan=10,
            ip="10.0.0.50",
        )

    def test_requires_login(self):
        response = self.client.get(reverse("mac_ip_search_report"))
        self.assertEqual(response.status_code, 302)

    def test_requires_view_permission(self):
        self.client.login(username="search_user", password="p1")
        response = self.client.get(reverse("mac_ip_search_report"))
        self.assertEqual(response.status_code, 403)

    def test_get_page_returns_rows_when_query_is_valid(self):
        perm = Permission.objects.get(codename="view_device")
        self.user.user_permissions.add(perm)
        self.client.login(username="search_user", password="p1")

        response = self.client.get(reverse("mac_ip_search_report"), {"q": "00:11"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "00:11:22:33:44:55")
        self.assertContains(response, "sw-edge-01")

    def test_post_datatables_payload_returns_json(self):
        perm = Permission.objects.get(codename="view_device")
        self.user.user_permissions.add(perm)
        self.client.login(username="search_user", password="p1")

        response = self.client.post(
            reverse("mac_ip_search_report"),
            data={
                "draw": "2",
                "search": "00:11",
                "order[0][column]": "4",
                "order[0][dir]": "desc",
                "start": "0",
                "length": "25",
                "filter_ip": "false",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["draw"], 2)
        self.assertEqual(payload["recordsFiltered"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["mac"], "00:11:22:33:44:55")
