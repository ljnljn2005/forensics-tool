from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt
from qfluentwidgets import SubtitleLabel, LineEdit, PushButton, ComboBox, PlainTextEdit, BodyLabel
from .widgets import CommandRunnerThread


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
        self.vbox.addLayout(ctrl)

        self.output = PlainTextEdit(self)
        self.output.setReadOnly(True)
        self.vbox.addWidget(self.output, 1)

        self.thread = None
        self.runBtn.clicked.connect(self.run_command)
        self.cmdEdit.returnPressed.connect(self.run_command)

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
