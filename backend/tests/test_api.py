from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from app.main import app


class DemoApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._context = TestClient(app)
        cls.client = cls._context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._context.__exit__(None, None, None)

    def test_pipeline_overview(self) -> None:
        response = self.client.get("/api/pipeline/overview")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("Real-time AI training observability", payload["headline"])
        self.assertGreaterEqual(len(payload["stats"]), 5)
        self.assertGreaterEqual(len(payload["active_runs"]), 1)

    def test_pipeline_runs(self) -> None:
        response = self.client.get("/api/pipeline/runs?page=1&page_size=3")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["page_size"], 3)
        self.assertGreaterEqual(len(payload["items"]), 1)
        self.assertGreaterEqual(payload["total"], 1)

    def test_realtime_command_center(self) -> None:
        response = self.client.get("/api/realtime/command-center")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("active_runs", payload)
        self.assertIn("logs", payload)
        self.assertIn("alerts", payload)

    def test_pipeline_repairs_uses_sibling_artifacts(self) -> None:
        response = self.client.get("/api/pipeline/repairs")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["stats"]), 3)
        self.assertIn("repairs", payload)

    def test_realtime_metrics_stream_emits_sse(self) -> None:
        with self.client.stream(
            "GET", "/api/realtime/metrics/stream?once=true"
        ) as response:
            self.assertEqual(response.status_code, 200)
            first_line = ""
            for line in response.iter_lines():
                if line:
                    first_line = line
                    break
            self.assertTrue(first_line.startswith("data: "))
            payload = json.loads(first_line.removeprefix("data: "))
            self.assertEqual(payload["channel"], "metrics")

    def test_openenv_meta(self) -> None:
        response = self.client.get("/api/openenv/meta")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "remorph-openenv")
        self.assertIn("environment_ready", payload)
        self.assertIn("description", payload)


if __name__ == "__main__":
    unittest.main()
