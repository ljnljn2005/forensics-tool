import os
import shutil
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem, QWidget

from src.extractor import (
    ExtractorInterface,
    collect_android_installed_packages,
    collect_android_template_packages,
)


class _MainWindowStub(QWidget):
    def __init__(self, mapping_path=""):
        super().__init__()
        self.mapping_path = mapping_path


class ExtractorInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = _MainWindowStub()

    def test_workbench_layout_exposes_toolbar_table_and_preview(self):
        widget = ExtractorInterface(self.host)

        self.assertEqual(widget.extractorPluginList.objectName(), "extractorPluginList")
        self.assertEqual(widget.blockTable.objectName(), "extractorBlockTable")
        self.assertEqual(widget.previewPanel.objectName(), "extractorPreviewPanel")
        self.assertEqual(widget.scanButton.text(), "扫描并加载")
        self.assertEqual(widget.useSavedPathBtn.text(), "使用主页映射路径")
        self.assertEqual(widget.copyOutputBtn.text(), "复制结果")

    def test_android_auto_mode_updates_title_and_scan_button(self):
        widget = ExtractorInterface(self.host, initial_module="android", show_module_bar=False, auto_analyze_mode=True)

        self.assertIn("Android", widget.titleLabel.text())
        self.assertIn("自动取证", widget.titleLabel.text())
        self.assertEqual(widget.scanButton.text(), "扫描应用并自动分析")

    def test_populate_plugins_filters_by_module_and_file_type(self):
        widget = ExtractorInterface(self.host)
        payload = {
            "Windows Group": {
                "blocks": [
                    {"name": "Registry", "cmd": "/Windows/System32/config/SOFTWARE", "module": "windows", "type": "文件提取"},
                    {"name": "Cmd", "cmd": "dir", "module": "windows", "type": "SSH命令"},
                ]
            },
            "Linux Group": {
                "blocks": [
                    {"name": "Shadow", "cmd": "/etc/shadow", "module": "linux", "type": "文件提取"},
                ]
            },
        }
        widget.current_module = "windows"

        with patch("src.extractor.json.load", return_value=payload), patch("builtins.open"):
            widget.populate_extractor_plugins()

        self.assertEqual(widget.extractorPluginList.count(), 1)
        self.assertEqual(widget.blockTable.rowCount(), 1)
        self.assertIn("Windows", widget.pluginSummaryLabel.text())
        self.assertEqual(widget.blockTable.item(0, 0).text(), "Registry")

    def test_module_change_updates_workbench_title(self):
        widget = ExtractorInterface(self.host)

        widget.on_module_changed("windows")

        self.assertEqual(widget.current_module, "windows")
        self.assertIn("Windows", widget.titleLabel.text())

    def test_selecting_plugin_updates_preview_panel(self):
        widget = ExtractorInterface(self.host)
        item = QListWidgetItem("Windows Group - Registry")
        item.setData(
            Qt.UserRole,
            {"group": "Windows Group", "name": "Registry", "cmd": "/Windows/System32/config/SOFTWARE", "type": "文件提取"},
        )
        widget.extractorPluginList.addItem(item)
        widget._plugin_entries = [item.data(Qt.UserRole)]
        widget._render_block_table(widget._plugin_entries)

        widget.extractorPluginList.setCurrentItem(item)
        widget.on_extractor_plugin_clicked(item)

        self.assertIn("Registry", widget.previewTitle.text())
        self.assertIn("/Windows/System32/config/SOFTWARE", widget.previewOutput.textEdit.toPlainText())

    def test_extract_all_reports_invalid_mapping_path(self):
        self.host.mapping_path = "Z:/not-found"
        widget = ExtractorInterface(self.host)

        widget.extract_all()

        self.assertIn("无效路径", widget.previewOutput.textEdit.toPlainText())

    def test_run_block_item_writes_execution_result_to_preview(self):
        temp_dir = os.path.join(os.getcwd(), "_extractor_test_data")
        try:
            os.makedirs(temp_dir, exist_ok=True)
            target = os.path.join(temp_dir, "note.txt")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("hello evidence")

            self.host.mapping_path = temp_dir
            widget = ExtractorInterface(self.host)
            item = QListWidgetItem("Local Group - Note")
            item.setData(Qt.UserRole, {"group": "Local Group", "name": "Note", "cmd": "note.txt", "type": "文件提取"})

            widget.run_block_item(item)

            self.assertIn("hello evidence", widget.previewOutput.textEdit.toPlainText())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_collect_android_template_packages_extracts_package_names(self):
        entries = [
            {"group": "微信", "name": "数据库", "cmd": "/data/com.tencent.mm/MicroMsg", "type": "文件提取", "module": "android"},
            {"group": "小米便签", "name": "数据库", "cmd": "/data/data/com.miui.notes/databases", "type": "文件提取", "module": "android"},
        ]

        packages = collect_android_template_packages(entries)

        self.assertEqual(packages["com.tencent.mm"][0]["group"], "微信")
        self.assertEqual(packages["com.miui.notes"][0]["group"], "小米便签")

    def test_collect_android_installed_packages_reads_packages_list_and_data_dirs(self):
        temp_dir = os.path.join(os.getcwd(), "_extractor_android_scan")
        try:
            os.makedirs(os.path.join(temp_dir, "data", "system"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "data", "data", "com.miui.notes"), exist_ok=True)
            with open(os.path.join(temp_dir, "data", "system", "packages.list"), "w", encoding="utf-8") as handle:
                handle.write("com.tencent.mm 10345 0 /data/user/0/com.tencent.mm default:targetSdkVersion=33 none 0 0 1 @null\n")

            packages = collect_android_installed_packages(temp_dir)

            self.assertIn("com.tencent.mm", packages)
            self.assertIn("com.miui.notes", packages)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extract_all_android_auto_analyzes_matching_apps(self):
        temp_dir = os.path.join(os.getcwd(), "_extractor_android_auto")
        try:
            os.makedirs(os.path.join(temp_dir, "data", "system"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "data", "com.tencent.mm", "MicroMsg"), exist_ok=True)
            with open(os.path.join(temp_dir, "data", "system", "packages.list"), "w", encoding="utf-8") as handle:
                handle.write("com.tencent.mm 10345 0 /data/user/0/com.tencent.mm default:targetSdkVersion=33 none 0 0 1 @null\n")
            with open(os.path.join(temp_dir, "data", "com.tencent.mm", "MicroMsg", "note.txt"), "w", encoding="utf-8") as handle:
                handle.write("wechat evidence")

            self.host.mapping_path = temp_dir
            widget = ExtractorInterface(self.host, initial_module="android", show_module_bar=False, auto_analyze_mode=True)
            payload = {
                "微信提取": {
                    "blocks": [
                        {
                            "name": "MicroMsg",
                            "cmd": "/data/com.tencent.mm/MicroMsg/note.txt",
                            "type": "文件提取",
                            "module": "android",
                        }
                    ]
                }
            }

            with patch.object(widget, "_load_plugin_payload", return_value=payload):
                widget.populate_extractor_plugins()
                widget.extract_all()

            text = widget.previewOutput.textEdit.toPlainText()
            self.assertIn("已安装应用扫描结果", text)
            self.assertIn("com.tencent.mm", text)
            self.assertIn("微信提取", text)
            self.assertIn("wechat evidence", text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
