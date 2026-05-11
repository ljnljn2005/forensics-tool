import json
import locale
import os
import subprocess

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from .constants import PLUGINS_DIR
from .widgets import SearchableTextEdit


LOCAL_MODULES = {"local", "all"}


def build_shell_command(shell: str, command: str) -> list[str]:
    """Build a command argv without relying on nested shell quoting."""
    shell = (shell or "cmd").lower()
    if shell == "powershell":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    if shell == "wsl":
        return ["wsl", "sh", "-lc", command]
    return ["cmd.exe", "/c", command]


def is_file_block(block_type: str) -> bool:
    text = (block_type or "").lower()
    return "文件" in text or "提取" in text or "file" in text or "extract" in text


def decode_shell_encoding() -> str:
    return locale.getpreferredencoding(False) or "utf-8"


class CommandRunnerThread(QThread):
    line_signal = Signal(str)
    finished_signal = Signal(int)

    def __init__(self, argv: list[str], parent=None):
        super().__init__(parent)
        self.argv = argv
        self._proc = None

    def run(self):
        code = -1
        try:
            self._proc = subprocess.Popen(
                self.argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=decode_shell_encoding(),
                errors="replace",
                bufsize=1,
            )
            if self._proc.stdout:
                for line in self._proc.stdout:
                    self.line_signal.emit(line.rstrip("\n"))
            self._proc.wait()
            code = self._proc.returncode
        except Exception as exc:
            self.line_signal.emit(f"[执行失败] {exc}")
        self.finished_signal.emit(code)

    def stop(self):
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass


class LocalShellReader(QThread):
    output_signal = Signal(str)

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self.running = True

    def run(self):
        try:
            while self.running and self.process and self.process.poll() is None:
                line = self.process.stdout.readline() if self.process.stdout else ""
                if line:
                    self.output_signal.emit(line.rstrip("\n"))
                else:
                    self.msleep(50)
        except Exception as exc:
            self.output_signal.emit(f"[读取终端输出失败] {exc}")

    def stop(self):
        self.running = False


class LocalTerminalWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(None)
        self.owner = parent
        self.setWindowTitle("交互式本地终端")
        self.resize(900, 560)

        self.proc = None
        self.reader = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.output = PlainTextEdit(self)
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        input_layout = QHBoxLayout()
        self.input = LineEdit(self)
        self.input.setPlaceholderText("输入命令并回车发送到当前 shell")
        self.input.returnPressed.connect(self.send_input)
        self.sendBtn = PushButton("发送", self)
        self.sendBtn.clicked.connect(self.send_input)
        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(self.sendBtn)
        layout.addLayout(input_layout)

    def start_shell(self, shell: str):
        if self.proc and self.proc.poll() is None:
            self.show()
            self.raise_()
            self.activateWindow()
            return

        argv = self._interactive_shell_argv(shell)
        self.output.clear()
        self.output.appendPlainText(f">>> 启动 shell: {' '.join(argv)}")
        try:
            self.proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=decode_shell_encoding(),
                errors="replace",
                bufsize=1,
            )
            self.reader = LocalShellReader(self.proc, self)
            self.reader.output_signal.connect(self.output.appendPlainText)
            self.reader.start()
        except Exception as exc:
            self.output.appendPlainText(f"[启动本地 shell 失败] {exc}")

    def send_input(self):
        if not self.proc or self.proc.poll() is not None or not self.proc.stdin:
            self.output.appendPlainText("[本地 shell 未运行]")
            return
        command = self.input.text().strip()
        self.input.clear()
        if not command:
            return
        try:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
        except Exception as exc:
            self.output.appendPlainText(f"[发送失败] {exc}")

    def closeEvent(self, event):
        self.stop_shell()
        event.accept()

    def stop_shell(self):
        try:
            if self.reader:
                self.reader.stop()
                self.reader.wait(1000)
                self.reader = None
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
                self.proc.wait(timeout=2)
        except Exception:
            try:
                if self.proc and self.proc.poll() is None:
                    self.proc.kill()
            except Exception:
                pass
        self.proc = None

    def _interactive_shell_argv(self, shell: str) -> list[str]:
        shell = (shell or "cmd").lower()
        if shell == "powershell":
            return ["powershell", "-NoProfile"]
        if shell == "wsl":
            return ["wsl"]
        return ["cmd.exe"]


class LocalTerminalInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("localTerminalInterface")

        self.plugins_data = {}
        self._plugin_entries: list[dict] = []
        self.thread = None
        self.terminal_window = LocalTerminalWindow(self)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._build_left_panel(), 1)
        root.addWidget(self._build_workbench(), 3)

        self.load_plugins()
        self._show_empty_preview()

    def _build_left_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("localTerminalPluginPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(SubtitleLabel("本地插件", panel))

        self.pluginSummaryLabel = BodyLabel("选择一个插件查看本地积木。", panel)
        self.pluginSummaryLabel.setWordWrap(True)
        layout.addWidget(self.pluginSummaryLabel)

        self.pluginList = ListWidget(panel)
        self.pluginList.setObjectName("localTerminalPluginList")
        self.pluginList.itemClicked.connect(self.on_plugin_selected)
        layout.addWidget(self.pluginList, 1)

        return panel

    def _build_workbench(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(SubtitleLabel("本地终端", panel))
        layout.addLayout(self._build_toolbar())
        layout.addLayout(self._build_command_bar())

        self.locationLabel = BodyLabel("未选择插件", panel)
        self.locationLabel.setObjectName("localTerminalLocationLabel")
        layout.addWidget(self.locationLabel)

        self.mainSplitter = QSplitter(Qt.Vertical, panel)
        self.mainSplitter.addWidget(self._build_block_panel())
        self.mainSplitter.addWidget(self._build_preview_panel())
        self.mainSplitter.setStretchFactor(0, 3)
        self.mainSplitter.setStretchFactor(1, 2)
        layout.addWidget(self.mainSplitter, 1)
        return panel

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.refreshBtn = PushButton("刷新插件", self)
        self.refreshBtn.clicked.connect(self.load_plugins)
        self.openTerminalBtn = PushButton("打开交互终端", self)
        self.openTerminalBtn.clicked.connect(self.open_terminal)
        self.clearOutputBtn = PushButton("清空输出", self)
        self.clearOutputBtn.clicked.connect(self.clear_output)
        self.copyOutputBtn = PushButton("复制输出", self)
        self.copyOutputBtn.clicked.connect(self.copy_output)
        self.stopBtn = PushButton("停止命令", self)
        self.stopBtn.clicked.connect(self.stop_command)
        self.stopBtn.setEnabled(False)

        layout.addWidget(self.refreshBtn)
        layout.addWidget(self.openTerminalBtn)
        layout.addWidget(self.clearOutputBtn)
        layout.addWidget(self.copyOutputBtn)
        layout.addWidget(self.stopBtn)
        layout.addStretch(1)
        return layout

    def _build_command_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)

        layout.addWidget(BodyLabel("Shell", self))
        self.shellSelect = ComboBox(self)
        self.shellSelect.addItems(["cmd", "powershell", "wsl"])
        self.shellSelect.setFixedWidth(140)
        layout.addWidget(self.shellSelect)

        self.cmdEdit = LineEdit(self)
        self.cmdEdit.setPlaceholderText("输入命令，回车执行")
        self.cmdEdit.returnPressed.connect(self.run_command)
        layout.addWidget(self.cmdEdit, 1)

        self.runBtn = PrimaryPushButton("运行", self)
        self.runBtn.clicked.connect(self.run_command)
        self.pluginRunBtn = PushButton("运行选中积木", self)
        self.pluginRunBtn.clicked.connect(self.run_selected_plugin)
        self.extractBtn = PushButton("按插件执行并查看", self)
        self.extractBtn.clicked.connect(self.extract_local_info)

        layout.addWidget(self.runBtn)
        layout.addWidget(self.pluginRunBtn)
        layout.addWidget(self.extractBtn)
        return layout

    def _build_block_panel(self) -> QWidget:
        panel = QFrame(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("本地积木列表", panel))
        header.addStretch(1)
        self.blockSearchEdit = LineEdit(panel)
        self.blockSearchEdit.setPlaceholderText("搜索名称、命令或来源插件")
        self.blockSearchEdit.textChanged.connect(self.on_block_search_changed)
        header.addWidget(self.blockSearchEdit)
        layout.addLayout(header)

        self.blockTable = QTableWidget(0, 5, panel)
        self.blockTable.setObjectName("localTerminalBlockTable")
        self.blockTable.setHorizontalHeaderLabels(["名称", "类型", "Shell", "来源插件", "命令"])
        self.blockTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.blockTable.setSelectionMode(QTableWidget.SingleSelection)
        self.blockTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.blockTable.setAlternatingRowColors(True)
        self.blockTable.verticalHeader().setVisible(False)
        self.blockTable.horizontalHeader().setStretchLastSection(True)
        self.blockTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.blockTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.blockTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.blockTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.blockTable.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.blockTable.itemSelectionChanged.connect(self.on_block_selection_changed)
        self.blockTable.itemDoubleClicked.connect(lambda _: self.run_selected_plugin())
        layout.addWidget(self.blockTable, 1)
        return panel

    def _build_preview_panel(self) -> QWidget:
        self.previewPanel = QFrame(self)
        self.previewPanel.setObjectName("localTerminalPreviewPanel")

        layout = QVBoxLayout(self.previewPanel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.previewTitle = SubtitleLabel("输出预览", self.previewPanel)
        layout.addWidget(self.previewTitle)

        self.previewMetaLabel = BodyLabel("选择积木后，可在这里查看命令预览或执行结果。", self.previewPanel)
        self.previewMetaLabel.setWordWrap(True)
        layout.addWidget(self.previewMetaLabel)

        self.previewOutput = SearchableTextEdit(self.previewPanel)
        layout.addWidget(self.previewOutput, 1)

        self.command_output = self.previewOutput
        return self.previewPanel

    def load_plugins(self):
        self.plugins_data = self._read_plugins()
        self.pluginList.clear()
        count = 0
        for name in sorted(self.plugins_data.keys()):
            if self._local_blocks_for_plugin(name):
                self.pluginList.addItem(name)
                count += 1

        self.pluginSummaryLabel.setText(f"已加载 {count} 个含本地积木的插件。")
        self.populate_plugin_blocks(None)
        if self.pluginList.count():
            self.pluginList.setCurrentRow(0)
            self.on_plugin_selected(self.pluginList.item(0))
        else:
            self.locationLabel.setText("未发现可用的本地插件")
            self._show_empty_preview("没有发现 module=local/all 的插件积木。")

    def populate_plugin_blocks(self, plugin_name: str | None):
        self._plugin_entries = []
        names = [plugin_name] if plugin_name else sorted(self.plugins_data.keys())
        for name in names:
            for block in self._local_blocks_for_plugin(name):
                entry = {"plugin": name, **block}
                self._plugin_entries.append(entry)
        self._render_block_table(self._plugin_entries)

    def on_plugin_selected(self, item):
        if not item:
            return
        plugin_name = item.text()
        self.populate_plugin_blocks(plugin_name)
        row_count = len(self._plugin_entries)
        self.locationLabel.setText(f"当前插件 / {plugin_name}")
        self.pluginSummaryLabel.setText(f"{plugin_name} 含 {row_count} 个本地积木。")
        if self.blockTable.rowCount():
            self.blockTable.selectRow(0)
            self.on_block_selection_changed()
        else:
            self._show_empty_preview("该插件没有本地可执行积木。")

    def on_block_search_changed(self):
        keyword = self.blockSearchEdit.text().strip().lower()
        if not keyword:
            self._render_block_table(self._plugin_entries)
            return

        filtered = []
        for entry in self._plugin_entries:
            haystack = " ".join(
                [
                    entry.get("plugin", ""),
                    entry.get("name", ""),
                    entry.get("type", ""),
                    entry.get("cmd", ""),
                ]
            ).lower()
            if keyword in haystack:
                filtered.append(entry)
        self._render_block_table(filtered)

    def on_block_selection_changed(self):
        entry = self._current_plugin_entry()
        if not entry:
            return
        self.previewTitle.setText(f"积木预览 / {entry.get('name') or '未命名积木'}")
        self.previewMetaLabel.setText(
            f"来源插件: {entry.get('plugin', '')}    类型: {entry.get('type', '')}    Shell: {self.shellSelect.currentText()}"
        )
        if is_file_block(entry.get("type", "")):
            self.previewOutput.setText(self._file_block_message(entry))
            return
        self.previewOutput.setText(
            f"命令预览:\n{entry.get('cmd', '')}\n\n双击表格行或点击“运行选中积木”即可执行。"
        )

    def run_selected_plugin(self):
        entry = self._current_plugin_entry()
        if not entry:
            InfoBar.info("请选择积木", "请选择左侧插件和可执行的本地积木。", parent=self)
            return
        if is_file_block(entry.get("type", "")):
            self.previewTitle.setText(f"文件提取型积木 / {entry.get('name') or '未命名积木'}")
            self.previewMetaLabel.setText(f"来源插件: {entry.get('plugin', '')}")
            self.previewOutput.setText(self._file_block_message(entry))
            return
        command = entry.get("cmd", "").strip()
        self.cmdEdit.setText(command)
        self.run_command()

    def run_command(self):
        if self.thread:
            InfoBar.info("命令运行中", "请等待当前命令完成，或先点击停止命令。", parent=self)
            return
        command = self.cmdEdit.text().strip()
        if not command:
            InfoBar.info("命令为空", "请输入要执行的本地命令。", parent=self)
            return
        argv = build_shell_command(self.shellSelect.currentText(), command)
        self.previewTitle.setText("命令输出")
        self.previewMetaLabel.setText(f"Shell: {self.shellSelect.currentText()}    命令: {command}")
        self.previewOutput.setText("")
        self.append_output(f">>> 执行: {' '.join(argv)}")
        self.thread = CommandRunnerThread(argv, self)
        self.thread.line_signal.connect(self.append_output)
        self.thread.finished_signal.connect(self._on_command_finished)
        self._set_running(True)
        self.thread.start()

    def stop_command(self):
        if self.thread:
            self.thread.stop()
            self.append_output("[已请求停止当前命令]")

    def extract_local_info(self):
        item = self.pluginList.currentItem()
        if not item:
            InfoBar.info("请选择插件", "请选择左侧插件后再执行。", parent=self)
            return
        plugin_name = item.text()
        blocks = self._local_blocks_for_plugin(plugin_name)
        if not blocks:
            InfoBar.info("没有本地积木", "该插件没有 module=local/all 的积木。", parent=self)
            return

        file_only = all(is_file_block((block or {}).get("type", "")) for block in blocks)
        sections = []
        ran_count = 0
        for block in blocks:
            entry = {"plugin": plugin_name, **block}
            title = block.get("name") or "未命名积木"
            if is_file_block(block.get("type", "")):
                sections.append(f"## {title}\n{self._file_block_message(entry)}")
                continue

            command = block.get("cmd", "").strip()
            if not command:
                continue

            argv = build_shell_command(self.shellSelect.currentText(), command)
            try:
                result = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    encoding=decode_shell_encoding(),
                    errors="replace",
                    timeout=60,
                )
                output = (result.stdout or "") + (result.stderr or "")
                section = (
                    f"## {title}\n"
                    f"命令: {' '.join(argv)}\n"
                    f"退出码: {result.returncode}\n\n"
                    f"{output.strip()}"
                )
                ran_count += 1
            except Exception as exc:
                section = f"## {title}\n命令: {' '.join(argv)}\n\n[执行失败] {exc}"
            sections.append(section)

        if file_only and len(blocks) == 1:
            block_name = blocks[0].get("name") or "未命名积木"
            self.previewTitle.setText(f"文件提取型积木 / {block_name}")
        else:
            self.previewTitle.setText(f"按插件执行结果 / {plugin_name}")
        self.previewMetaLabel.setText(f"共处理 {len(blocks)} 个积木，其中执行命令 {ran_count} 个。")
        self.previewOutput.setText("\n\n".join(sections) if sections else "当前插件没有可展示的结果。")
        if ran_count:
            InfoBar.success(
                "执行完成",
                f"已执行 {ran_count} 条本地命令。",
                parent=self,
                position=InfoBarPosition.TOP,
            )

    def open_terminal(self):
        self.terminal_window.start_shell(self.shellSelect.currentText())
        self.terminal_window.show()
        self.terminal_window.raise_()
        self.terminal_window.activateWindow()

    def clear_output(self):
        self.previewOutput.setText("")
        self.previewMetaLabel.setText("输出已清空。")

    def copy_output(self):
        QApplication.clipboard().setText(self.previewOutput.textEdit.toPlainText())
        InfoBar.success("已复制", "当前预览输出已复制到剪贴板。", parent=self)

    def append_output(self, text: str):
        self.previewOutput.textEdit.append(text)
        scrollbar = self.previewOutput.textEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_command_finished(self, code: int):
        self.append_output(f"[命令完成，退出码={code}]")
        self.thread = None
        self._set_running(False)

    def _set_running(self, running: bool):
        self.runBtn.setEnabled(not running)
        self.pluginRunBtn.setEnabled(not running)
        self.extractBtn.setEnabled(not running)
        self.refreshBtn.setEnabled(not running)
        self.stopBtn.setEnabled(running)

    def _render_block_table(self, entries: list[dict]):
        self.blockTable.setRowCount(0)
        for row, entry in enumerate(entries):
            self.blockTable.insertRow(row)
            values = [
                entry.get("name", ""),
                entry.get("type", ""),
                self.shellSelect.currentText(),
                entry.get("plugin", ""),
                entry.get("cmd", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, entry)
                if column == 0 and is_file_block(entry.get("type", "")):
                    item.setForeground(QBrush(QColor("#c25f30")))
                self.blockTable.setItem(row, column, item)

        if self.blockTable.rowCount():
            self.blockTable.selectRow(0)
        else:
            self.previewTitle.setText("输出预览")
            self.previewMetaLabel.setText("当前筛选条件下没有积木。")
            self.previewOutput.setText("没有匹配的本地积木。")

    def _current_plugin_entry(self):
        row = self.blockTable.currentRow()
        if row < 0:
            return None
        item = self.blockTable.item(row, 0)
        if not item:
            return None
        data = item.data(Qt.UserRole)
        return data if isinstance(data, dict) else None

    def _local_blocks_for_plugin(self, plugin_name: str) -> list[dict]:
        plugin = self.plugins_data.get(plugin_name, {})
        blocks = plugin.get("blocks", []) if isinstance(plugin, dict) else plugin
        result = []
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            module = (block.get("module") or "linux").lower()
            if module in LOCAL_MODULES:
                result.append(block)
        return result

    def _file_block_message(self, entry: dict) -> str:
        return (
            "这是文件提取型积木，不会在本地终端直接执行。\n"
            "请切换到“离线取证（提取盘）”页面，设置映射路径后运行提取。\n\n"
            f"插件: {entry.get('plugin', '')}\n"
            f"积木: {entry.get('name', '')}\n"
            f"路径/命令示例:\n{entry.get('cmd', '')}"
        )

    def _show_empty_preview(self, message: str = "选择左侧插件或手动输入命令，查看执行结果。"):
        self.previewTitle.setText("输出预览")
        self.previewMetaLabel.setText("未选中文件 / 记录")
        self.previewOutput.setText(message)

    def _read_plugins(self) -> dict:
        plugins_file = os.path.join(PLUGINS_DIR, "ssh_plugins.json")
        try:
            if os.path.exists(plugins_file):
                with open(plugins_file, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                return data if isinstance(data, dict) else {}
        except Exception as exc:
            InfoBar.warning("插件加载失败", str(exc), parent=self)
        return {}

    def closeEvent(self, event):
        try:
            self.terminal_window.close()
        except Exception:
            pass
        super().closeEvent(event)
