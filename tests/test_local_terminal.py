import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.local_terminal import LocalTerminalInterface, LocalTerminalWindow, build_shell_command


class _DummySignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in self._callbacks:
            callback(*args)


class _DummyRunner:
    def __init__(self, argv, parent=None):
        self.argv = argv
        self.parent = parent
        self.line_signal = _DummySignal()
        self.finished_signal = _DummySignal()
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class LocalTerminalInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_build_shell_command_uses_argv_per_shell(self):
        self.assertEqual(build_shell_command("cmd", "echo hi"), ["cmd.exe", "/c", "echo hi"])
        self.assertEqual(
            build_shell_command("powershell", "Get-ChildItem"),
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Get-ChildItem"],
        )
        self.assertEqual(build_shell_command("wsl", "ls -la"), ["wsl", "sh", "-lc", "ls -la"])

    def test_interactive_terminal_window_is_top_level(self):
        widget = LocalTerminalInterface()

        self.assertIsInstance(widget.terminal_window, LocalTerminalWindow)
        self.assertIsNone(widget.terminal_window.parent())
        self.assertTrue(widget.terminal_window.isWindow())

    def test_workbench_layout_exposes_toolbar_table_and_preview(self):
        widget = LocalTerminalInterface()

        self.assertEqual(widget.pluginList.objectName(), "localTerminalPluginList")
        self.assertEqual(widget.blockTable.objectName(), "localTerminalBlockTable")
        self.assertEqual(widget.previewPanel.objectName(), "localTerminalPreviewPanel")
        self.assertEqual(widget.refreshBtn.text(), "刷新插件")
        self.assertEqual(widget.openTerminalBtn.text(), "打开交互终端")
        self.assertEqual(widget.clearOutputBtn.text(), "清空输出")
        self.assertEqual(widget.copyOutputBtn.text(), "复制输出")

    def test_run_command_starts_background_runner_and_updates_controls(self):
        widget = LocalTerminalInterface()
        widget.cmdEdit.setText("echo hello")

        created = []

        def build_runner(argv, parent=None):
            runner = _DummyRunner(argv, parent)
            created.append(runner)
            return runner

        with patch("src.local_terminal.CommandRunnerThread", side_effect=build_runner):
            widget.run_command()

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].argv, ["cmd.exe", "/c", "echo hello"])
        self.assertIs(widget.thread, created[0])
        self.assertTrue(created[0].started)
        self.assertFalse(widget.runBtn.isEnabled())
        self.assertTrue(widget.stopBtn.isEnabled())
        self.assertIn(">>> 执行:", widget.command_output.textEdit.toPlainText())

    def test_command_finish_restores_controls(self):
        widget = LocalTerminalInterface()
        widget.cmdEdit.setText("echo hello")

        with patch("src.local_terminal.CommandRunnerThread", side_effect=lambda argv, parent=None: _DummyRunner(argv, parent)):
            widget.run_command()
            widget.thread.finished_signal.emit(0)

        self.assertIsNone(widget.thread)
        self.assertTrue(widget.runBtn.isEnabled())
        self.assertFalse(widget.stopBtn.isEnabled())
        self.assertIn("退出码=0", widget.command_output.textEdit.toPlainText())

    def test_selecting_plugin_filters_block_table(self):
        widget = LocalTerminalInterface()
        widget.plugins_data = {
            "Plugin A": {
                "blocks": [
                    {"name": "Local One", "cmd": "echo a", "module": "local", "type": "SSH命令"},
                    {"name": "Remote One", "cmd": "uname -a", "module": "linux", "type": "SSH命令"},
                ]
            },
            "Plugin B": {
                "blocks": [
                    {"name": "Local Two", "cmd": "echo b", "module": "all", "type": "SSH命令"},
                ]
            },
        }
        widget.pluginList.clear()
        widget.pluginList.addItem("Plugin A")
        widget.pluginList.addItem("Plugin B")

        widget.on_plugin_selected(widget.pluginList.item(1))

        self.assertEqual(widget.blockTable.rowCount(), 1)
        self.assertEqual(widget.blockTable.item(0, 0).text(), "Local Two")
        self.assertEqual(widget.blockTable.item(0, 3).text(), "Plugin B")

    def test_run_selected_plugin_without_selected_plugin_shows_message(self):
        widget = LocalTerminalInterface()
        widget.blockTable.setRowCount(0)
        widget._plugin_entries = []

        with patch("src.local_terminal.InfoBar.info") as info_mock:
            widget.run_selected_plugin()

        info_mock.assert_called_once()
        self.assertIn("请选择", info_mock.call_args.args[1])

    def test_file_block_renders_offline_forensics_guidance(self):
        widget = LocalTerminalInterface()
        widget.plugins_data = {
            "Plugin A": {
                "blocks": [
                    {"name": "File Block", "cmd": "C:\\evidence\\test", "module": "local", "type": "文件提取"}
                ]
            }
        }
        widget.pluginList.clear()
        widget.pluginList.addItem("Plugin A")
        widget.pluginList.setCurrentRow(0)

        widget.extract_local_info()

        self.assertIn("文件提取型积木", widget.previewTitle.text())
        text = widget.previewOutput.textEdit.toPlainText()
        self.assertIn("不会在本地终端直接执行", text)

    def test_selecting_table_row_updates_preview_panel(self):
        widget = LocalTerminalInterface()
        widget.plugins_data = {
            "Plugin A": {
                "blocks": [
                    {"name": "Local One", "cmd": "echo a", "module": "local", "type": "SSH命令"},
                ]
            }
        }
        widget.pluginList.clear()
        widget.pluginList.addItem("Plugin A")

        widget.on_plugin_selected(widget.pluginList.item(0))
        widget.blockTable.selectRow(0)
        widget.on_block_selection_changed()

        self.assertIn("Local One", widget.previewTitle.text())
        self.assertIn("echo a", widget.previewOutput.textEdit.toPlainText())


if __name__ == "__main__":
    unittest.main()
