import os
import shutil
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from src.memory_forensics import (
    MemoryForensicsInterface,
    build_memprocfs_command,
    build_vol3_linux_command,
    build_vol3_windows_command,
    load_memory_tool_paths,
    read_csv_rows,
    windows_memory_tasks,
    linux_memory_tasks,
)


class _MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()


class _DummySignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in self._callbacks:
            callback(*args)


class _DummyRunner:
    def __init__(self, mode, payload, parent=None):
        self.mode = mode
        self.payload = payload
        self.parent = parent
        self.finished_signal = _DummySignal()
        self.started = False

    def start(self):
        self.started = True


class MemoryForensicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_root = os.path.join(os.getcwd(), "_memory_forensics_test")
        shutil.rmtree(self.temp_root, ignore_errors=True)
        os.makedirs(self.temp_root, exist_ok=True)
        self.host = _MainWindowStub()

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_load_memory_tool_paths_resolves_relative_paths(self):
        config_dir = os.path.join(self.temp_root, "config")
        tools_dir = os.path.join(self.temp_root, "tools")
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(tools_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "base_config.yaml")
        with open(config_path, "w", encoding="utf-8") as handle:
            handle.write(
                "base_tools:\n"
                "  python310:\n"
                "    path: ../tools/python.exe\n"
                "tools:\n"
                "  memprocfs:\n"
                "    path: ../tools/MemProcFS.exe\n"
                "  volatility3:\n"
                "    path: ../tools/vol.py\n"
                "  volatility3_symbols:\n"
                "    path: ../tools/symbols\n"
            )

        paths = load_memory_tool_paths(self.temp_root)

        self.assertTrue(paths["python310"].endswith("tools\\python.exe"))
        self.assertTrue(paths["memprocfs"].endswith("tools\\MemProcFS.exe"))
        self.assertTrue(paths["volatility3"].endswith("tools\\vol.py"))

    def test_load_memory_tool_paths_supports_bundled_layout_without_config(self):
        memprocfs_dir = os.path.join(self.temp_root, "memprocfs")
        symbols_dir = os.path.join(self.temp_root, "volatility3", "volatility3", "symbols")
        os.makedirs(memprocfs_dir, exist_ok=True)
        os.makedirs(symbols_dir, exist_ok=True)
        with open(os.path.join(memprocfs_dir, "MemProcFS.exe"), "w", encoding="utf-8") as handle:
            handle.write("")
        with open(os.path.join(self.temp_root, "volatility3", "vol.py"), "w", encoding="utf-8") as handle:
            handle.write("")

        paths = load_memory_tool_paths(self.temp_root)

        self.assertTrue(paths["memprocfs"].endswith("memprocfs\\MemProcFS.exe"))
        self.assertTrue(paths["volatility3"].endswith("volatility3\\vol.py"))
        self.assertTrue(paths["volatility3_symbols"].endswith("volatility3\\volatility3\\symbols"))

    def test_build_memory_commands_follow_integrated_style(self):
        paths = {
            "python310": "C:/Tools/python.exe",
            "memprocfs": "C:/Tools/MemProcFS.exe",
            "volatility3": "C:/Tools/vol.py",
            "volatility3_symbols": "C:/Tools/volatility3/symbols",
        }

        memprocfs_cmd = build_memprocfs_command(paths, "D:/mem.raw")
        win_cmd = build_vol3_windows_command(paths, "D:/mem.raw", "pslist", offline=True)
        linux_cmd = build_vol3_linux_command(paths, "D:/mem.raw", "linux.pslist", offline=False)

        self.assertIn("-device", memprocfs_cmd)
        self.assertIn("--offline", win_cmd)
        self.assertIn("--symbol-dirs", win_cmd)
        self.assertIn("windows.pslist", win_cmd)
        self.assertIn("linux.pslist", linux_cmd)

    def test_task_catalogs_include_windows_memprocfs_and_linux_vol3(self):
        win_names = [task["name"] for task in windows_memory_tasks()]
        linux_names = [task["name"] for task in linux_memory_tasks()]

        self.assertIn("加载内存文件系统", win_names)
        self.assertIn("进程列表", win_names)
        self.assertIn("进程列表", linux_names)

    def test_read_csv_rows_parses_headers_and_values(self):
        csv_path = os.path.join(self.temp_root, "process.csv")
        with open(csv_path, "w", encoding="utf-8") as handle:
            handle.write("PID,Name\n4,System\n100,cmd.exe\n")

        rows = read_csv_rows(csv_path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["PID"], "4")
        self.assertEqual(rows[1]["Name"], "cmd.exe")

    def test_memory_interface_exposes_workbench_controls(self):
        widget = MemoryForensicsInterface(self.host, module="windows")

        self.assertEqual(widget.taskList.objectName(), "memoryTaskList")
        self.assertEqual(widget.resultTable.objectName(), "memoryResultTable")
        self.assertEqual(widget.previewPanel.objectName(), "memoryPreviewPanel")
        self.assertNotIn("LovelyMem", widget.toolRootEdit.placeholderText())
        self.assertNotIn("LovelyMem", widget.browseToolRootBtn.text())

    def test_run_volatility_task_starts_background_runner(self):
        widget = MemoryForensicsInterface(self.host, module="linux")
        widget.toolRootEdit.setText(self.temp_root)
        widget.memoryImageEdit.setText("D:/evidence/mem.raw")
        created = []

        def build_runner(mode, payload, parent=None):
            runner = _DummyRunner(mode, payload, parent)
            created.append(runner)
            return runner

        with patch(
            "src.memory_forensics.load_memory_tool_paths",
            return_value={"python310": "python", "volatility3": "vol.py", "memprocfs": "MemProcFS.exe"},
        ), patch(
            "src.memory_forensics.MemoryCommandThread",
            side_effect=build_runner,
        ):
            widget._run_task({"engine": "vol3_linux", "plugin": "linux.pslist", "name": "进程列表", "output": "csv"})

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].mode, "command")
        self.assertTrue(created[0].started)
        self.assertFalse(widget.runTaskBtn.isEnabled())


if __name__ == "__main__":
    unittest.main()
