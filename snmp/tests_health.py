from unittest.mock import patch

from django.test import SimpleTestCase


class HealthEndpointTests(SimpleTestCase):
    @patch("config.health._check_db", return_value=(True, "ok"))
    @patch("config.health._check_redis", return_value=(True, "ok"))
    @patch("config.health._check_celery", return_value=(True, "ok"))
    def test_healthz_returns_200_when_all_checks_ok(self, *_):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("config.health._check_db", return_value=(True, "ok"))
    @patch("config.health._check_redis", return_value=(False, "redis down"))
    @patch("config.health._check_celery", return_value=(True, "ok"))
    def test_healthz_returns_503_when_any_check_fails(self, *_):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["checks"]["redis"]["ok"])
