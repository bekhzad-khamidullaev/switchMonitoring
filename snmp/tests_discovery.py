from django.test import SimpleTestCase, TestCase

from snmp.models import DeviceProfile
from snmp.services.discovery.normalize import normalize_vendor_model
from snmp.services.discovery.profile_matcher import match_device_profile
from snmp.services.discovery.vendor_profiles.factory import get_vendor_profile


class DiscoveryNormalizeTests(SimpleTestCase):
    def test_normalize_detects_iskratel_vendor(self):
        data = normalize_vendor_model(
            "1.3.6.1.4.1.9999.1",
            "Iskratel ESCOM SI3000 firmware 1.2.3",
        )
        self.assertEqual(data["vendor"], "iskratel")

    def test_normalize_vendor_from_enterprise_oid(self):
        data = normalize_vendor_model(
            "1.3.6.1.4.1.9.1.1208",
            "Unknown switch description",
        )
        self.assertEqual(data["vendor"], "cisco")

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

    def test_normalize_extracts_model_from_platform_hint(self):
        data = normalize_vendor_model(
            "1.3.6.1.4.1.25506.11.1",
            "H3C Comware Platform Software, Model: S5120-28P-EI, Version 7.1.045",
        )
        self.assertEqual(data["vendor"], "h3c")
        self.assertEqual(data["model"], "S5120-28P-EI")


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


class VendorProfileFactoryTests(SimpleTestCase):
    def test_factory_picks_huawei_profile(self):
        profile = get_vendor_profile(
            vendor="huawei",
            model="S5720-28X",
            firmware="V200R010",
            sys_object_id="1.3.6.1.4.1.2011.2.23.134",
            sys_descr="Huawei S5720",
        )
        self.assertEqual(profile.name, "huawei")

    def test_factory_picks_h3c_profile(self):
        profile = get_vendor_profile(
            vendor="h3c",
            model="5130",
            firmware="7.1",
            sys_object_id="1.3.6.1.4.1.25506.11",
            sys_descr="HPE Comware Platform Software",
        )
        self.assertEqual(profile.name, "h3c")

    def test_factory_falls_back_to_generic_profile(self):
        profile = get_vendor_profile(
            vendor="unknown",
            model="",
            firmware="",
            sys_object_id="1.3.6.1.4.1.9999.1",
            sys_descr="Generic switch",
        )
        self.assertEqual(profile.name, "generic")

    def test_factory_picks_dlink_profile(self):
        profile = get_vendor_profile(
            vendor="d-link",
            model="DGS-3420",
            firmware="",
            sys_object_id="1.3.6.1.4.1.171.10.117.4.1",
            sys_descr="D-Link DGS-3420",
        )
        self.assertEqual(profile.name, "dlink")

    def test_factory_picks_extreme_profile(self):
        profile = get_vendor_profile(
            vendor="extreme networks",
            model="X460",
            firmware="",
            sys_object_id="1.3.6.1.4.1.1916.2.3.1",
            sys_descr="ExtremeXOS",
        )
        self.assertEqual(profile.name, "extreme")

    def test_factory_picks_threecom_profile(self):
        profile = get_vendor_profile(
            vendor="3com",
            model="4500G",
            firmware="",
            sys_object_id="1.3.6.1.4.1.43.1.19",
            sys_descr="3Com switch",
        )
        self.assertEqual(profile.name, "3com")
