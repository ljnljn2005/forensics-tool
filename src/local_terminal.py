from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt
from qfluentwidgets import SubtitleLabel, LineEdit, PushButton, ComboBox, PlainTextEdit, BodyLabel
from .widgets import CommandRunnerThread
from .constants import PLUGINS_DIR
import json, os


class LocalTerminalInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('localTerminalInterface')
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(16, 16, 16, 16)
        self.vbox.setSpacing(8)

        self.title = SubtitleLabel('本地终端', self)
        self.vbox.addWidget(self.title)

        ctrl = QHBoxLayout()
        ctrl.addWidget(BodyLabel('Shell:', self))
        self.shellSelect = ComboBox(self)
        self.shellSelect.addItems(['cmd', 'powershell'])
        self.shellSelect.setFixedWidth(140)
        ctrl.addWidget(self.shellSelect)
        ctrl.addWidget(BodyLabel('命令:', self))
        self.cmdEdit = LineEdit(self)
        self.cmdEdit.setPlaceholderText('在此输入要执行的命令，回车可执行')
        ctrl.addWidget(self.cmdEdit, 1)
        self.runBtn = PushButton('运行', self)
        ctrl.addWidget(self.runBtn)
        # plugin run controls
        self.pluginSelect = ComboBox(self)
        self.pluginSelect.setFixedWidth(320)
        self.pluginRunBtn = PushButton('运行插件积木', self)
        ctrl.addWidget(self.pluginSelect)
        ctrl.addWidget(self.pluginRunBtn)
        self.vbox.addLayout(ctrl)

        self.output = PlainTextEdit(self)
        self.output.setReadOnly(True)
        self.vbox.addWidget(self.output, 1)

        self.thread = None
        self.runBtn.clicked.connect(self.run_command)
        self.cmdEdit.returnPressed.connect(self.run_command)
        self.pluginRunBtn.clicked.connect(self.run_selected_plugin)
        # populate plugins
        self.populate_plugins()

    def populate_plugins(self):
        self.pluginSelect.clear()
        plugins_file = os.path.join(PLUGINS_DIR, 'ssh_plugins.json')
        data = {}
        try:
            if os.path.exists(plugins_file):
                with open(plugins_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
        except Exception:
            data = {}
        # data is a dict of plugin_name -> plugin_obj
        entries = []
        for pname, pobj in (data.items() if isinstance(data, dict) else []):
            blocks = pobj.get('blocks', []) if isinstance(pobj, dict) else pobj
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                mod = b.get('module', 'linux')
                # include blocks that target local or all
                if mod in ('local', 'all'):
                    label = f"{pname} - {b.get('name','')}: {b.get('cmd','') }"
                    # store raw cmd as userData via a simple mapping
                    entries.append((label, b.get('cmd','')))
        for lbl, cmd in entries:
            self.pluginSelect.addItem(lbl)
            # attach cmd into internal mapping in the model (ComboBox doesn't support userData easily)
        # store mapping
        self._plugin_entries = entries

    def run_selected_plugin(self):
        idx = self.pluginSelect.currentIndex()
        if idx < 0:
            return
        try:
            cmd = self._plugin_entries[idx][1]
            if cmd:
                self.cmdEdit.setText(cmd)
                self.run_command()
        except Exception:
            pass

    def append_output(self, text: str):
        self.output.appendPlainText(text)

    def run_command(self):
        if self.thread:
            return
        shell = self.shellSelect.currentText()
        cmd = self.cmdEdit.text().strip()
        if not cmd:
            return
        # prepare platform command
        if shell == 'powershell':
            full = f'powershell -NoProfile -Command "{cmd}"'
        else:
            # cmd.exe /c
            full = f'cmd /c "{cmd}"'

        self.output.appendPlainText(f">>> 执行: {full}\n")
        self.thread = CommandRunnerThread(full)
        self.thread.line_signal.connect(self.append_output)
        self.thread.finished_signal.connect(self._on_finished)
        self.thread.start()

    def _on_finished(self, code: int):
        self.append_output(f"\n[命令完成，退出码={code}]")
        self.thread = None
