import unittest
from unittest.mock import patch

from backend.app.services.extractor import list_extractor_entries


class ExtractorServiceTests(unittest.TestCase):
    def test_android_auto_plugins_are_excluded_from_android_local_extractor_entries(self):
        payload = {
            "Android Auto Plugin": {
                "package_names": ["com.demo.app"],
                "blocks": [
                    {
                        "name": "Auto DB",
                        "cmd": "/data/user/0/com.demo.app/databases/main.db",
                        "type": "文件提取",
                        "module": "android",
                        "package_name": "com.demo.app",
                    }
                ],
            },
            "Android Local Plugin": {
                "blocks": [
                    {
                        "name": "Media Folder",
                        "cmd": "/sdcard/DCIM",
                        "type": "文件提取",
                        "module": "android",
                    }
                ],
            },
        }

        with patch("backend.app.services.extractor._load_plugin_payload", return_value=payload):
            result = list_extractor_entries("android")

        names = [entry["name"] for entry in result["entries"]]
        self.assertIn("Media Folder", names)
        self.assertNotIn("Auto DB", names)


if __name__ == "__main__":
    unittest.main()
