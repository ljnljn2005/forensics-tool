import locale
import os
import re
import subprocess

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QListWidgetItem, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, LineEdit, ListWidget, PushButton, SubtitleLabel

from .constants import get_app_settings
from .widgets import SearchableTextEdit


def discover_logs(mapping_path: str, module: str) -> list[dict]:
    root = os.path.abspath(os.path.expanduser(os.path.expandvars(mapping_path or "")))
    if not root or not os.path.exists(root):
        return []

    if module == "windows":
        return _discover_windows_logs(root)
    return _discover_linux_logs(root)


def _discover_windows_logs(root: str) -> list[dict]:
    entries = []
    targets = [
        ("Windows/System32/winevt/Logs", ".evtx", "事件日志"),
        ("Windows/Logs", ".log", "文本日志"),
        ("Windows/Panther", ".log", "安装日志"),
    ]
    for relative_dir, suffix, category in targets:
        full_dir = os.path.join(root, *relative_dir.split("/"))
        if not os.path.isdir(full_dir):
            continue
        for name in sorted(os.listdir(full_dir)):
            full_path = os.path.join(full_dir, name)
            if os.path.isfile(full_path) and name.lower().endswith(suffix):
                entries.append(_build_log_entry(full_path, "/" + relative_dir.replace("\\", "/") + "/" + name, category))
    return entries


def _discover_linux_logs(root: str) -> list[dict]:
    entries = []
    full_dir = os.path.join(root, "var", "log")
    if not os.path.isdir(full_dir):
        return entries

    for name in sorted(os.listdir(full_dir)):
        full_path = os.path.join(full_dir, name)
        if not os.path.isfile(full_path):
            continue
        if name.endswith((".log", ".txt")) or "." not in name:
            entries.append(_build_log_entry(full_path, f"/var/log/{name}", "系统日志"))
    return entries


def _build_log_entry(full_path: str, display_path: str, category: str) -> dict:
    stat = os.stat(full_path)
    return {
        "name": os.path.basename(full_path),
        "path": full_path,
        "display_path": display_path,
        "category": category,
        "size": stat.st_size,
        "modified": int(stat.st_mtime),
    }


def read_log_detail(entry: dict) -> str:
    path = entry.get("path", "")
    lines = [
        f"名称: {entry.get('name', '')}",
        f"分类: {entry.get('category', '')}",
        f"路径: {entry.get('display_path', path)}",
        f"大小: {entry.get('size', 0)} bytes",
        "",
    ]

    if path.lower().endswith(".evtx"):
        lines.append("事件级解析预览:")
        lines.append(_read_evtx_events(path))
        return "\n".join(lines)

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read(8000)
        lines.append("内容预览:")
        lines.append(content or "[空文件]")
    except Exception as exc:
        lines.append(f"读取失败: {exc}")
    return "\n".join(lines)


