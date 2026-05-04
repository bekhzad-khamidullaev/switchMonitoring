from types import SimpleNamespace

from django.test import SimpleTestCase

from snmp.models import MetricBinding
from snmp.services.metrics.runtime import apply_converter, render_oid, validate_numeric


class MetricsRuntimeTests(SimpleTestCase):
    def test_apply_converter_div100(self):
        result = apply_converter(MetricBinding.Converter.DIV100, '1234')
        self.assertEqual(result, 12.34)

    def test_apply_converter_div10(self):
        result = apply_converter(MetricBinding.Converter.DIV10, '123')
        self.assertEqual(result, 12.3)

    def test_apply_converter_mw_to_dbm(self):
        result = apply_converter(MetricBinding.Converter.MW_TO_DBM, '1000')
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_apply_converter_enum_map(self):
        result = apply_converter(
            MetricBinding.Converter.ENUM_MAP,
            '1',
            {'enum_map': {'1': 'up', '2': 'down'}},
        )
        self.assertEqual(result, 'up')

    def test_validate_numeric_filters_sentinel(self):
        self.assertIsNone(validate_numeric(-65535))

    def test_validate_numeric_filters_custom_boundaries(self):
        self.assertIsNone(validate_numeric(120, {'max_allowed': 100}))
        self.assertIsNone(validate_numeric(-120, {'min_allowed': -100}))
        self.assertEqual(validate_numeric(50, {'min_allowed': 0, 'max_allowed': 100}), 50.0)

    def test_render_oid_if_index(self):
        binding = SimpleNamespace(
            index_strategy=MetricBinding.IndexStrategy.IF_INDEX,
            oid_template='1.3.6.1.4.1.9999.1.{if_index}',
            binding_params={},
        )
        device = SimpleNamespace(ip='10.0.0.1', vendor='eltex', model='MES2428')
        interface = SimpleNamespace(if_index=25)

        resolved = render_oid(binding=binding, device=device, interface=interface)
        self.assertEqual(resolved.oid, '1.3.6.1.4.1.9999.1.25')
        self.assertEqual(resolved.index, 25)

    def test_render_oid_fixed(self):
        binding = SimpleNamespace(
            index_strategy=MetricBinding.IndexStrategy.FIXED,
            oid_template='1.3.6.1.4.1.9999.1.{index}',
            binding_params={'fixed_index': 7},
        )
        device = SimpleNamespace(ip='10.0.0.1', vendor='eltex', model='MES2428')

        resolved = render_oid(binding=binding, device=device, interface=None)
        self.assertEqual(resolved.oid, '1.3.6.1.4.1.9999.1.7')
        self.assertEqual(resolved.index, 7)
