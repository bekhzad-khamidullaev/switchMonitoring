from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from snmp.models import (
    Branch,
    Device,
    DeviceNeighbor,
    DeviceProfile,
    Interface,
    MetricDefinition,
    MetricSample,
    MetricSubscription,
)
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.tasks import (
    discover_all_devices_task,
    maintain_metric_samples_task,
    poll_all_devices_metrics_task,
)
from snmp.web.views.device_operations import refresh_device_status


class EndpointAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', password='p1')
        self.managed_device = Device.objects.create(hostname='sw-test', ip='10.0.0.1')
        self.settings_manager = self.settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_BROKER_URL='memory://')
        self.settings_manager.enable()

    def test_unauthorized_user_is_redirected_to_login(self):
        response = self.client.post(reverse('sync_zbx'))
        self.assertEqual(response.status_code, 302)

    def test_forbidden_user_gets_custom_403_page(self):
        self.client.login(username='u1', password='p1')
        response = self.client.post(reverse('sync_zbx'))
        self.assertEqual(response.status_code, 403)
        self.assertIn('Access denied.', response.content.decode('utf-8'))

    def test_method_not_allowed_uses_custom_405_page(self):
        perm = Permission.objects.get(codename='change_device')
        self.user.user_permissions.add(perm)

        self.client.login(username='u1', password='p1')
        response = self.client.get(reverse('update_optical_info', args=[self.managed_device.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertIn('Method Not Allowed', response.content.decode('utf-8'))


class DeviceCreateSnmpFieldsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='create_user', password='p1')
        add_perm = Permission.objects.get(codename='add_device')
        self.user.user_permissions.add(add_perm)
        self.client.login(username='create_user', password='p1')

    def test_create_device_requires_and_saves_snmp_fields(self):
        response = self.client.post(
            reverse('device_create'),
            data={
                'ip': '10.1.1.1',
                'hostname': 'new-host',
                'snmp_version': '2c',
                'snmp_community_ro': 'public_ro',
                'snmp_community_rw': 'private_rw',
            },
        )
        self.assertEqual(response.status_code, 302)
        managed_device = Device.objects.get(ip='10.1.1.1')
        self.assertEqual(managed_device.snmp_community_ro, 'public_ro')
        self.assertEqual(managed_device.snmp_community_rw, 'private_rw')

        self.assertEqual(managed_device.snmp_version, '2c')


class DeviceSettingsProfileAssignmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='device_update_user', password='p1')
        change_perm = Permission.objects.get(codename='change_device')
        self.user.user_permissions.add(change_perm)
        self.client.login(username='device_update_user', password='p1')

    def test_device_update_allows_assigning_profile(self):
        device = Device.objects.create(
            ip='10.1.2.3',
            hostname='host-1',
            snmp_version='2c',
            snmp_community_ro='public',
            snmp_community_rw='private',
        )
        profile = DeviceProfile.objects.create(
            vendor='snr',
            model_pattern='SNR-S2982G-24TE',
            firmware_pattern='',
            priority=10,
            active=True,
        )

        response = self.client.post(
            reverse('device_update', args=[device.pk]),
            data={
                'ip': str(device.ip),
                'hostname': device.hostname,
                'snmp_version': '2c',
                'snmp_community_ro': 'public',
                'snmp_community_rw': 'private',
                'profile': str(profile.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        device.refresh_from_db()
        self.assertEqual(device.profile_id, profile.id)

    def test_host_settings_page_allows_assigning_profile(self):
        device = Device.objects.create(
            ip='10.1.2.30',
            hostname='host-settings-1',
            snmp_version='2c',
            snmp_community_ro='public',
            snmp_community_rw='private',
        )
        profile = DeviceProfile.objects.create(
            vendor='snr',
            model_pattern='SNR-S2995G-24FX',
            firmware_pattern='',
            priority=20,
            active=True,
        )

        response = self.client.post(
            reverse('device_host_settings', args=[device.pk]),
            data={
                'ip': str(device.ip),
                'hostname': 'host-settings-renamed',
                'vendor': 'SNR',
                'model': 'S2995',
                'firmware': '',
                'sys_object_id': '',
                'snmp_version': '2c',
                'auth_profile': '',
                'status': 'on',
                'device_type': '',
                'uptime': '',
                'switch_mac': '',
                'snmp_community_ro': 'public',
                'snmp_community_rw': 'private',
                'neighbor': '',
                'parent_port': '',
                'profile': str(profile.pk),
                'group': '',
                'subgroup': '',
                'soft_version': '',
                'serial_number': '',
                'rx_signal': '',
                'tx_signal': '',
                'sfp_vendor': '',
                'part_number': '',
                'last_discovered_at': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        device.refresh_from_db()
        self.assertEqual(device.hostname, 'host-settings-renamed')
        self.assertEqual(device.profile_id, profile.id)

    def test_host_settings_apply_preset_prefills_form_without_saving(self):
        device = Device.objects.create(
            ip='10.1.2.31',
            hostname='host-settings-preset',
            snmp_version='2c',
            snmp_community_ro='public',
            snmp_community_rw='private',
        )
        profile = DeviceProfile.objects.create(
            vendor='preset-vendor',
            model_pattern='PRESET-MODEL',
            firmware_pattern='PRESET-FW',
            priority=20,
            active=True,
        )

        response = self.client.post(
            reverse('device_host_settings', args=[device.pk]),
            data={
                'action': 'apply_profile_preset',
                'ip': str(device.ip),
                'hostname': device.hostname,
                'vendor': '',
                'model': '',
                'firmware': '',
                'sys_object_id': '',
                'snmp_version': '2c',
                'auth_profile': '',
                'status': 'on',
                'device_type': '',
                'uptime': '',
                'switch_mac': '',
                'snmp_community_ro': 'public',
                'snmp_community_rw': 'private',
                'neighbor': '',
                'parent_port': '',
                'profile': str(profile.pk),
                'group': '',
                'subgroup': '',
                'soft_version': '',
                'serial_number': '',
                'rx_signal': '',
                'tx_signal': '',
                'sfp_vendor': '',
                'part_number': '',
                'last_discovered_at': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'preset-vendor')
        self.assertContains(response, 'PRESET-MODEL')
        self.assertContains(response, 'PRESET-FW')
        device.refresh_from_db()
        self.assertEqual(device.vendor, '')
        self.assertEqual(device.model, '')
        self.assertEqual(device.firmware, '')
        self.assertIsNone(device.profile_id)

    def test_host_settings_recommend_profile_selects_best_match_without_saving(self):
        device = Device.objects.create(
            ip='10.1.2.32',
            hostname='host-settings-recommend',
            snmp_version='2c',
            snmp_community_ro='public',
            snmp_community_rw='private',
        )
        low_specific = DeviceProfile.objects.create(
            vendor='snr',
            model_pattern='.*',
            firmware_pattern='',
            priority=10,
            active=True,
        )
        high_specific = DeviceProfile.objects.create(
            vendor='snr',
            model_pattern='S2995',
            firmware_pattern='7\\.0',
            priority=10,
            active=True,
        )

        response = self.client.post(
            reverse('device_host_settings', args=[device.pk]),
            data={
                'action': 'recommend_profile',
                'ip': str(device.ip),
                'hostname': device.hostname,
                'vendor': 'SNR',
                'model': 'S2995',
                'firmware': '7.0',
                'sys_object_id': '',
                'snmp_version': '2c',
                'auth_profile': '',
                'status': 'on',
                'device_type': '',
                'uptime': '',
                'switch_mac': '',
                'snmp_community_ro': 'public',
                'snmp_community_rw': 'private',
                'neighbor': '',
                'parent_port': '',
                'profile': str(low_specific.pk),
                'group': '',
                'subgroup': '',
                'soft_version': '',
                'serial_number': '',
                'rx_signal': '',
                'tx_signal': '',
                'sfp_vendor': '',
                'part_number': '',
                'last_discovered_at': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Recommended profile #{high_specific.pk} selected')
        device.refresh_from_db()
        self.assertIsNone(device.profile_id)


class MetricsPageActionTests(TestCase):
    def setUp(self):
        self.managed_device = Device.objects.create(hostname='sw-metrics', ip='10.0.0.50')
        self.user = User.objects.create_user(username='metrics_user', password='p1')
        change_device_perm = Permission.objects.get(codename='change_device')
        self.user.user_permissions.add(change_device_perm)
        self.client.login(username='metrics_user', password='p1')

    @patch('snmp.web.views.metrics.run_device_discovery')
    def test_run_discovery_action(self, mock_discovery):
        mock_discovery.return_value = {'interfaces_count': 2, 'profile_id': 10}
        response = self.client.post(
            reverse('device_metrics', args=[self.managed_device.pk]),
            data={'action': 'run_discovery', 'community': 'public'},
        )
        self.assertEqual(response.status_code, 302)
        mock_discovery.assert_called_once()

    @patch('snmp.web.views.metrics.poll_device_metrics')
    def test_poll_now_action(self, mock_poll):
        mock_poll.return_value = 3
        response = self.client.post(
            reverse('device_metrics', args=[self.managed_device.pk]),
            data={'action': 'poll_now'},
        )
        self.assertEqual(response.status_code, 302)
        mock_poll.assert_called_once()

    def test_export_device_metrics_csv(self):
        view_sample_perm = Permission.objects.get(codename='view_metricsample')
        self.user.user_permissions.add(view_sample_perm)

        device = self.managed_device
        interface = Interface.objects.create(device=device, if_index=1, if_name='eth1')
        metric = MetricDefinition.objects.create(key='rx_power_dbm_t', title='RX Test')
        sub = MetricSubscription.objects.create(device=device, interface=interface, metric=metric, enabled=True)
        MetricSample.objects.create(
            subscription=sub,
            value_float=-12.3,
            value_text='',
            quality=MetricSample.Quality.GOOD,
            raw_value='-1230',
        )

        response = self.client.get(reverse('export_device_metrics_csv', args=[self.managed_device.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        csv_payload = response.content.decode('utf-8')
        self.assertIn('metric,if_index,value_float', csv_payload)
        self.assertIn('rx_power_dbm_t', csv_payload)


class ApiOnboardValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api_user', password='p1')
        self.client.login(username='api_user', password='p1')
        self.url = '/snmp/api/devices/onboard'

    def test_onboard_forbidden_without_device_permissions(self):
        managed_device = Device.objects.create(hostname='dev-1', ip='10.20.0.1')
        response = self.client.post(self.url, data={'device_id': managed_device.id})
        self.assertEqual(response.status_code, 403)

    def test_onboard_create_requires_add_device_permission(self):
        response = self.client.post(self.url, data={'ip': '10.20.0.100'})
        self.assertEqual(response.status_code, 403)

        add_device_perm = Permission.objects.get(codename='add_device')
        self.user.user_permissions.add(add_device_perm)
        response = self.client.post(self.url, data={'ip': '10.20.0.100'})
        self.assertEqual(response.status_code, 201)


    def test_onboard_rejects_ip_mismatch_with_managed_device(self):
        view_device_perm = Permission.objects.get(codename='view_device')
        self.user.user_permissions.add(view_device_perm)
        managed_device = Device.objects.create(hostname='dev-2', ip='10.20.0.2')
        response = self.client.post(
            self.url,
            data={'device_id': managed_device.id, 'ip': '10.20.0.3'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Provided ip does not match device ip', response.content.decode('utf-8'))

    def test_onboard_success_with_permission(self):
        view_device_perm = Permission.objects.get(codename='view_device')
        self.user.user_permissions.add(view_device_perm)
        managed_device = Device.objects.create(hostname='dev-ok', ip='10.20.0.10')
        response = self.client.post(self.url, data={'device_id': managed_device.id})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Device.objects.filter(ip='10.20.0.10').exists())


class DeviceStatusIcmpTests(TestCase):
    def test_zero_rtt_is_treated_as_up(self):
        managed_device = Device.objects.create(hostname='icmp-dev', ip='10.30.0.1', status=False)
        with patch('snmp.web.views.device_operations.ping_host', return_value=0.0):
            response = refresh_device_status(managed_device)
        managed_device.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(managed_device.status)


class DeviceProfilesPageTests(TestCase):
    def setUp(self):
        self.managed_device = Device.objects.create(hostname='sw-profile', ip='10.0.0.60')
        self.user = User.objects.create_user(username='profiles_user', password='p1')
        change_device_perm = Permission.objects.get(codename='change_device')
        self.user.user_permissions.add(change_device_perm)
        self.client.login(username='profiles_user', password='p1')

    def test_profiles_page_renders(self):
        response = self.client.get(reverse('device_profiles'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Device Profiles', response.content.decode('utf-8'))

    def test_create_profile_manually_and_assign_device(self):
        response = self.client.post(
            reverse('device_profile_create'),
            data={
                'vendor': 'snr',
                'model_pattern': 'SNR-S2982G-24TE',
                'firmware_pattern': '7.0.3',
                'priority': '10',
                'active': 'on',
                'assign_managed_device_id': str(self.managed_device.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        profile = DeviceProfile.objects.get(vendor='snr', model_pattern='SNR-S2982G-24TE', firmware_pattern='7.0.3')
        self.managed_device.refresh_from_db()
        self.assertEqual(self.managed_device.profile_id, profile.id)

    def test_profile_detail_renders(self):
        profile = DeviceProfile.objects.create(
            vendor='snr',
            model_pattern='SNR-S2982G-24TE',
            firmware_pattern='',
            priority=100,
            active=True,
        )
        response = self.client.get(reverse('device_profile_detail', args=[profile.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Assigned Hosts', response.content.decode('utf-8'))

    def test_profile_update(self):
        profile = DeviceProfile.objects.create(
            vendor='snr',
            model_pattern='SNR-S2982G-24TE',
            firmware_pattern='',
            priority=100,
            active=True,
        )
        response = self.client.post(
            reverse('device_profile_update', args=[profile.pk]),
            data={
                'vendor': 'snr-updated',
                'model_pattern': 'SNR-S2982G-24TE',
                'firmware_pattern': '7.0',
                'priority': '50',
                'active': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.vendor, 'snr-updated')
        self.assertEqual(profile.priority, 50)

    def test_profile_delete(self):
        profile = DeviceProfile.objects.create(
            vendor='snr',
            model_pattern='SNR-S2982G-24TE',
            firmware_pattern='',
            priority=100,
            active=True,
        )
        response = self.client.post(reverse('device_profile_delete', args=[profile.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DeviceProfile.objects.filter(pk=profile.pk).exists())


class ZabbixSyncBranchHierarchyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='zbx_user', password='p1')
        add_perm = Permission.objects.get(codename='add_device')
        self.user.user_permissions.add(add_perm)
        self.client.login(username='zbx_user', password='p1')

    @patch('snmp.web.views.integrations.requests.post')
    def test_sync_creates_group_and_subgroup_hierarchy(self, mock_post):
        mock_post.side_effect = [
            _MockResponse(
                {
                    'result': [
                        {
                            'hostid': '101',
                            'name': 'edge-sw-1',
                            'hostgroups': [
                                {'groupid': '1', 'name': 'HQ/Access/Floor-1'},
                            ],
                        }
                    ]
                }
            ),
            _MockResponse({'result': [{'ip': '10.55.0.10'}]}),
        ]

        with self.settings(
            ZABBIX_URL='https://example.test/api_jsonrpc.php',
            ZABBIX_TOKEN='token',
            ZABBIX_VERIFY_SSL=False,
        ):
            response = self.client.post(reverse('sync_zbx'))

        self.assertEqual(response.status_code, 302)
        hq = Branch.objects.get(name='HQ', parent__isnull=True)
        access = Branch.objects.get(name='Access', parent=hq)
        floor = Branch.objects.get(name='Floor-1', parent=access)
        self.assertIsNotNone(floor)

        device = Device.objects.get(ip='10.55.0.10')
        self.assertEqual(device.group_id, floor.id)
        self.assertIsNone(device.subgroup_id)

    @patch('snmp.web.views.integrations.requests.post')
    def test_sync_reuses_existing_groups_without_duplicates(self, mock_post):
        hq = Branch.objects.create(name='hq')
        access = Branch.objects.create(name=' Access ', parent=hq)
        floor = Branch.objects.create(name='floor-1', parent=access)

        mock_post.side_effect = [
            _MockResponse(
                {
                    'result': [
                        {
                            'hostid': '201',
                            'name': 'edge-sw-2',
                            'hostgroups': [
                                {'groupid': '11', 'name': 'HQ/Access/Floor-1'},
                            ],
                        }
                    ]
                }
            ),
            _MockResponse({'result': [{'ip': '10.55.0.11'}]}),
        ]

        with self.settings(
            ZABBIX_URL='https://example.test/api_jsonrpc.php',
            ZABBIX_TOKEN='token',
            ZABBIX_VERIFY_SSL=False,
        ):
            response = self.client.post(reverse('sync_zbx'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Branch.objects.count(), 3)
        device = Device.objects.get(ip='10.55.0.11')
        self.assertEqual(device.group_id, floor.id)
        self.assertIsNone(device.subgroup_id)

    @patch('snmp.web.views.integrations.requests.post')
    def test_sync_skips_duplicate_hosts_with_same_ip(self, mock_post):
        mock_post.side_effect = [
            _MockResponse(
                {
                    'result': [
                        {
                            'hostid': '301',
                            'name': 'edge-sw-main',
                            'hostgroups': [
                                {'groupid': '21', 'name': 'HQ/Access/Floor-2'},
                            ],
                        },
                        {
                            'hostid': '302',
                            'name': 'edge-sw-duplicate',
                            'hostgroups': [
                                {'groupid': '22', 'name': 'HQ/Access/Floor-3'},
                            ],
                        },
                    ]
                }
            ),
            _MockResponse({'result': [{'ip': '10.55.0.12'}]}),
            _MockResponse({'result': [{'ip': '10.55.0.12'}]}),
        ]

        with self.settings(
            ZABBIX_URL='https://example.test/api_jsonrpc.php',
            ZABBIX_TOKEN='token',
            ZABBIX_VERIFY_SSL=False,
        ):
            response = self.client.post(reverse('sync_zbx'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Device.objects.filter(ip='10.55.0.12').count(), 1)
        device = Device.objects.get(ip='10.55.0.12')
        self.assertEqual(device.hostname, 'edge-sw-main')


class _MockResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception('http error')

    def json(self):
        return self._payload


class HostMapViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='host_map_user', password='p1')
        view_device_perm = Permission.objects.get(codename='view_device')
        self.user.user_permissions.add(view_device_perm)
        self.client.login(username='host_map_user', password='p1')

        self.left = Device.objects.create(hostname='core-a', ip='10.50.0.1', switch_mac='aa:bb:cc:dd:ee:01')
        self.right = Device.objects.create(hostname='core-b', ip='10.50.0.2', switch_mac='aa:bb:cc:dd:ee:02')
        DeviceNeighbor.objects.create(
            mac1='aa:bb:cc:dd:ee:01',
            port1=1,
            mac2='aa:bb:cc:dd:ee:02',
            port2=2,
        )

    def test_host_map_page_renders(self):
        response = self.client.get(reverse('neighbor_devices_map'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Host Topology Map', response.content.decode('utf-8'))

    def test_host_map_data_contains_nodes_and_links(self):
        response = self.client.get(reverse('neighbor_devices_map_data'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['nodes']), 2)
        self.assertEqual(len(payload['links']), 1)
        self.assertIn('detail_url', payload['nodes'][0])
        self.assertEqual(payload['links'][0]['left_port'], 1)
        self.assertEqual(payload['links'][0]['right_port'], 2)
        self.assertIn(payload['links'][0]['status'], {'up', 'down', 'unknown'})


class TaskResilienceTests(TestCase):
    def setUp(self):
        Device.objects.create(hostname='t-1', ip='10.40.0.1')
        Device.objects.create(hostname='t-2', ip='10.40.0.2')
        self.settings_manager = self.settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_BROKER_URL='memory://')
        self.settings_manager.enable()

    @patch('snmp.tasks.poll_device_metrics_task.delay')
    def test_poll_all_fanout_queues_all_devices(self, mock_delay):
        with patch('snmp.tasks.POLL_DISPATCH_ASYNC', True):
            result = poll_all_devices_metrics_task()
        self.assertEqual(result['mode'], 'fanout')
        self.assertEqual(result['queued'], 2)
        self.assertEqual(mock_delay.call_count, 2)

    @patch('snmp.tasks.poll_device_metrics')
    def test_poll_all_inline_isolates_failures(self, mock_poll):
        mock_poll.side_effect = [3, RuntimeError('boom')]
        with patch('snmp.tasks.POLL_DISPATCH_ASYNC', False):
            result = poll_all_devices_metrics_task()
        self.assertEqual(result['mode'], 'inline')
        self.assertEqual(result['saved'], 3)
        self.assertEqual(result['failed'], 1)

    @patch('snmp.tasks._redis_queue_depth', return_value=999999)
    def test_poll_all_throttles_when_queue_is_over_limit(self, _mock_depth):
        with patch('snmp.tasks.POLL_DISPATCH_ASYNC', True), patch('snmp.tasks.POLL_MAX_QUEUE_DEPTH', 10):
            result = poll_all_devices_metrics_task()
        self.assertEqual(result['mode'], 'throttled')
        self.assertEqual(result['queued'], 0)

    @patch('snmp.tasks.run_device_discovery')
    def test_discover_all_devices_isolates_unexpected_errors(self, mock_discovery):
        def side_effect(ip, **kwargs):
            if ip == '10.40.0.2':
                raise RuntimeError('boom')
        mock_discovery.side_effect = side_effect

        result = discover_all_devices_task()
        self.assertEqual(result['queued'], 2)
        # 1 success + 1 failure + 3 retries = 5 calls
        self.assertEqual(mock_discovery.call_count, 5)

    @patch('snmp.tasks.call_command')
    def test_maintain_metric_samples_task_calls_command(self, mock_call_command):
        result = maintain_metric_samples_task()
        self.assertEqual(result['status'], 'ok')
        mock_call_command.assert_called_once()


class MetricSampleMaintenanceTests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(hostname='ret-1', ip='10.60.0.1')
        self.metric = MetricDefinition.objects.create(key='ret_metric', title='Retention Metric')
        self.subscription = MetricSubscription.objects.create(device=self.device, metric=self.metric, enabled=True)

    def _sample(self, *, days_ago: int):
        MetricSample.objects.create(
            subscription=self.subscription,
            ts=timezone.now() - timedelta(days=days_ago),
            value_float=1.0,
            quality=MetricSample.Quality.GOOD,
        )

    def test_maintain_metric_samples_dry_run_does_not_delete(self):
        self._sample(days_ago=90)
        self._sample(days_ago=1)

        call_command(
            'maintain_metric_samples',
            retention_days=30,
            batch_size=100,
            max_batches=5,
            dry_run=True,
        )

        self.assertEqual(MetricSample.objects.count(), 2)

    def test_maintain_metric_samples_deletes_in_bounded_batches(self):
        self._sample(days_ago=90)
        self._sample(days_ago=80)
        self._sample(days_ago=70)
        self._sample(days_ago=1)

        call_command(
            'maintain_metric_samples',
            retention_days=30,
            batch_size=2,
            max_batches=1,
        )
        self.assertEqual(MetricSample.objects.count(), 2)

        call_command(
            'maintain_metric_samples',
            retention_days=30,
            batch_size=2,
            max_batches=2,
        )
        self.assertEqual(MetricSample.objects.count(), 1)


class DiscoveryNeighborSyncTests(TestCase):
    @patch("snmp.services.discovery.pipeline.read_base_snmp")
    def test_discovery_syncs_lldp_neighbors(self, mock_read_base):
        local = Device.objects.create(hostname="sw-a", ip="10.70.0.1", switch_mac="aa:bb:cc:dd:ee:01")
        Device.objects.create(hostname="sw-b", ip="10.70.0.2", switch_mac="aa:bb:cc:dd:ee:02")

        mock_read_base.return_value = {
            "sys_object_id": "1.3.6.1.4.1.2011.2.23.134",
            "sys_descr": "Huawei S5720",
            "switch_mac": "AA BB CC DD EE 01",
            "interfaces": [
                {
                    "if_index": 1,
                    "if_name": "GigabitEthernet0/0/1",
                    "if_alias": "",
                    "if_type": "6",
                    "is_optical": False,
                    "admin_up": True,
                    "oper_up": True,
                }
            ],
            "lldp_neighbors": [
                {
                    "local_port": 24,
                    "remote_chassis_mac": "aa:bb:cc:dd:ee:02",
                    "remote_port": 48,
                    "remote_port_id": "48",
                }
            ],
        }

        run_device_discovery(ip=str(local.ip), community="public", managed_device=local)

        self.assertTrue(
            DeviceNeighbor.objects.filter(
                mac1="aa:bb:cc:dd:ee:01",
                port1=24,
                mac2="aa:bb:cc:dd:ee:02",
                port2=48,
            ).exists()
        )

    @patch("snmp.services.discovery.pipeline.read_base_snmp")
    def test_discovery_replaces_previous_neighbors_for_device(self, mock_read_base):
        local = Device.objects.create(hostname="sw-a", ip="10.70.1.1", switch_mac="aa:bb:cc:dd:ee:11")
        DeviceNeighbor.objects.create(
            mac1="aa:bb:cc:dd:ee:11",
            port1=1,
            mac2="aa:bb:cc:dd:ee:12",
            port2=2,
        )

        mock_read_base.return_value = {
            "sys_object_id": "1.3.6.1.4.1.2011.2.23.134",
            "sys_descr": "Huawei S5720",
            "switch_mac": "aa:bb:cc:dd:ee:11",
            "interfaces": [],
            "lldp_neighbors": [],
        }
        run_device_discovery(ip=str(local.ip), community="public", managed_device=local)

        self.assertFalse(DeviceNeighbor.objects.filter(mac1="aa:bb:cc:dd:ee:11").exists())


class BulkDeviceJobsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bulk_jobs_user", password="p1")
        change_perm = Permission.objects.get(codename="change_device")
        self.user.user_permissions.add(change_perm)
        self.client.login(username="bulk_jobs_user", password="p1")

        self.device1 = Device.objects.create(hostname="bulk-a", ip="10.80.0.1")
        self.device2 = Device.objects.create(hostname="bulk-b", ip="10.80.0.2")

    @patch("snmp.web.views.integrations.discover_device_task.delay")
    def test_bulk_discovery_job_queues_selected_devices(self, mock_delay):
        response = self.client.post(
            reverse("run_bulk_device_job"),
            data={
                "action": "discover",
                "scope": "device_ids",
                "device_ids": f"{self.device1.id},{self.device2.id}",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["queued"], 2)
        self.assertEqual(mock_delay.call_count, 2)

    @patch("snmp.web.views.integrations.poll_device_metrics_task.delay")
    def test_bulk_poll_job_queues_all_devices(self, mock_delay):
        response = self.client.post(
            reverse("run_bulk_device_job"),
            data={"action": "poll", "scope": "all"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["queued"], 2)
        self.assertEqual(mock_delay.call_count, 2)

    def test_bulk_jobs_reject_invalid_action(self):
        response = self.client.post(
            reverse("run_bulk_device_job"),
            data={"action": "reboot", "scope": "all"},
        )
        self.assertEqual(response.status_code, 400)


class PortActivityReportViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="report_user", password="p1")
        view_device_perm = Permission.objects.get(codename="view_device")
        self.user.user_permissions.add(view_device_perm)
        self.client.login(username="report_user", password="p1")

        self.group = Branch.objects.create(name="Report Branch")
        self.device = Device.objects.create(hostname="report-sw", ip="10.90.0.1", group=self.group)

    def test_report_page_renders(self):
        branch_perm = Permission.objects.get(codename="view_report_branch")
        self.user.user_permissions.add(branch_perm)
        response = self.client.get(reverse("port_activity_report"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Port Activity Report", response.content.decode("utf-8"))
