import unittest

from backend.app.services.registry_scan import build_registry_scan_response


class RegistryScanServiceTests(unittest.TestCase):
    def test_build_registry_scan_response_wraps_text_result(self):
        result = build_registry_scan_response("default_apps", "scan output")

        self.assertEqual(result["scan_item"], "default_apps")
        self.assertEqual(result["text"], "scan output")


if __name__ == "__main__":
    unittest.main()
