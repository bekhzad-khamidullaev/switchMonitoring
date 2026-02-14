from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from snmp.models import Device, Interface, MetricDefinition, MetricSample, MetricSubscription, Switch


class EndpointAccessTests(TestCase):
    def setUp(self):
        self.switch = Switch.objects.create(hostname='sw-test', ip='10.0.0.1')
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
        response = self.client.get(reverse('update_optical_info', args=[self.switch.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertIn('Method Not Allowed', response.content.decode('utf-8'))


class MetricsPageActionTests(TestCase):
    def setUp(self):
        self.switch = Switch.objects.create(hostname='sw-metrics', ip='10.0.0.50')
        self.user = User.objects.create_user(username='metrics_user', password='p1')
        change_device_perm = Permission.objects.get(codename='change_device')
        self.user.user_permissions.add(change_device_perm)
        self.client.login(username='metrics_user', password='p1')

    @patch('snmp.views.metrics_views.run_device_discovery')
    def test_run_discovery_action(self, mock_discovery):
        mock_discovery.return_value = {'interfaces_count': 2, 'profile_id': 10}
        response = self.client.post(
            reverse('switch_metrics', args=[self.switch.pk]),
            data={'action': 'run_discovery', 'community': 'public'},
        )
        self.assertEqual(response.status_code, 302)
        mock_discovery.assert_called_once()

    @patch('snmp.views.metrics_views.poll_device_metrics')
    def test_poll_now_action(self, mock_poll):
        mock_poll.return_value = 3
        response = self.client.post(
            reverse('switch_metrics', args=[self.switch.pk]),
            data={'action': 'poll_now'},
        )
        self.assertEqual(response.status_code, 302)
        mock_poll.assert_called_once()

    def test_export_device_metrics_csv(self):
        view_sample_perm = Permission.objects.get(codename='view_metricsample')
        self.user.user_permissions.add(view_sample_perm)

        device = Device.objects.create(ip='10.0.0.50', switch=self.switch, hostname='sw-metrics')
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

        response = self.client.get(reverse('export_device_metrics_csv', args=[self.switch.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        csv_payload = response.content.decode('utf-8')
        self.assertIn('metric,if_index,value_float', csv_payload)
        self.assertIn('rx_power_dbm_t', csv_payload)
