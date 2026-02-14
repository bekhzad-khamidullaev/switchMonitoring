from unittest.mock import patch

from django.test import SimpleTestCase


class AppMetricsEndpointTests(SimpleTestCase):
    @patch("config.metrics.get_metrics_snapshot")
    def test_metrics_endpoint_returns_snapshot(self, mock_snapshot):
        mock_snapshot.return_value = {
            "poll": {"total": 5, "avg_duration_ms": 123.4, "samples_total": 50, "snmp_errors_total": 1},
            "celery": {"queue_depth": {"active": 1, "reserved": 2, "scheduled": 3}},
        }

        response = self.client.get("/metrics/app/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["poll"]["total"], 5)
