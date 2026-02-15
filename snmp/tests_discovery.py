from django.test import SimpleTestCase, TestCase

from snmp.models import DeviceProfile
from snmp.services.discovery.normalize import normalize_vendor_model
from snmp.services.discovery.profile_matcher import match_device_profile


class DiscoveryNormalizeTests(SimpleTestCase):
    def test_normalize_huawei_vendor_model_and_firmware(self):
        data = normalize_vendor_model(
            "1.3.6.1.4.1.2011.2.23.134",
            "Huawei S3352P-EI-24S version V200R001C00SPC300",
        )
        self.assertEqual(data["vendor"], "huawei")
        self.assertEqual(data["model"], "S3352P-EI-24S")
        self.assertEqual(data["firmware"], "V200R001C00SPC300")

    def test_normalize_unknown_vendor(self):
        data = normalize_vendor_model(
            "1.3.6.1.4.1.9999.1.1",
            "Generic Ethernet Device firmware 1.0.0",
        )
        self.assertEqual(data["vendor"], "unknown")
        self.assertEqual(data["model"], "")
        self.assertEqual(data["firmware"], "1.0.0")


class DiscoveryProfileMatcherTests(TestCase):
    def test_match_profile_uses_priority(self):
        lower_priority = DeviceProfile.objects.create(
            vendor="huawei",
            model_pattern=r"S33\d{2}",
            firmware_pattern="",
            priority=5,
            active=True,
        )
        DeviceProfile.objects.create(
            vendor="huawei",
            model_pattern=r"S33\d{2}",
            firmware_pattern=r"V200R",
            priority=50,
            active=True,
        )

        matched = match_device_profile("huawei", "S3352P-EI-24S", "V200R001")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.id, lower_priority.id)

    def test_match_profile_respects_firmware_pattern(self):
        DeviceProfile.objects.create(
            vendor="huawei",
            model_pattern=r"S33\d{2}",
            firmware_pattern=r"V100R",
            priority=10,
            active=True,
        )
        expected = DeviceProfile.objects.create(
            vendor="huawei",
            model_pattern=r"S33\d{2}",
            firmware_pattern=r"V200R",
            priority=20,
            active=True,
        )

        matched = match_device_profile("huawei", "S3352P-EI-24S", "V200R001C00SPC300")
        self.assertIsNotNone(matched)
        self.assertEqual(matched.id, expected.id)

    def test_match_profile_returns_none(self):
        DeviceProfile.objects.create(
            vendor="eltex",
            model_pattern=r"MES\d+",
            firmware_pattern="",
            priority=10,
            active=True,
        )

        matched = match_device_profile("huawei", "S3352P-EI-24S", "V200R001")
        self.assertIsNone(matched)
