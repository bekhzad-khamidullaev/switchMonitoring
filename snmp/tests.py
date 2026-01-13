"""snmp app unit tests.

These tests are DB-free (SimpleTestCase) and validate key helpers used by monitoring.
"""

from django.test import SimpleTestCase

from snmp.services.bandwidth import CounterSnapshot, compute_bps
from snmp.services.interface_classification import is_virtual_interface


class VirtualInterfaceClassifierTests(SimpleTestCase):
    def test_loopback_by_iftype(self):
        is_virt, reason = is_virtual_interface(24, 'Loopback0', 'Loopback interface', '')
        self.assertTrue(is_virt)
        self.assertIn('ifType', reason)

    def test_vlan_by_name(self):
        is_virt, reason = is_virtual_interface(None, 'Vlan100', '', '')
        self.assertTrue(is_virt)
        self.assertTrue(reason)

    def test_lag_by_name(self):
        is_virt, reason = is_virtual_interface(None, 'Port-Channel1', '', '')
        self.assertTrue(is_virt)
        self.assertTrue(reason)

    def test_physical_interface_not_virtual(self):
        is_virt, reason = is_virtual_interface(None, 'GigabitEthernet0/1', 'Gi0/1', '')
        self.assertFalse(is_virt)
        self.assertEqual('', reason)


class BandwidthComputationTests(SimpleTestCase):
    def test_compute_bps_basic(self):
        prev = CounterSnapshot(in_octets=1000, out_octets=2000)
        curr = CounterSnapshot(in_octets=2000, out_octets=3000)
        bps = compute_bps(prev, curr, interval_sec=10, counter_bits=64)
        self.assertEqual(bps, (800, 800))

    def test_compute_bps_rollover_32bit(self):
        # Simulate 32-bit counter rollover
        prev = CounterSnapshot(in_octets=4294967200, out_octets=4294967200)
        curr = CounterSnapshot(in_octets=100, out_octets=200)
        bps = compute_bps(prev, curr, interval_sec=10, counter_bits=32)
        self.assertIsNotNone(bps)
        in_bps, out_bps = bps
        self.assertGreater(in_bps, 0)
        self.assertGreater(out_bps, 0)

    def test_compute_bps_invalid_interval(self):
        prev = CounterSnapshot(in_octets=100, out_octets=100)
        curr = CounterSnapshot(in_octets=200, out_octets=200)
        self.assertIsNone(compute_bps(prev, curr, interval_sec=0, counter_bits=64))
