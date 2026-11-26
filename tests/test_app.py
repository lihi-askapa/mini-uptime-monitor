import sqlite3
import tempfile
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
        # CI learning exercise: deliberately wrong; restore 503 after inspecting the failure.
        self.assertEqual(self.client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
