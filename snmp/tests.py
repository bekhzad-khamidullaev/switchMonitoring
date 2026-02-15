from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from snmp.models import Device, Interface, ManagedDevice, MetricDefinition, MetricSample, MetricSubscription
from snmp.web.views.device_operations import refresh_device_status
from snmp.tasks import discover_all_devices_task, poll_all_devices_metrics_task


class EndpointAccessTests(TestCase):
    def setUp(self):
        self.managed_device = ManagedDevice.objects.create(hostname='sw-test', ip='10.0.0.1')
        self.user = User.objects.create_user(username='u1', password='p1')

    def test_unauthorized_user_is_redirected_to_login(self):
        response = self.client.post(reverse('sync_zbx'))
        self.assertEqual(response.status_code, 302)

    def test_forbidden_user_gets_custom_403_page(self):
        self.client.login(username='u1', password='p1')
        response = self.client.post(reverse('sync_zbx'))
        self.assertEqual(response.status_code, 403)
        self.assertIn('Access denied.', response.content.decode('utf-8'))

    def test_method_not_allowed_uses_custom_405_page(self):
        perm = Permission.objects.get(codename='change_switch')
        self.user.user_permissions.add(perm)

        self.client.login(username='u1', password='p1')
        response = self.client.get(reverse('update_optical_info', args=[self.managed_device.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertIn('Method Not Allowed', response.content.decode('utf-8'))


class MetricsPageActionTests(TestCase):
    def setUp(self):
        self.managed_device = ManagedDevice.objects.create(hostname='sw-metrics', ip='10.0.0.50')
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

        device = Device.objects.create(ip='10.0.0.50', managed_device=self.managed_device, hostname='sw-metrics')
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
        managed_device = ManagedDevice.objects.create(hostname='dev-1', ip='10.20.0.1')
        response = self.client.post(self.url, data={'managed_device_id': managed_device.id})
        self.assertEqual(response.status_code, 403)

    def test_onboard_requires_ip_when_managed_device_has_no_ip(self):
        view_device_perm = Permission.objects.get(codename='view_device')
        self.user.user_permissions.add(view_device_perm)
        managed_device = ManagedDevice.objects.create(hostname='dev-no-ip', ip=None)
        response = self.client.post(self.url, data={'managed_device_id': managed_device.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('IP address is required', response.content.decode('utf-8'))

    def test_onboard_rejects_ip_mismatch_with_managed_device(self):
        view_device_perm = Permission.objects.get(codename='view_device')
        self.user.user_permissions.add(view_device_perm)
        managed_device = ManagedDevice.objects.create(hostname='dev-2', ip='10.20.0.2')
        response = self.client.post(
            self.url,
            data={'managed_device_id': managed_device.id, 'ip': '10.20.0.3'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('does not match managed device ip', response.content.decode('utf-8'))

    def test_onboard_success_with_permission(self):
        view_device_perm = Permission.objects.get(codename='view_device')
        self.user.user_permissions.add(view_device_perm)
        managed_device = ManagedDevice.objects.create(hostname='dev-ok', ip='10.20.0.10')
        response = self.client.post(self.url, data={'managed_device_id': managed_device.id})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Device.objects.filter(ip='10.20.0.10').exists())


class DeviceStatusIcmpTests(TestCase):
    def test_zero_rtt_is_treated_as_up(self):
        managed_device = ManagedDevice.objects.create(hostname='icmp-dev', ip='10.30.0.1', status=False)
        with patch('snmp.web.views.device_operations.ping_host', return_value=0.0):
            response = refresh_device_status(managed_device)
        managed_device.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(managed_device.status)


class TaskResilienceTests(TestCase):
    def setUp(self):
        md1 = ManagedDevice.objects.create(hostname='t-1', ip='10.40.0.1')
        md2 = ManagedDevice.objects.create(hostname='t-2', ip='10.40.0.2')
        Device.objects.create(ip='10.40.0.1', managed_device=md1, hostname='t-1')
        Device.objects.create(ip='10.40.0.2', managed_device=md2, hostname='t-2')

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
        mock_discovery.side_effect = [None, RuntimeError('boom')]
        result = discover_all_devices_task()
        self.assertEqual(result['success'], 1)
        self.assertEqual(result['failed'], 1)
