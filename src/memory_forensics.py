import csv
import io
import locale
import os
import subprocess
import sys

import yaml
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QListWidgetItem,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CheckBox, LineEdit, ListWidget, PrimaryPushButton, PushButton, SubtitleLabel

from .constants import BASE_DIR, get_app_settings, save_app_settings
from .widgets import SearchableTextEdit


BUNDLED_MEMORY_TOOL_ROOT = os.path.join(BASE_DIR, "tools", "memory")


def _first_existing_path(*candidates: str) -> str:
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return os.path.abspath(candidate)
    return ""


def _resolve_python_runtime(root: str) -> str:
    bundled_python = _first_existing_path(
        os.path.join(root, "python3", "python.exe"),
        os.path.join(root, "python", "python.exe"),
    )
    if bundled_python:
        return bundled_python
    return sys.executable


def _resolve_from_config(root: str) -> dict:
    config_path = os.path.join(root or "", "config", "base_config.yaml")
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    def resolve(rel_path: str) -> str:
        if not rel_path:
            return ""
        return os.path.abspath(os.path.join(root, rel_path))

    return {
        "python310": resolve(data.get("base_tools", {}).get("python310", {}).get("path", "")),
        "memprocfs": resolve(data.get("tools", {}).get("memprocfs", {}).get("path", "")),
        "volatility3": resolve(data.get("tools", {}).get("volatility3", {}).get("path", "")),
        "volatility3_symbols": resolve(data.get("tools", {}).get("volatility3_symbols", {}).get("path", "")),
    }


def bundled_memory_tool_root() -> str:
    return BUNDLED_MEMORY_TOOL_ROOT


