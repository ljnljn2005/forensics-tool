import os
import unittest

from backend.app.services.cases import delete_case, list_cases, save_case, select_case
from src.constants import SETTINGS_DIR


class CasesServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings_path = os.path.join(SETTINGS_DIR, "app_settings.json")
        self._backup = None
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r", encoding="utf-8") as handle:
                self._backup = handle.read()
        if os.path.exists(self.settings_path):
            os.remove(self.settings_path)

    def tearDown(self):
        if self._backup is None:
            if os.path.exists(self.settings_path):
                os.remove(self.settings_path)
        else:
            with open(self.settings_path, "w", encoding="utf-8") as handle:
                handle.write(self._backup)

    def test_save_case_sets_first_case_as_current(self):
        payload = save_case(
            {
                "name": "Case A",
                "evidence_items": [{"type": "windows", "label": "分区1", "path": "C:/case-a/windows"}],
                "ssh": {"host": "10.0.0.5", "port": 22, "user": "root", "password": "pw"},
            }
        )

        self.assertEqual(len(payload["cases"]), 1)
        self.assertEqual(payload["current_case"]["name"], "Case A")
        self.assertEqual(payload["current_case"]["evidence_paths"]["windows"], "C:/case-a/windows")
        self.assertEqual(payload["current_case"]["evidence_items"][0]["label"], "分区1")

    def test_select_case_switches_current_case(self):
        first = save_case({"name": "Case A"})["cases"][0]
        second = save_case({"name": "Case B"})["cases"][1]

        payload = select_case(second["id"])

        self.assertEqual(payload["current_case_id"], second["id"])
        self.assertEqual(payload["current_case"]["name"], "Case B")
        self.assertNotEqual(payload["current_case_id"], first["id"])

    def test_delete_current_case_falls_back_to_remaining_case(self):
        first = save_case({"name": "Case A"})["cases"][0]
        second = save_case({"name": "Case B"})["cases"][1]
        select_case(second["id"])

        payload = delete_case(second["id"])

        self.assertEqual(payload["current_case_id"], first["id"])
        self.assertEqual(payload["current_case"]["name"], "Case A")
        self.assertEqual(len(list_cases()["cases"]), 1)

    def test_legacy_evidence_paths_are_migrated_to_evidence_items(self):
        payload = save_case({"name": "Legacy", "evidence_paths": {"android": "D:/android.tar"}})
        current_case = payload["current_case"]

        self.assertEqual(current_case["evidence_paths"]["android"], "D:/android.tar")
        self.assertEqual(current_case["evidence_items"][0]["type"], "android")
        self.assertEqual(current_case["evidence_items"][0]["path"], "D:/android.tar")


if __name__ == "__main__":
    unittest.main()
