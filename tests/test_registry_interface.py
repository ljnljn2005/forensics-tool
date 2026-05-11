import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.registry_interface import RegistryScanInterface


class RegistryScanInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_load_search_items_includes_builtin_and_plugin_registry_items(self):
        widget = RegistryScanInterface()
        widget.plugins_data = {
            "Win": {
                "blocks": [
                    {
                        "name": "Run Keys",
                        "cmd": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                        "type": "注册表查找",
                        "module": "windows",
                    }
                ]
            }
        }

        widget.load_search_items()

        labels = [widget.itemList.item(i).text() for i in range(widget.itemList.count())]
        self.assertIn("内置 - 默认应用", labels)
        self.assertIn("Win - Run Keys", labels)

    def test_run_builtin_default_apps_displays_report(self):
        widget = RegistryScanInterface()
        widget.mappingPathEdit.setText(r"C:\mount")
        widget.load_search_items()
        widget.itemList.setCurrentRow(0)

        with patch("src.registry_interface.lookup_default_apps_report", return_value="默认应用报告"):
            widget.run_selected_item()

        self.assertIn("默认应用报告", widget.resultViewer.textEdit.toPlainText())

    def test_run_plugin_item_queries_registry_path(self):
        widget = RegistryScanInterface()
        widget.mappingPathEdit.setText(r"C:\mount")
        widget.plugins_data = {
            "Win": {
                "blocks": [
                    {
                        "name": "Run Keys",
                        "cmd": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                        "type": "注册表查找",
                        "module": "windows",
                    }
                ]
            }
        }
        widget.load_search_items()
        widget.itemList.setCurrentRow(1)

        with patch("src.registry_interface.query_registry_path_report", return_value="Run Keys 报告") as query:
            widget.run_selected_item()

        query.assert_called_once_with(r"C:\mount", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run")
        self.assertIn("Run Keys 报告", widget.resultViewer.textEdit.toPlainText())


if __name__ == "__main__":
    unittest.main()