def is_memory_tool_root(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    tool_paths = load_memory_tool_paths(path)
    return bool(tool_paths.get("memprocfs") or tool_paths.get("volatility3"))


def default_memory_tool_root() -> str:
    saved = ""
    try:
        settings = get_app_settings()
        saved = settings.get("memory_tools_root", "") or settings.get("lovelymem_root", "")
    except Exception:
        saved = ""

    bundled = bundled_memory_tool_root()
    if is_memory_tool_root(bundled):
        return bundled
    if is_memory_tool_root(saved):
        return saved
    return ""


def load_memory_tool_paths(root: str) -> dict:
    root = os.path.abspath(root) if root else ""

    bundled_paths = {
        "python310": _resolve_python_runtime(root),
        "memprocfs": _first_existing_path(
            os.path.join(root, "memprocfs", "MemProcFS.exe"),
            os.path.join(root, "MemProcFS.exe"),
        ),
        "volatility3": _first_existing_path(
            os.path.join(root, "volatility3", "vol.py"),
            os.path.join(root, "vol.py"),
        ),
        "volatility3_symbols": _first_existing_path(
            os.path.join(root, "volatility3", "volatility3", "symbols"),
            os.path.join(root, "volatility3", "symbols"),
            os.path.join(root, "symbols"),
        ),
    }

    config_paths = _resolve_from_config(root)
    merged = dict(bundled_paths)
    for key, value in config_paths.items():
        if value:
            merged[key] = value
    return merged


def build_memprocfs_command(paths: dict, memory_image: str) -> list[str]:
    return [
        paths.get("memprocfs", ""),
        "-device",
        memory_image,
        "-v",
        "-license-accept-elastic-license-2-0",
        "-forensic",
        "1",
    ]


def build_vol3_windows_command(paths: dict, memory_image: str, plugin: str, offline: bool = False) -> list[str]:
    command = [
        paths.get("python310", sys.executable),
        paths.get("volatility3", ""),
        "-f",
        memory_image,
    ]
    symbol_dir = paths.get("volatility3_symbols", "")
    if symbol_dir:
        command.extend(["--symbol-dirs", symbol_dir])
    if offline:
        command.append("--offline")
    renderer = "quick" if plugin in {"hashdump", "lsadump", "cachedump", "truecrypt"} else "csv"
    command.extend(["-r", renderer, f"windows.{plugin}"])
    return command


def build_vol3_linux_command(paths: dict, memory_image: str, plugin: str, offline: bool = False) -> list[str]:
    command = [
        paths.get("python310", sys.executable),
        paths.get("volatility3", ""),
        "-f",
        memory_image,
    ]
    symbol_dir = paths.get("volatility3_symbols", "")
    if symbol_dir:
        command.extend(["--symbol-dirs", symbol_dir])
    if offline:
        command.append("--offline")
    command.extend(["-r", "quick" if plugin == "linux.psaux" else "csv", plugin])
    return command


def windows_memory_tasks() -> list[dict]:
    return [
        {"name": "加载内存文件系统", "engine": "memprocfs_mount", "output": "text"},
        {"name": "进程列表", "engine": "memprocfs_csv", "result_path": r"M:\forensic\csv\process.csv", "output": "csv"},
        {"name": "网络连接", "engine": "memprocfs_csv", "result_path": r"M:\forensic\csv\net.csv", "output": "csv"},
        {"name": "句柄列表", "engine": "memprocfs_csv", "result_path": r"M:\forensic\csv\handles.csv", "output": "csv"},
        {"name": "系统信息", "engine": "memprocfs_text", "result_path": r"M:\sys\sysinfo\sysinfo.txt", "output": "text"},
        {"name": "进程列表（高级引擎）", "engine": "vol3_windows", "plugin": "pslist", "output": "csv"},
        {"name": "进程树（高级引擎）", "engine": "vol3_windows", "plugin": "pstree", "output": "csv"},
        {"name": "网络连接（高级引擎）", "engine": "vol3_windows", "plugin": "netscan", "output": "csv"},
        {"name": "句柄列表（高级引擎）", "engine": "vol3_windows", "plugin": "handles", "output": "csv"},
        {"name": "命令行（高级引擎）", "engine": "vol3_windows", "plugin": "cmdline", "output": "csv"},
        {"name": "恶意注入（高级引擎）", "engine": "vol3_windows", "plugin": "malfind", "output": "csv"},
        {"name": "HashDump（高级引擎）", "engine": "vol3_windows", "plugin": "hashdump", "output": "text"},
        {"name": "LsaDump（高级引擎）", "engine": "vol3_windows", "plugin": "lsadump", "output": "text"},
    ]


def linux_memory_tasks() -> list[dict]:
    return [
        {"name": "进程列表", "engine": "vol3_linux", "plugin": "linux.pslist", "output": "csv"},
        {"name": "进程扫描", "engine": "vol3_linux", "plugin": "linux.psscan", "output": "csv"},
        {"name": "进程树", "engine": "vol3_linux", "plugin": "linux.pstree", "output": "csv"},
        {"name": "命令行", "engine": "vol3_linux", "plugin": "linux.psaux", "output": "text"},
        {"name": "环境变量", "engine": "vol3_linux", "plugin": "linux.envars", "output": "csv"},
        {"name": "网络连接", "engine": "vol3_linux", "plugin": "linux.netstat", "output": "csv"},
        {"name": "文件句柄", "engine": "vol3_linux", "plugin": "linux.lsof", "output": "csv"},
        {"name": "已加载模块", "engine": "vol3_linux", "plugin": "linux.lsmod", "output": "csv"},
        {"name": "恶意注入", "engine": "vol3_linux", "plugin": "linux.malfind", "output": "csv"},
        {"name": "系统调用检查", "engine": "vol3_linux", "plugin": "linux.check_syscall", "output": "csv"},
    ]


def read_csv_rows(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def parse_csv_bytes(data: bytes) -> list[dict]:
    text = data.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def decode_command_output(data: bytes) -> str:
    encodings = [locale.getpreferredencoding(False), "utf-8", "gbk"]
    for encoding in encodings:
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class MemoryCommandThread(QThread):
    finished_signal = Signal(str, object)

    def __init__(self, mode: str, payload, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.payload = payload

    def run(self):
        try:
            if self.mode == "command":
                process = subprocess.run(
                    self.payload,
                    capture_output=True,
                    text=False,
                    timeout=120,
                )
                output = process.stdout + process.stderr
                self.finished_signal.emit("command", {"returncode": process.returncode, "output": output})
                return
            if self.mode == "csv_file":
                self.finished_signal.emit("csv_file", read_csv_rows(self.payload))
                return
            if self.mode == "text_file":
                self.finished_signal.emit("text_file", read_text_file(self.payload))
                return
            self.finished_signal.emit("error", f"未知任务模式: {self.mode}")
        except Exception as exc:
            self.finished_signal.emit("error", str(exc))


class MemoryForensicsInterface(QWidget):
    def __init__(self, parent=None, module: str = "windows"):
        super().__init__(parent=parent)
        self.module = module
        self.tasks = windows_memory_tasks() if module == "windows" else linux_memory_tasks()
        self.current_tasks = list(self.tasks)
        self.command_thread = None
        self.memprocfs_process = None
        self.setObjectName(f"{module}MemoryForensicsInterface")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(16, 16, 16, 16)
        self.vBoxLayout.setSpacing(12)

        module_name = "Windows" if module == "windows" else "Linux"
        self.titleLabel = SubtitleLabel(f"{module_name} 内存取证", self)
        self.vBoxLayout.addWidget(self.titleLabel)

        self.vBoxLayout.addLayout(self._build_toolbar())

        self.contentSplitter = QSplitter(Qt.Horizontal, self)
        self.contentSplitter.addWidget(self._build_left_panel())
        self.contentSplitter.addWidget(self._build_center_panel())
        self.contentSplitter.addWidget(self._build_preview_panel())
        self.contentSplitter.setStretchFactor(0, 1)
        self.contentSplitter.setStretchFactor(1, 2)
        self.contentSplitter.setStretchFactor(2, 2)
        self.vBoxLayout.addWidget(self.contentSplitter, 1)

        self.toolRootEdit.setText(default_memory_tool_root())
        self._render_task_list(self.tasks)
        self._render_task_table(self.tasks)

    def _build_toolbar(self):
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self.toolRootEdit = LineEdit(self)
        self.toolRootEdit.setPlaceholderText("内存取证工具目录")
        self.browseToolRootBtn = PushButton("浏览工具目录", self)
        self.browseToolRootBtn.clicked.connect(self.browse_tool_root)
        row1.addWidget(self.toolRootEdit, 1)
        row1.addWidget(self.browseToolRootBtn)

        row2 = QHBoxLayout()
        self.memoryImageEdit = LineEdit(self)
        self.memoryImageEdit.setPlaceholderText("内存镜像路径")
        self.browseImageBtn = PushButton("浏览镜像", self)
        self.browseImageBtn.clicked.connect(self.browse_memory_image)
        self.offlineCheck = CheckBox("高级引擎离线模式", self)
        self.runTaskBtn = PrimaryPushButton("运行选中任务", self)
        self.runTaskBtn.clicked.connect(self.run_selected_task)
        self.stopMountBtn = PushButton("停止内存文件系统", self)
        self.stopMountBtn.clicked.connect(self.stop_memprocfs)
        row2.addWidget(self.memoryImageEdit, 1)
        row2.addWidget(self.browseImageBtn)
        row2.addWidget(self.offlineCheck)
        row2.addWidget(self.runTaskBtn)
        row2.addWidget(self.stopMountBtn)

        layout.addLayout(row1)
        layout.addLayout(row2)
        return layout

    def _build_left_panel(self):
        panel = QFrame(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(SubtitleLabel("任务分类", panel))
        self.summaryLabel = BodyLabel("选择左侧任务，右侧查看命令预览和执行结果。", panel)
        self.summaryLabel.setWordWrap(True)
        layout.addWidget(self.summaryLabel)

        self.taskSearchEdit = LineEdit(panel)
        self.taskSearchEdit.setPlaceholderText("搜索任务")
        self.taskSearchEdit.textChanged.connect(self.filter_tasks)
        layout.addWidget(self.taskSearchEdit)

        self.taskList = ListWidget(panel)
        self.taskList.setObjectName("memoryTaskList")
        self.taskList.itemClicked.connect(self.on_task_clicked)
        layout.addWidget(self.taskList, 1)
        return panel

    def _build_center_panel(self):
        panel = QFrame(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(SubtitleLabel("任务清单", panel))
        self.resultTable = QTableWidget(0, 3, panel)
        self.resultTable.setObjectName("memoryResultTable")
        self.resultTable.setHorizontalHeaderLabels(["名称", "引擎", "输出"])
        self.resultTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.resultTable.setSelectionMode(QTableWidget.SingleSelection)
        self.resultTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.resultTable.setSortingEnabled(True)
        self.resultTable.verticalHeader().setVisible(False)
        self.resultTable.horizontalHeader().setStretchLastSection(True)
        self.resultTable.itemSelectionChanged.connect(self.on_result_selection_changed)
        layout.addWidget(self.resultTable, 1)
        return panel

    def _build_preview_panel(self):
        self.previewPanel = QFrame(self)
        self.previewPanel.setObjectName("memoryPreviewPanel")
        layout = QVBoxLayout(self.previewPanel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.previewTitle = SubtitleLabel("任务预览", self.previewPanel)
        self.previewMetaLabel = BodyLabel("未选中任务", self.previewPanel)
        self.previewMetaLabel.setWordWrap(True)
        self.previewOutput = SearchableTextEdit(self.previewPanel)

        layout.addWidget(self.previewTitle)
        layout.addWidget(self.previewMetaLabel)
        layout.addWidget(self.previewOutput, 1)
        return self.previewPanel

    def browse_tool_root(self):
        folder = QFileDialog.getExistingDirectory(self, "选择内存取证工具目录")
        if folder:
            self.toolRootEdit.setText(folder)
            save_app_settings({"memory_tools_root": folder})

    def browse_memory_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择内存镜像", "", "Memory Images (*.raw *.mem *.dmp *.bin);;All Files (*.*)")
        if path:
            self.memoryImageEdit.setText(path)

    def filter_tasks(self, text: str):
        keyword = text.strip().lower()
        filtered = []
        for task in self.tasks:
            haystack = " ".join([task.get("name", ""), task.get("engine", ""), task.get("plugin", "")]).lower()
            if keyword and keyword not in haystack:
                continue
            filtered.append(task)
        self.current_tasks = filtered
        self._render_task_list(filtered)
        self._render_task_table(filtered)

    def _render_task_list(self, tasks: list[dict]):
        self.taskList.clear()
        for task in tasks:
            item = QListWidgetItem(task["name"])
            item.setData(Qt.UserRole, task)
            self.taskList.addItem(item)

    def _render_task_table(self, tasks: list[dict]):
        sorting = self.resultTable.isSortingEnabled()
        self.resultTable.setSortingEnabled(False)
        self.resultTable.clearContents()
        self.resultTable.setColumnCount(3)
        self.resultTable.setHorizontalHeaderLabels(["名称", "引擎", "输出"])
        self.resultTable.setRowCount(0)
        for row, task in enumerate(tasks):
            self.resultTable.insertRow(row)
            for column, value in enumerate([task.get("name", ""), task.get("engine", ""), task.get("output", "")]):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, task)
                self.resultTable.setItem(row, column, item)
        self.resultTable.setSortingEnabled(sorting)

    def on_task_clicked(self, item):
        task = item.data(Qt.UserRole) if item else None
        if not task:
            return
        self._select_task_in_table(task)
        self.show_task_preview(task)

    def on_result_selection_changed(self):
        row = self.resultTable.currentRow()
        if row < 0:
            return
        item = self.resultTable.item(row, 0)
        if not item:
            return
        task = item.data(Qt.UserRole)
        if task:
            self.show_task_preview(task)

    def _select_task_in_table(self, task: dict):
        for row in range(self.resultTable.rowCount()):
            item = self.resultTable.item(row, 0)
            if item and item.data(Qt.UserRole) == task:
                self.resultTable.selectRow(row)
                return

    def show_task_preview(self, task: dict):
        self.previewTitle.setText(f"任务预览 / {task.get('name', '')}")
        self.previewMetaLabel.setText(f"引擎: {task.get('engine', '')}    输出: {task.get('output', '')}")
        self.previewOutput.setText(self._task_preview_text(task))

    def _task_preview_text(self, task: dict) -> str:
        engine = task.get("engine", "")
        root = self.toolRootEdit.text().strip()
        tool_paths = load_memory_tool_paths(root)
        image = self.memoryImageEdit.text().strip() or "<memory-image>"

        if engine == "vol3_windows":
            command = build_vol3_windows_command(tool_paths, image, task.get("plugin", ""), offline=self.offlineCheck.isChecked())
            return "命令预览:\n" + " ".join(command)
        if engine == "vol3_linux":
            command = build_vol3_linux_command(tool_paths, image, task.get("plugin", ""), offline=self.offlineCheck.isChecked())
            return "命令预览:\n" + " ".join(command)
        if engine == "memprocfs_mount":
            return "挂载命令预览:\n" + " ".join(build_memprocfs_command(tool_paths, image))
        return f"结果路径:\n{task.get('result_path', '')}"

    def run_selected_task(self):
        row = self.resultTable.currentRow()
        if row < 0:
            self.previewOutput.setText("请先选择一个内存取证任务。")
            return
        item = self.resultTable.item(row, 0)
        if not item:
            return
        task = item.data(Qt.UserRole)
        if task:
            self._run_task(task)

    def _validate_tool_paths(self, tool_paths: dict, keys: list[str]) -> str:
        missing = [key for key in keys if not tool_paths.get(key)]
        if missing:
            return "未找到必需工具: " + ", ".join(missing)
        return ""

    def _run_task(self, task: dict):
        engine = task.get("engine", "")
        root = self.toolRootEdit.text().strip()
        image = self.memoryImageEdit.text().strip()
        tool_paths = load_memory_tool_paths(root)

        if engine == "memprocfs_mount":
            missing = self._validate_tool_paths(tool_paths, ["memprocfs"])
            if missing:
                self.previewOutput.setText(missing)
                return
            if not image:
                self.previewOutput.setText("请先选择内存镜像路径。")
                return
            try:
                self.memprocfs_process = subprocess.Popen(build_memprocfs_command(tool_paths, image))
                self.previewOutput.setText("内存文件系统已启动，请等待挂载完成后再读取常用结果。")
            except Exception as exc:
                self.previewOutput.setText(f"启动内存文件系统失败: {exc}")
            return

        if engine in {"memprocfs_csv", "memprocfs_text"}:
            result_path = task.get("result_path", "")
            if not os.path.exists(result_path):
                self.previewOutput.setText(f"结果文件不存在，请先加载内存文件系统:\n{result_path}")
                return
            self._start_thread("csv_file" if engine == "memprocfs_csv" else "text_file", result_path)
            return

        if not image:
            self.previewOutput.setText("请先选择内存镜像路径。")
            return

        if engine == "vol3_windows":
            missing = self._validate_tool_paths(tool_paths, ["python310", "volatility3"])
            if missing:
                self.previewOutput.setText(missing)
                return
            command = build_vol3_windows_command(tool_paths, image, task.get("plugin", ""), offline=self.offlineCheck.isChecked())
            self._start_thread("command", command)
            return

        if engine == "vol3_linux":
            missing = self._validate_tool_paths(tool_paths, ["python310", "volatility3"])
            if missing:
                self.previewOutput.setText(missing)
                return
            command = build_vol3_linux_command(tool_paths, image, task.get("plugin", ""), offline=self.offlineCheck.isChecked())
            self._start_thread("command", command)

    def _start_thread(self, mode: str, payload):
        self.command_thread = MemoryCommandThread(mode, payload, self)
        self.command_thread.finished_signal.connect(self._on_task_finished)
        self.runTaskBtn.setEnabled(False)
        self.previewOutput.setText("任务正在后台执行，请稍候...")
        self.command_thread.start()

    def _on_task_finished(self, mode: str, payload):
        self.command_thread = None
        self.runTaskBtn.setEnabled(True)

        if mode == "error":
            self.previewOutput.setText(f"执行失败: {payload}")
            return

        if mode == "command":
            returncode = payload.get("returncode", -1)
            output = payload.get("output", b"")
            text = decode_command_output(output)
            if returncode == 0:
                try:
                    rows = parse_csv_bytes(output)
                except Exception:
                    rows = []
                self._render_output_rows(rows)
            self.previewOutput.setText(f"退出码: {returncode}\n\n{text}")
            return

        if mode == "csv_file":
            self._render_output_rows(payload)
            self.previewOutput.setText(f"已加载 CSV 结果，共 {len(payload)} 行。")
            return

        if mode == "text_file":
            self.previewOutput.setText(payload)

    def _render_output_rows(self, rows: list[dict]):
        if not rows:
            return
        headers = list(rows[0].keys())
        sorting = self.resultTable.isSortingEnabled()
        self.resultTable.setSortingEnabled(False)
        self.resultTable.clear()
        self.resultTable.setColumnCount(len(headers))
        self.resultTable.setHorizontalHeaderLabels(headers)
        self.resultTable.setRowCount(0)
        for row_index, row in enumerate(rows[:300]):
            self.resultTable.insertRow(row_index)
            for col_index, header in enumerate(headers):
                self.resultTable.setItem(row_index, col_index, QTableWidgetItem(str(row.get(header, ""))))
        self.resultTable.setSortingEnabled(sorting)

    def stop_memprocfs(self):
        try:
            if self.memprocfs_process and self.memprocfs_process.poll() is None:
                self.memprocfs_process.terminate()
                self.previewOutput.setText("内存文件系统已请求停止。")
        except Exception as exc:
            self.previewOutput.setText(f"停止内存文件系统失败: {exc}")


# Backward-compatible aliases for earlier imports.
default_lovelymem_root = default_memory_tool_root
load_lovelymem_tool_paths = load_memory_tool_paths
