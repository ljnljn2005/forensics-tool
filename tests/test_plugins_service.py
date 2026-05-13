import unittest

from backend.app.services.plugins import is_android_auto_plugin, normalize_plugin


class PluginServiceTests(unittest.TestCase):
    def test_normalize_plugin_derives_android_package_names(self):
        plugin = normalize_plugin(
            {
                "name": "微信取证插件",
                "blocks": [
                    {
                        "name": "MicroMsg",
                        "cmd": "/data/com.tencent.mm/MicroMsg",
                        "type": "文件提取",
                        "module": "android",
                    }
                ],
            }
        )

        self.assertEqual(plugin["package_names"], ["com.tencent.mm"])
        self.assertIn("android", plugin["detected_modules"])

    def test_is_android_auto_plugin_detects_package_rules(self):
        plugin = normalize_plugin(
            {
                "name": "Android Auto",
                "blocks": [
                    {
                        "name": "db",
                        "cmd": "/data/user/0/com.demo.app/databases/main.db",
                        "type": "文件提取",
                        "module": "android",
                        "package_name": "com.demo.app",
                    }
                ],
            }
        )

        self.assertTrue(is_android_auto_plugin(plugin))


if __name__ == "__main__":
    unittest.main()
