from django.core.management.base import BaseCommand
from snmp.models import DeviceProfile, MetricDefinition, MetricBinding

class Command(BaseCommand):
    help = 'Seed the database with a massive collection of device profiles, metrics and optical monitoring'

    def handle(self, *args, **options):
        # 1. Metric Definitions
        metrics = {
            'cpu_usage': {
                'title': 'CPU Usage',
                'description': 'CPU utilization percentage',
                'unit': '%',
                'value_type': MetricDefinition.ValueType.FLOAT
            },
            'memory_usage': {
                'title': 'Memory Usage',
                'description': 'Memory utilization percentage',
                'unit': '%',
                'value_type': MetricDefinition.ValueType.FLOAT
            },
            'device_temperature': {
                'title': 'Temperature',
                'description': 'Internal device temperature',
                'unit': 'C',
                'value_type': MetricDefinition.ValueType.FLOAT
            },
            'sys_uptime': {
                'title': 'System Uptime',
                'description': 'Time since last reboot',
                'unit': 'timeticks',
                'value_type': MetricDefinition.ValueType.INTEGER
            },
            'active_sessions': {
                'title': 'Active Sessions',
                'description': 'Number of active firewall or VPN sessions',
                'unit': 'sessions',
                'value_type': MetricDefinition.ValueType.INTEGER
            },
            'optical_rx_power': {
                'title': 'Optical RX Power',
                'description': 'Optical receiver power level',
                'unit': 'dBm',
                'value_type': MetricDefinition.ValueType.FLOAT
            },
            'optical_tx_power': {
                'title': 'Optical TX Power',
                'description': 'Optical transmitter power level',
                'unit': 'dBm',
                'value_type': MetricDefinition.ValueType.FLOAT
            }
        }

        metric_objs = {}
        for key, defaults in metrics.items():
            obj, created = MetricDefinition.objects.update_or_create(
                key=key,
                defaults=defaults
            )
            metric_objs[key] = obj
            if created:
                self.stdout.write(f'Created metric: {key}')

        # 2. Device Profiles
        profiles_data = [
            {
                'vendor': 'huawei',
                'model_pattern': r'S[356]\d{3}',
                'firmware_pattern': '',
                'priority': 50,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.2011.5.25.31.1.1.1.1.5.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.2011.5.25.31.1.1.1.1.7.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'device_temperature', 'oid': '1.3.6.1.4.1.2011.5.25.31.1.1.1.1.11.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'optical_rx_power', 'oid': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.32', 'strategy': MetricBinding.IndexStrategy.IF_INDEX, 'converter': MetricBinding.Converter.DIV100},
                    {'metric': 'optical_tx_power', 'oid': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.33', 'strategy': MetricBinding.IndexStrategy.IF_INDEX, 'converter': MetricBinding.Converter.DIV100},
                ]
            },
            {
                'vendor': 'cisco',
                'model_pattern': r'Catalyst|Nexus|ISR|ASR',
                'firmware_pattern': '',
                'priority': 60,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.9.9.109.1.1.1.1.3.1', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.9.9.48.1.1.1.6.1', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'optical_rx_power', 'oid': '1.3.6.1.4.1.9.9.91.1.1.1.1.4', 'strategy': MetricBinding.IndexStrategy.VENDOR_MAP, 'converter': MetricBinding.Converter.DIV10},
                    {'metric': 'optical_tx_power', 'oid': '1.3.6.1.4.1.9.9.91.1.1.1.1.4', 'strategy': MetricBinding.IndexStrategy.VENDOR_MAP, 'converter': MetricBinding.Converter.DIV10},
                ]
            },
            {
                'vendor': 'mikrotik',
                'model_pattern': r'RB|CCR|CRS',
                'firmware_pattern': '',
                'priority': 70,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.14988.1.1.3.10.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.14988.1.1.3.11.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'device_temperature', 'oid': '1.3.6.1.4.1.14988.1.1.3.13.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'optical_rx_power', 'oid': '1.3.6.1.4.1.14988.1.1.14.1.1.2', 'strategy': MetricBinding.IndexStrategy.IF_INDEX, 'converter': MetricBinding.Converter.DIV100},
                    {'metric': 'optical_tx_power', 'oid': '1.3.6.1.4.1.14988.1.1.14.1.1.5', 'strategy': MetricBinding.IndexStrategy.IF_INDEX, 'converter': MetricBinding.Converter.DIV100},
                ]
            },
            {
                'vendor': 'juniper',
                'model_pattern': r'EX\d+|MX\d+|SRX\d+|QFX\d+',
                'firmware_pattern': '',
                'priority': 90,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.2636.3.1.13.1.8.9.1.0.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.2636.3.1.13.1.11.9.1.0.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'device_temperature', 'oid': '1.3.6.1.4.1.2636.3.1.13.1.7.9.1.0.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'optical_rx_power', 'oid': '1.3.6.1.4.1.2636.3.60.1.1.1.1.5', 'strategy': MetricBinding.IndexStrategy.IF_INDEX, 'converter': MetricBinding.Converter.DIV100},
                    {'metric': 'optical_tx_power', 'oid': '1.3.6.1.4.1.2636.3.60.1.1.1.1.6', 'strategy': MetricBinding.IndexStrategy.IF_INDEX, 'converter': MetricBinding.Converter.DIV100},
                ]
            },
            {
                'vendor': 'fortinet',
                'model_pattern': r'FortiGate',
                'firmware_pattern': '',
                'priority': 100,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.12356.101.4.1.3.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.12356.101.4.1.4.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'active_sessions', 'oid': '1.3.6.1.4.1.12356.101.4.1.8.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'extreme',
                'model_pattern': r'Summit|BlackDiamond|X\d+',
                'firmware_pattern': '',
                'priority': 150,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.1916.1.1.1.28.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.1916.1.1.1.29.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'device_temperature', 'oid': '1.3.6.1.4.1.1916.1.1.1.22.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'allied',
                'model_pattern': r'x\d+|AT-\d+',
                'firmware_pattern': '',
                'priority': 160,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.294.1.1.1.1.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.294.1.1.1.2.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'dell',
                'model_pattern': r'PowerConnect|N\d+|S\d+',
                'firmware_pattern': '',
                'priority': 170,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.674.10895.5000.2.6132.1.1.1.1.4.1', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.674.10895.5000.2.6132.1.1.1.1.4.2', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'brocade',
                'model_pattern': r'ICX|FCX|V\d+',
                'firmware_pattern': '',
                'priority': 180,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.1991.1.1.2.1.50.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.1991.1.1.2.1.53.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'alcatel',
                'model_pattern': r'OmniSwitch|OS\d+',
                'firmware_pattern': '',
                'priority': 190,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.648.1.5.2.1.1.1.11.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.648.1.5.2.1.1.1.1.3.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'hp',
                'model_pattern': r'Aruba|ProCurve|OfficeConnect',
                'firmware_pattern': '',
                'priority': 110,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'paloalto',
                'model_pattern': r'PA-\d+',
                'firmware_pattern': '',
                'priority': 120,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.25461.2.1.2.1.1.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.25461.2.1.2.1.2.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'active_sessions', 'oid': '1.3.6.1.4.1.25461.2.1.2.1.3.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'ubnt',
                'model_pattern': r'EdgeRouter|EdgeSwitch|UniFi',
                'firmware_pattern': '',
                'priority': 130,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.41112.1.4.1.1.4.1', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.41112.1.4.1.1.6.1', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'zyxel',
                'model_pattern': r'GS\d+|XGS\d+',
                'firmware_pattern': '',
                'priority': 140,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.890.1.15.3.2.4.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.890.1.15.3.2.5.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'd-link',
                'model_pattern': r'DGS|DES',
                'firmware_pattern': '',
                'priority': 80,
                'bindings': [
                    {'metric': 'cpu_usage', 'oid': '1.3.6.1.4.1.171.12.1.1.6.2.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                    {'metric': 'memory_usage', 'oid': '1.3.6.1.4.1.171.12.1.1.6.1.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            },
            {
                'vendor': 'generic',
                'model_pattern': r'.*',
                'firmware_pattern': '',
                'priority': 1000,
                'bindings': [
                    {'metric': 'sys_uptime', 'oid': '1.3.6.1.2.1.1.3.0', 'strategy': MetricBinding.IndexStrategy.FIXED},
                ]
            }
        ]

        for p_data in profiles_data:
            profile, created = DeviceProfile.objects.update_or_create(
                vendor=p_data['vendor'],
                model_pattern=p_data['model_pattern'],
                firmware_pattern=p_data['firmware_pattern'],
                defaults={'priority': p_data['priority'], 'active': True}
            )
            created_str = "(New)" if created else "(Updated)"
            self.stdout.write(f'{created_str} Profile: {p_data["vendor"]} {p_data["model_pattern"]}')

            for b_data in p_data.get('bindings', []):
                MetricBinding.objects.update_or_create(
                    profile=profile,
                    metric=metric_objs[b_data['metric']],
                    oid_template=b_data['oid'],
                    defaults={
                        'index_strategy': b_data['strategy'], 
                        'converter': b_data.get('converter', MetricBinding.Converter.IDENTITY),
                        'enabled_by_default': True
                    }
                )

        self.stdout.write(self.style.SUCCESS('Successfully seeded massive profiles with optical monitoring'))
