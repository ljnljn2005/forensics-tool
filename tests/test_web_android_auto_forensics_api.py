import os
import shutil
import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class WebAndroidAutoForensicsApiTests(unittest.TestCase):
    def setUp(self):
        self.root = os.path.join(os.getcwd(), "_android_api_test")
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "data", "system"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "data", "com.tencent.mm", "MicroMsg"), exist_ok=True)
        with open(os.path.join(self.root, "data", "system", "packages.list"), "w", encoding="utf-8") as handle:
            handle.write("com.tencent.mm 1000 0 /data/user/0/com.tencent.mm default none 0 0 1 @null\n")
        with open(os.path.join(self.root, "data", "com.tencent.mm", "MicroMsg", "note.txt"), "w", encoding="utf-8") as handle:
            handle.write("wechat evidence")
        self.client = TestClient(app)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_android_auto_forensics_api_returns_scan_result(self):
        response = self.client.post(
            "/api/android/auto-forensics/scan",
            json={
                "mapping_path": self.root,
                "entries": [
                    {
                        "group": "微信提取",
                        "name": "MicroMsg",
                        "cmd": "/data/com.tencent.mm/MicroMsg/note.txt",
                        "type": "文件提取",
                        "module": "android",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("com.tencent.mm", payload["installed_packages"])
        self.assertEqual(payload["matched_packages"][0]["package_name"], "com.tencent.mm")


if __name__ == "__main__":
    unittest.main()