def _read_evtx_events(path: str, max_events: int = 30) -> str:
    try:
        result = subprocess.run(
            ["wevtutil", "qe", path, f"/c:{max_events}", "/f:text", "/lf:true"],
            capture_output=True,
            text=True,
            encoding=locale.getpreferredencoding(False) or "utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        return f"事件日志解析失败: {exc}"

    if result.returncode == 0:
        output = (result.stdout or "").strip()
        return output or "未读取到事件内容。"

    error_text = (result.stderr or result.stdout or "").strip()
    if error_text:
        return f"事件日志解析失败:\n{error_text}"
    return "事件日志解析失败。"


def parse_evtx_text(text: str) -> list[dict]:
    source = text.strip()
    matches = list(re.finditer(r"(?m)^Event\[\d+\]:", source))
    if matches:
        chunks = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
            chunks.append(source[start:end].strip())
    else:
        chunks = [source] if source else []
    events = []
    for chunk in chunks:
        block = chunk.strip()
        if not block:
            continue
        event = {
            "event_id": _match_field(block, ["Event ID"]),
            "provider": _match_field(block, ["Provider Name", "Source"]),
            "time_created": _match_field(block, ["Date", "Time Created"]),
            "level": _match_field(block, ["Level"]),
            "raw": block,
        }
        if any(event[key] for key in ("event_id", "provider", "time_created", "level")):
            events.append(event)
    return events


def _match_field(text: str, keys: list[str]) -> str:
    for key in keys:
        match = re.search(rf"^\s*{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


class LogScanThread(QThread):
    finished_signal = Signal(list, str)

    def __init__(self, mapping_path: str, module: str, parent=None):
        super().__init__(parent)
        self.mapping_path = mapping_path
        self.module = module

    def run(self):
        try:
            entries = discover_logs(self.mapping_path, self.module)
            self.finished_signal.emit(entries, "")
        except Exception as exc:
            self.finished_signal.emit([], str(exc))


class LogDetailThread(QThread):
    finished_signal = Signal(str, list)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry

    def run(self):
        detail = read_log_detail(self.entry)
        events = parse_evtx_text(detail) if str(self.entry.get("path", "")).lower().endswith(".evtx") else []
        self.finished_signal.emit(detail, events)


class LogAnalysisInterface(QWidget):
    def __init__(self, parent=None, module: str = "windows"):
        super().__init__(parent=parent)
        self.module = module
        self.entries: list[dict] = []
        self.scan_thread = None
        self.detail_thread = None
        self.setObjectName(f"{module}LogAnalysisInterface")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(16, 16, 16, 16)
        self.vBoxLayout.setSpacing(12)

        module_name = "Windows" if module == "windows" else "Linux"
        self.titleLabel = SubtitleLabel(f"{module_name} 日志分析", self)
        self.vBoxLayout.addWidget(self.titleLabel)

        self.toolbarLayout = QHBoxLayout()
        self.mappingPathEdit = LineEdit(self)
        self.mappingPathEdit.setPlaceholderText("映射路径，例如镜像分区根目录")
        self.useSavedPathBtn = PushButton("使用主页映射路径", self)
        self.useSavedPathBtn.clicked.connect(self.fill_saved_mapping_path)
        self.scanBtn = PushButton("扫描日志", self)
        self.scanBtn.clicked.connect(self.scan_logs)
        self.copyOutputBtn = PushButton("复制详情", self)
        self.copyOutputBtn.clicked.connect(self.copy_output)
        self.toolbarLayout.addWidget(self.mappingPathEdit, 1)
        self.toolbarLayout.addWidget(self.useSavedPathBtn)
        self.toolbarLayout.addWidget(self.scanBtn)
        self.toolbarLayout.addWidget(self.copyOutputBtn)
        self.vBoxLayout.addLayout(self.toolbarLayout)

        self.contentSplitter = QSplitter(Qt.Horizontal, self)
        self.contentSplitter.addWidget(self._build_left_panel())
        self.contentSplitter.addWidget(self._build_center_panel())
        self.contentSplitter.addWidget(self._build_preview_panel())
        self.contentSplitter.setStretchFactor(0, 1)
        self.contentSplitter.setStretchFactor(1, 2)
        self.contentSplitter.setStretchFactor(2, 2)
        self.vBoxLayout.addWidget(self.contentSplitter, 1)

        self.fill_saved_mapping_path()
        self.previewOutput.setText("点击“扫描日志”后，在这里查看日志详情。")

    def _build_left_panel(self):
        panel = QFrame(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(SubtitleLabel("日志来源", panel))
        self.summaryLabel = BodyLabel("等待扫描日志目录。", panel)
        self.summaryLabel.setWordWrap(True)
        layout.addWidget(self.summaryLabel)

        self.sourceSearchEdit = LineEdit(panel)
        self.sourceSearchEdit.setPlaceholderText("搜索日志文件")
        self.sourceSearchEdit.textChanged.connect(self.filter_sources)
        layout.addWidget(self.sourceSearchEdit)

        self.logSourceList = ListWidget(panel)
        self.logSourceList.setObjectName("logSourceList")
        self.logSourceList.itemClicked.connect(self.on_source_clicked)
        layout.addWidget(self.logSourceList, 1)
        return panel

    def _build_center_panel(self):
        panel = QFrame(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(SubtitleLabel("日志结果", panel))
        self.resultTable = QTableWidget(0, 4, panel)
        self.resultTable.setObjectName("logResultTable")
        self.resultTable.setHorizontalHeaderLabels(["名称", "分类", "路径", "大小"])
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
        self.previewPanel.setObjectName("logPreviewPanel")

        layout = QVBoxLayout(self.previewPanel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.previewTitle = SubtitleLabel("日志详情", self.previewPanel)
        self.previewMetaLabel = BodyLabel("未选中日志记录", self.previewPanel)
        self.previewMetaLabel.setWordWrap(True)
        self.previewOutput = SearchableTextEdit(self.previewPanel)
        self.eventTable = QTableWidget(0, 4, self.previewPanel)
        self.eventTable.setObjectName("logEventTable")
        self.eventTable.setHorizontalHeaderLabels(["Event ID", "Provider", "TimeCreated", "Level"])
        self.eventTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.eventTable.setSelectionMode(QTableWidget.SingleSelection)
        self.eventTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.eventTable.setSortingEnabled(True)
        self.eventTable.verticalHeader().setVisible(False)
        self.eventTable.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.previewTitle)
        layout.addWidget(self.previewMetaLabel)
        layout.addWidget(self.previewOutput, 1)
        layout.addWidget(self.eventTable, 1)
        return self.previewPanel

    def fill_saved_mapping_path(self):
        path = self._current_mapping_path()
        if path:
            self.mappingPathEdit.setText(path)

    def _current_mapping_path(self):
        try:
            window = self.window()
            if hasattr(window, "mapping_path") and window.mapping_path:
                return window.mapping_path
        except Exception:
            pass
        try:
            return get_app_settings().get("mapping_path", "")
        except Exception:
            return ""

    def scan_logs(self):
        mapping_path = self.mappingPathEdit.text().strip() or self._current_mapping_path()
        if not mapping_path or not os.path.exists(mapping_path):
            self.summaryLabel.setText("映射路径不可用。")
            self.previewOutput.setText("错误: 无效路径。请选择或输入一个存在的提取路径。")
            self.resultTable.setRowCount(0)
            self.logSourceList.clear()
            return

        self.mappingPathEdit.setText(mapping_path)
        self.summaryLabel.setText("正在后台扫描日志，请稍候...")
        self.previewOutput.setText("正在扫描日志目录，界面仍可继续操作。")
        self._set_loading(True)

        self.scan_thread = LogScanThread(mapping_path, self.module, self)
        self.scan_thread.finished_signal.connect(self._on_scan_finished)
        self.scan_thread.start()

    def _on_scan_finished(self, entries: list[dict], error: str):
        self.scan_thread = None
        self._set_loading(False)

        if error:
            self.summaryLabel.setText("日志扫描失败。")
            self.previewOutput.setText(f"扫描失败: {error}")
            self.resultTable.setRowCount(0)
            self.logSourceList.clear()
            return

        self.entries = entries
        self._render_source_list(self.entries)
        self._render_result_table(self.entries)
        module_name = "Windows" if self.module == "windows" else "Linux"
        self.summaryLabel.setText(f"{module_name} 日志共发现 {len(self.entries)} 个候选文件。")

        if self.entries:
            self.logSourceList.setCurrentRow(0)
            self.resultTable.selectRow(0)
            self.show_entry_detail(self.entries[0])
        else:
            self.previewOutput.setText("没有发现匹配的日志文件。")

    def _set_loading(self, loading: bool):
        self.scanBtn.setEnabled(not loading)
        self.useSavedPathBtn.setEnabled(not loading)

    def _render_source_list(self, entries: list[dict]):
        self.logSourceList.clear()
        for entry in entries:
            item = QListWidgetItem(f"{entry['category']} - {entry['name']}")
            item.setData(Qt.UserRole, entry)
            self.logSourceList.addItem(item)

    def _render_result_table(self, entries: list[dict]):
        sorting_enabled = self.resultTable.isSortingEnabled()
        self.resultTable.setSortingEnabled(False)
        self.resultTable.setRowCount(0)
        for row, entry in enumerate(entries):
            self.resultTable.insertRow(row)
            values = [
                entry.get("name", ""),
                entry.get("category", ""),
                entry.get("display_path", ""),
                str(entry.get("size", 0)),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, entry)
                self.resultTable.setItem(row, column, item)
        self.resultTable.setSortingEnabled(sorting_enabled)

    def filter_sources(self, text: str):
        keyword = text.strip().lower()
        filtered = []
        for entry in self.entries:
            haystack = " ".join([entry.get("name", ""), entry.get("category", ""), entry.get("display_path", "")]).lower()
            if keyword and keyword not in haystack:
                continue
            filtered.append(entry)
        self._render_source_list(filtered)
        self._render_result_table(filtered)

    def on_source_clicked(self, item):
        entry = item.data(Qt.UserRole) if item else None
        if not entry:
            return
        self.show_entry_detail(entry)
        for row in range(self.resultTable.rowCount()):
            row_entry = self.resultTable.item(row, 0).data(Qt.UserRole)
            if row_entry == entry:
                self.resultTable.selectRow(row)
                return

    def on_result_selection_changed(self):
        row = self.resultTable.currentRow()
        if row < 0:
            return
        item = self.resultTable.item(row, 0)
        if not item:
            return
        entry = item.data(Qt.UserRole)
        if entry:
            self.show_entry_detail(entry)

    def show_entry_detail(self, entry: dict):
        self.previewTitle.setText(f"日志详情 / {entry.get('name', '')}")
        self.previewMetaLabel.setText(f"分类: {entry.get('category', '')}    路径: {entry.get('display_path', '')}")
        self.previewOutput.setText("正在加载日志详情...")
        self._render_event_table([])
        self.detail_thread = LogDetailThread(entry, self)
        self.detail_thread.finished_signal.connect(self._on_detail_finished)
        self.detail_thread.start()

    def _on_detail_finished(self, text: str, events: list[dict]):
        self.detail_thread = None
        self.previewOutput.setText(text)
        self._render_event_table(events)

    def _render_event_table(self, events: list[dict]):
        sorting_enabled = self.eventTable.isSortingEnabled()
        self.eventTable.setSortingEnabled(False)
        self.eventTable.setRowCount(0)
        for row, event in enumerate(events):
            self.eventTable.insertRow(row)
            values = [
                event.get("event_id", ""),
                event.get("provider", ""),
                event.get("time_created", ""),
                event.get("level", ""),
            ]
            for column, value in enumerate(values):
                self.eventTable.setItem(row, column, QTableWidgetItem(value))
        self.eventTable.setSortingEnabled(sorting_enabled)

    def copy_output(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.previewOutput.textEdit.toPlainText())
