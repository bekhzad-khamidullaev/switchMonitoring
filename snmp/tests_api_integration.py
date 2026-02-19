from unittest.mock import patch

from django.contrib.auth.models import ContentType, Permission, User
from django.test import TestCase

from snmp.models import (
    Branch,
    Device,
    DeviceProfile,
    Interface,
    MetricBinding,
    MetricDefinition,
    MetricSample,
    MetricSubscription,
)
from snmp.services.polling.poller import poll_device_metrics


class ApiIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="api_user", password="p1")
        self.client.login(username="api_user", password="p1")
        view_device_perm = Permission.objects.get(codename="view_device")
        add_device_perm = Permission.objects.get(codename="add_device")
        change_device_perm = Permission.objects.get(codename="change_device")
        self.user.user_permissions.add(view_device_perm, add_device_perm, change_device_perm)

    @patch("snmp.services.discovery.pipeline.read_base_snmp")
    @patch("snmp.services.polling.poller.snmp_get_many")
    def test_onboard_discover_subscribe_polling_sample_flow(self, mock_get_many, mock_read_base):
        onboard_response = self.client.post(
            "/snmp/api/devices/onboard",
            data={"ip": "10.10.10.10"},
            content_type="application/json",
        )
        self.assertEqual(onboard_response.status_code, 201)
        device_id = onboard_response.json()["id"]

        profile = DeviceProfile.objects.create(
            vendor="huawei",
            model_pattern=r"S33\d{2}",
            firmware_pattern="",
            priority=10,
            active=True,
        )

        mock_read_base.return_value = {
            "sys_object_id": "1.3.6.1.4.1.2011.2.23.134",
            "sys_descr": "Huawei S3352P-EI-24S version V200R001C00SPC300",
            "interfaces": [
                {
                    "if_index": 1,
                    "if_name": "GigabitEthernet0/0/1",
                    "if_alias": "uplink",
                    "if_type": "117",
                    "is_optical": True,
                    "admin_up": True,
                    "oper_up": True,
                }
            ],
        }

        discover_response = self.client.post(
            f"/snmp/api/devices/{device_id}/discover",
            data={"community": "public"},
            content_type="application/json",
        )
        self.assertEqual(discover_response.status_code, 200)
        self.assertEqual(discover_response.json()["interfaces_count"], 1)

        device = Device.objects.get(pk=device_id)
        device.refresh_from_db()
        self.assertEqual(device.vendor, "huawei")
        self.assertEqual(device.profile_id, profile.id)

        interface = Interface.objects.get(device=device, if_index=1)
        metric = MetricDefinition.objects.create(
            key="rx_power_dbm",
            title="RX Power",
            unit="dBm",
            value_type=MetricDefinition.ValueType.FLOAT,
        )
        binding = MetricBinding.objects.create(
            profile=profile,
            metric=metric,
            oid_template="1.3.6.1.4.1.9999.1.1.{if_index}",
            index_strategy=MetricBinding.IndexStrategy.IF_INDEX,
            converter=MetricBinding.Converter.DIV100,
            binding_params={},
        )
        subscription = MetricSubscription.objects.create(
            device=device,
            interface=interface,
            metric=metric,
            binding=binding,
            enabled=True,
            poll_interval_sec=60,
        )

        oid = "1.3.6.1.4.1.9999.1.1.1"
        mock_get_many.return_value = {oid: "-1234"}
        saved = poll_device_metrics(device.id)
        self.assertEqual(saved, 1)

        sample = MetricSample.objects.filter(subscription=subscription).order_by("-id").first()
        self.assertIsNotNone(sample)
        self.assertEqual(sample.quality, MetricSample.Quality.GOOD)
        self.assertAlmostEqual(sample.value_float, -12.34, places=2)

    def test_api_device_metrics_respects_branch_permissions(self):
        branch = Branch.objects.create(name="North Zone")
        device = Device.objects.create(hostname="sw-1", ip="10.0.0.2", branch=branch)

        denied = self.client.get(f"/snmp/api/devices/{device.id}/metrics")
        self.assertEqual(denied.status_code, 403)

        content_type = ContentType.objects.get_for_model(Branch)
        branch_perm, _ = Permission.objects.update_or_create(
            codename="view_north_zone",
            content_type=content_type,
            defaults={"name": "Can view devices in North Zone"},
        )
        self.user.user_permissions.add(branch_perm)

        allowed = self.client.get(f"/snmp/api/devices/{device.id}/metrics")
        self.assertEqual(allowed.status_code, 200)
