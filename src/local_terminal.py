from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt
from qfluentwidgets import SubtitleLabel, LineEdit, PushButton, ComboBox, PlainTextEdit, BodyLabel, SubtitleLabel
from .widgets import CommandRunnerThread
from .constants import PLUGINS_DIR
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem
from PySide6.QtCore import QThread, Signal
import json, os, subprocess, sys


class LocalShellThread(QThread):
    output_received = Signal(str)

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self.running = True

    def run(self):
        try:
            while self.running and self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line is None:
                    break
                if line:
                    try:
                        self.output_received.emit(line.rstrip('\n'))
                    except Exception:
                        pass
                else:
                    self.msleep(50)
        except Exception:
            pass

    def stop(self):
        self.running = False


class LocalTerminalWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("简单终端 - 本地")
        self.resize(800, 500)
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(10, 10, 10, 10)

        self.output = PlainTextEdit(self)
        self.output.setReadOnly(True)
        self.vbox.addWidget(self.output, 1)

        cmdLayout = QHBoxLayout()
        self.input = LineEdit(self)
        self.input.setPlaceholderText("输入命令并按回车发送到本地 shell")
        self.input.returnPressed.connect(self.send_input)
        self.sendBtn = PushButton("发送", self)
        self.sendBtn.clicked.connect(self.send_input)
        cmdLayout.addWidget(self.input)
        cmdLayout.addWidget(self.sendBtn)
        self.vbox.addLayout(cmdLayout)

        self.proc = None
        self.thread = None

    def start_shell(self, shell_cmd: list):
        # if already started, ignore
        if self.proc and self.proc.poll() is None:
            return
        try:
            self.output.clear()
            # start subprocess with pipes
            self.proc = subprocess.Popen(shell_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            self.thread = LocalShellThread(self.proc)
            self.thread.output_received.connect(self.append_output)
            self.thread.start()
        except Exception as e:
            self.append_output(f"[启动本地 shell 失败: {e}]")

    def append_output(self, text: str):
        self.output.appendPlainText(text)

    def send_input(self):
        if not self.proc or self.proc.poll() is not None:
            self.append_output("[本地 shell 未运行]")
            return
        cmd = self.input.text()
        self.input.clear()
        try:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            self.append_output(f"[发送失败: {e}]")

    def closeEvent(self, event):
        try:
            if self.thread:
                self.thread.stop()
                self.thread.wait()
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass
        event.accept()



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
        self.shellSelect.addItems(['cmd', 'powershell', 'wsl'])
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

        # interactive terminal window (separate popup)
        self.terminal_window = LocalTerminalWindow(self)

        self.thread = None
        self.runBtn.clicked.connect(self.run_command)
        self.cmdEdit.returnPressed.connect(self.run_command)
        self.pluginRunBtn.clicked.connect(self.run_selected_plugin)
        # populate plugins
        self.populate_plugins()

        # left-panel-like plugin list and controls (mimic LiveSshInterface)
        # note: for simplicity we provide a reload button to refresh plugin list and an open terminal button
        self.reloadBtn = PushButton('刷新插件', self)
        self.openTerminalBtn = PushButton('打开交互式终端', self)
        self.reloadBtn.clicked.connect(self.populate_plugins)
        self.openTerminalBtn.clicked.connect(self.open_terminal)
        # add to vbox top area
        top_tools = QHBoxLayout()
        top_tools.addWidget(self.reloadBtn)
        top_tools.addWidget(self.openTerminalBtn)
        top_tools.addStretch(1)
        self.vbox.insertLayout(1, top_tools)

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
        elif shell == 'wsl':
            # invoke wsl with -e sh -c
            full = f'wsl {cmd}'
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

    def open_terminal(self):
        # start shell process in terminal window according to selection
        shell = self.shellSelect.currentText()
        if shell == 'powershell':
            cmd = ['powershell']
        elif shell == 'wsl':
            cmd = ['wsl']
        else:
            cmd = ['cmd.exe']
        try:
            self.terminal_window.start_shell(cmd)
            self.terminal_window.show()
            self.terminal_window.raise_()
            self.terminal_window.activateWindow()
        except Exception as e:
            self.output.appendPlainText(f"打开终端失败: {e}")
