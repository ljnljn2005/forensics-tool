import os
import shutil
import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class WebRegistryScanApiTests(unittest.TestCase):
    def setUp(self):
        self.root = os.path.join(os.getcwd(), "_registry_api_test")
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(self.root, exist_ok=True)
        self.client = TestClient(app)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_registry_scan_api_exists(self):
        response = self.client.post(
            "/api/windows/registry/scan",
            json={"mapping_path": self.root, "scan_item": "default_apps"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["scan_item"], "default_apps")
        self.assertIn("text", payload)


if __name__ == "__main__":
    unittest.main()
