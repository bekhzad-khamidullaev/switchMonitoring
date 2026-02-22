import os
from unittest.mock import patch

from django.test import SimpleTestCase

from config.settings.components import load_host_config, load_metrics_config


class HostConfigTests(SimpleTestCase):
    def test_auto_builds_csrf_origins_from_allowed_hosts(self):
        env = {
            'ALLOWED_HOSTS': 'example.com,localhost,127.0.0.1',
            'CSRF_TRUSTED_ORIGINS': '',
            'HOST_AUTO_TRUST_CSRF_FROM_ALLOWED_HOSTS': '1',
            'HOST_TRUST_CSRF_HTTP_FOR_LOCALHOST': '1',
        }
        with patch.dict(os.environ, env, clear=False):
            host_config = load_host_config(env_name='dev')

        self.assertEqual(host_config.allowed_hosts, ['example.com', 'localhost', '127.0.0.1'])
        self.assertIn('https://example.com', host_config.csrf_trusted_origins)
        self.assertIn('http://localhost', host_config.csrf_trusted_origins)
        self.assertIn('http://127.0.0.1', host_config.csrf_trusted_origins)

    def test_prod_rejects_wildcard_hosts(self):
        env = {
            'ALLOWED_HOSTS': '*',
            'ALLOW_WILDCARD_HOSTS_IN_PROD': '0',
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaises(RuntimeError):
                load_host_config(env_name='prod')


class MetricsConfigTests(SimpleTestCase):
    def test_loads_metrics_limits_and_retention(self):
        env = {
            'POLL_ALL_DEVICES_INTERVAL_SEC': '120',
            'POLL_ALL_DEVICES_ASYNC_DISPATCH': '0',
            'POLL_BATCH_SIZE': '123',
            'POLL_MAX_QUEUE_DEPTH': '4321',
            'DISCOVERY_BATCH_SIZE': '55',
            'DISCOVERY_MAX_QUEUE_DEPTH': '333',
            'METRIC_SAMPLE_RETENTION_ENABLED': '1',
            'METRIC_SAMPLE_RETENTION_DAYS': '45',
            'METRIC_SAMPLE_RETENTION_BATCH_SIZE': '4000',
            'METRIC_SAMPLE_RETENTION_MAX_BATCHES': '5',
            'METRIC_SAMPLE_RETENTION_HOUR': '3',
            'METRIC_SAMPLE_RETENTION_MINUTE': '11',
            'AUTOPROVISION_ENABLED': '1',
            'AUTOPROVISION_HOUR': '4',
            'AUTOPROVISION_MINUTE': '12',
            'AUTOPROVISION_ASSIGN_PROFILES': '0',
        }
        with patch.dict(os.environ, env, clear=False):
            metrics_config = load_metrics_config()

        self.assertEqual(metrics_config.poll_interval_sec, 120)
        self.assertFalse(metrics_config.poll_async_dispatch)
        self.assertEqual(metrics_config.poll_batch_size, 123)
        self.assertEqual(metrics_config.discovery_batch_size, 55)
        self.assertEqual(metrics_config.discovery_max_queue_depth, 333)
        self.assertTrue(metrics_config.retention_enabled)
        self.assertEqual(metrics_config.retention_days, 45)
        self.assertEqual(metrics_config.retention_minute, 11)
        self.assertTrue(metrics_config.autoprovision_enabled)
        self.assertEqual(metrics_config.autoprovision_hour, '4')
        self.assertEqual(metrics_config.autoprovision_minute, 12)
        self.assertFalse(metrics_config.autoprovision_assign_profiles)
