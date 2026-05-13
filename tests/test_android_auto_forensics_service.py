import os
import shutil
import unittest

from backend.app.services.android_auto_forensics import scan_android_apps
from src.constants import PLUGINS_DIR, SETTINGS_DIR, save_app_settings
from src.extractor import collect_android_installed_packages, resolve_android_entry_candidates


class AndroidAutoForensicsServiceTests(unittest.TestCase):
    def setUp(self):
        self.root = os.path.join(os.getcwd(), "_android_service_test")
        self.plugin_path = os.path.join(PLUGINS_DIR, "AndroidAutoForensicsTestPlugin.json")
        self.settings_path = os.path.join(SETTINGS_DIR, "app_settings.json")
        self._settings_backup = None
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r", encoding="utf-8") as handle:
                self._settings_backup = handle.read()
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "data", "system"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "data", "user", "0", "com.tencent.mm", "MicroMsg"), exist_ok=True)
        with open(os.path.join(self.root, "data", "system", "packages.list"), "w", encoding="utf-8") as handle:
            handle.write("com.tencent.mm 1000 0 /data/user/0/com.tencent.mm default none 0 0 1 @null\n")
        with open(os.path.join(self.root, "data", "user", "0", "com.tencent.mm", "MicroMsg", "note.txt"), "w", encoding="utf-8") as handle:
            handle.write("wechat evidence")
        save_app_settings({"android_system_roots": ["/data/user/0", "/data/data"]})

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        if os.path.exists(self.plugin_path):
            os.remove(self.plugin_path)
        if self._settings_backup is None:
            if os.path.exists(self.settings_path):
                os.remove(self.settings_path)
        else:
            with open(self.settings_path, "w", encoding="utf-8") as handle:
                handle.write(self._settings_backup)

    def test_scan_android_apps_returns_installed_and_matched_packages(self):
        entries = [
            {
                "group": "WeChat Extractor",
                "name": "MicroMsg",
                "cmd": "/MicroMsg/note.txt",
                "type": "文件提取",
                "module": "android",
                "package_name": "com.tencent.mm",
            }
        ]

        result = scan_android_apps(self.root, entries)

        self.assertIn("com.tencent.mm", result["installed_packages"])
        self.assertEqual(result["matched_packages"][0]["package_name"], "com.tencent.mm")
        self.assertEqual(result["matched_packages"][0]["entries"][0]["result"], "wechat evidence")
        self.assertEqual(
            result["matched_packages"][0]["entries"][0]["resolved_path"],
            os.path.normpath(os.path.join(self.root, "data", "user", "0", "com.tencent.mm", "MicroMsg", "note.txt")),
        )

    def test_scan_android_apps_uses_installed_android_plugins_when_entries_empty(self):
        with open(self.plugin_path, "w", encoding="utf-8") as handle:
            handle.write(
                """
{
  "name": "Android Auto Forensics Test Plugin",
  "author": "test",
  "description": "test plugin",
  "package_names": ["com.tencent.mm"],
  "blocks": [
    {
      "name": "MicroMsg",
      "cmd": "/MicroMsg/note.txt",
      "type": "文件提取",
      "module": "android",
      "package_name": "com.tencent.mm"
    }
  ]
}
                """.strip()
            )

        result = scan_android_apps(self.root, [])

        self.assertEqual(result["matched_packages"][0]["package_name"], "com.tencent.mm")
        self.assertEqual(result["matched_packages"][0]["entries"][0]["result"], "wechat evidence")

    def test_collect_android_installed_packages_ignores_permission_names_in_packages_xml(self):
        packages_xml_path = os.path.join(self.root, "data", "system", "packages.xml")
        with open(packages_xml_path, "w", encoding="utf-8") as handle:
            handle.write(
                """
<packages>
  <package name="com.tencent.mm" />
  <perms>
    <item name="android.providers.downloads.permission.MIPUSH_RECEIVE" />
  </perms>
</packages>
                """.strip()
            )

        packages = collect_android_installed_packages(self.root)

        self.assertIn("com.tencent.mm", packages)
        self.assertNotIn("android.providers.downloads.permission.MIPUSH_RECEIVE", packages)

    def test_resolve_android_entry_candidates_uses_mapping_system_package_and_plugin_segments(self):
        candidates = resolve_android_entry_candidates(self.root, "com.tencent.mm", "/MicroMsg/note.txt")

        self.assertIn(
            os.path.normpath(os.path.join(self.root, "data", "user", "0", "com.tencent.mm", "MicroMsg", "note.txt")),
            candidates,
        )

    def test_resolve_android_entry_candidates_strips_full_prefix_path(self):
        candidates = resolve_android_entry_candidates(
            self.root,
            "com.baidu.input_mi",
            "/data/user/0/com.baidu.input_mi/databases/clipborad_records.db",
        )

        self.assertEqual(
            candidates[0],
            os.path.normpath(
                os.path.join(
                    self.root,
                    "data",
                    "user",
                    "0",
                    "com.baidu.input_mi",
                    "databases",
                    "clipborad_records.db",
                )
            ),
        )


if __name__ == "__main__":
    unittest.main()
