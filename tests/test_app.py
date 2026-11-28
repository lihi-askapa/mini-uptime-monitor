import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from app import create_app


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "checks.db")
        self.config = {"TESTING": True, "DATABASE": self.path,
                       "TARGETS": {"demo": {"name": "Demo", "url": "https://example.com"}}}
        self.client = create_app(self.config).test_client()

    def tearDown(self):
        self.temp.cleanup()

    def latest(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT status,status_code,error FROM checks ORDER BY id DESC LIMIT 1").fetchone()

    def test_success_persists_across_app_restart(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch("app.urlopen", return_value=response):
            self.assertEqual(self.client.post("/checks", data={"target_id": "demo"}).status_code, 303)
        self.assertEqual(self.latest()[:2], ("up", 200))
        restarted = create_app(self.config).test_client()
        self.assertIn(b"UP", restarted.get("/").data)

    def test_http_error_records_code_without_breaking_app_health(self):
        with patch("app.urlopen", side_effect=HTTPError("https://example.com", 503, "Unavailable", {}, None)):
            self.client.post("/checks", data={"target_id": "demo"})
        self.assertEqual(self.latest()[:2], ("down", 503))
        self.assertEqual(self.client.get("/health").json["status"], "ok")
        self.assertIn(b"503", self.client.get("/").data)

    def test_connection_error_records_no_http_status(self):
        with patch("app.urlopen", side_effect=URLError("timed out")):
            self.client.post("/checks", data={"target_id": "demo"})
        self.assertEqual(self.latest(), ("down", None, "timed out"))

    def test_unknown_target_never_sends_request(self):
        with patch("app.urlopen") as call:
            self.assertEqual(self.client.post("/checks", data={"target_id": "http://localhost"}).status_code, 400)
            call.assert_not_called()

    def test_health_reports_database_failure(self):
        Path(self.path).unlink()
        self.assertEqual(self.client.get("/health").status_code, 503)

    def test_monitor_once_records_every_configured_target(self):
        self.client.application.config["TARGETS"]["second"] = {
            "name": "Second", "url": "https://example.org"}
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch("app.urlopen", return_value=response) as call:
            result = self.client.application.test_cli_runner().invoke(args=["monitor", "--once"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(call.call_count, 2)
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT target_id,status FROM checks ORDER BY id").fetchall()
        self.assertEqual(rows, [("demo", "up"), ("second", "up")])

    def test_monitor_rejects_interval_below_ten_seconds(self):
        with patch("app.urlopen") as call:
            result = self.client.application.test_cli_runner().invoke(args=["monitor", "--interval", "0"])
        self.assertEqual(result.exit_code, 2)
        call.assert_not_called()

    def test_monitoring_health_requires_a_completed_round(self):
        response = self.client.get("/health/monitoring")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["scheduler"], "no_completed_round")
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_monitoring_health_persists_and_expires_even_when_targets_are_down(self):
        with patch("app.urlopen", side_effect=URLError("offline")), patch("app.time.time", return_value=1000):
            result = self.client.application.test_cli_runner().invoke(args=["monitor", "--once"])
        self.assertEqual(result.exit_code, 0, result.output)
        restarted = create_app(self.config).test_client()
        with patch("app.time.time", return_value=1180):
            self.assertEqual(restarted.get("/health/monitoring").status_code, 200)
        with patch("app.time.time", return_value=1181):
            response = restarted.get("/health/monitoring")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["scheduler"], "stale")

    def test_manual_check_does_not_hide_a_stale_scheduler(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch("app.urlopen", return_value=response), patch("app.time.time", return_value=1000):
            result = self.client.application.test_cli_runner().invoke(args=["monitor", "--once"])
        self.assertEqual(result.exit_code, 0, result.output)
        with patch("app.urlopen", return_value=response), patch("app.time.time", return_value=1200):
            self.assertEqual(self.client.post("/checks", data={"target_id": "demo"}).status_code, 303)
            self.assertEqual(self.client.get("/health/monitoring").status_code, 503)

    def test_failed_round_does_not_advance_scheduler_heartbeat(self):
        self.client.application.config["TARGETS"]["second"] = {
            "name": "Second", "url": "https://example.org"}
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO monitor_state VALUES (1,1000)")
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch("app.urlopen", side_effect=[response, RuntimeError("interrupted")]):
            result = self.client.application.test_cli_runner().invoke(args=["monitor", "--once"])
        self.assertNotEqual(result.exit_code, 0)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT completed_at FROM monitor_state").fetchone()[0], 1000)

    def test_monitoring_health_reports_database_failure(self):
        Path(self.path).unlink()
        response = self.client.get("/health/monitoring")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["database"], "unavailable")

    def public_client(self):
        return create_app({**self.config, "PUBLIC_DEMO": True,
                           "SECRET_KEY": "test-only-secret"}).test_client()

    def public_form(self, client):
        client.get("/", base_url="https://demo.example")
        with client.session_transaction(base_url="https://demo.example") as saved:
            token = saved["csrf_token"]
        return {"target_id": "demo", "csrf_token": token}

    def test_public_demo_rejects_missing_form_token(self):
        client = self.public_client()
        with patch("app.urlopen") as call:
            response = client.post("/checks", data={"target_id": "demo"},
                                   base_url="https://demo.example")
        self.assertEqual(response.status_code, 400)
        call.assert_not_called()

    def test_public_cooldown_is_shared_and_expires(self):
        now = time.time()
        first, second = self.public_client(), self.public_client()
        first_form, second_form = self.public_form(first), self.public_form(second)
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch("app.urlopen", return_value=response) as call, patch("app.time.time", return_value=now):
            self.assertEqual(first.post("/checks", data=first_form, base_url="https://demo.example").status_code, 303)
            blocked = second.post("/checks", data=second_form, base_url="https://demo.example")
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers["Retry-After"], "30")
            self.assertEqual(call.call_count, 1)
        with patch("app.urlopen", return_value=response) as call, patch("app.time.time", return_value=now + 31):
            self.assertEqual(second.post("/checks", data=second_form, base_url="https://demo.example").status_code, 303)
            self.assertEqual(call.call_count, 1)

    def test_public_scheduler_does_not_require_form_token(self):
        app = self.public_client().application
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch("app.urlopen", return_value=response) as call:
            result = app.test_cli_runner().invoke(args=["monitor", "--once"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
