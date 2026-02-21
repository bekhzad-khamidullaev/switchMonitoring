from unittest.mock import patch

from django.contrib.auth.models import ContentType, Permission, User
from django.test import TestCase
from django.utils import timezone

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

    def test_api_device_metrics_supports_enabled_limit_and_offset(self):
        device = Device.objects.create(hostname="sw-10", ip="10.0.10.2")
        metric1 = MetricDefinition.objects.create(key="m_enabled_1", title="Enabled 1")
        metric2 = MetricDefinition.objects.create(key="m_disabled_1", title="Disabled 1")
        metric3 = MetricDefinition.objects.create(key="m_enabled_2", title="Enabled 2")

        MetricSubscription.objects.create(device=device, metric=metric1, enabled=True)
        MetricSubscription.objects.create(device=device, metric=metric2, enabled=False)
        MetricSubscription.objects.create(device=device, metric=metric3, enabled=True)

        response = self.client.get(
            f"/snmp/api/devices/{device.id}/metrics",
            data={"enabled": "true", "limit": 1, "offset": 1},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["enabled"], True)

    def test_api_device_timeseries_validates_if_index_and_before(self):
        device = Device.objects.create(hostname="sw-ts", ip="10.0.20.2")
        interface = Interface.objects.create(device=device, if_index=101, if_name="ge0/0/1")
        metric = MetricDefinition.objects.create(key="rx_power_dbm_ts", title="RX Power TS")
        subscription = MetricSubscription.objects.create(device=device, interface=interface, metric=metric, enabled=True)

        ts_old = timezone.now() - timezone.timedelta(minutes=5)
        ts_new = timezone.now()
        MetricSample.objects.create(subscription=subscription, ts=ts_old, value_float=-12.5, quality=MetricSample.Quality.GOOD)
        MetricSample.objects.create(subscription=subscription, ts=ts_new, value_float=-12.0, quality=MetricSample.Quality.GOOD)

        bad_if_index = self.client.get(
            f"/snmp/api/devices/{device.id}/timeseries",
            data={"if_index": "abc"},
        )
        self.assertEqual(bad_if_index.status_code, 400)

        filtered = self.client.get(
            f"/snmp/api/devices/{device.id}/timeseries",
            data={"if_index": 101, "before": ts_new.isoformat(), "limit": 10},
        )
        self.assertEqual(filtered.status_code, 200)
        payload = filtered.json()
        self.assertEqual(len(payload), 1)
