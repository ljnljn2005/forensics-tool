import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class WebBackendHealthTests(unittest.TestCase):
    def test_health_endpoint_returns_ok(self):
        client = TestClient(app)

        response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})


if __name__ == "__main__":
    unittest.main()
