from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem, QDialog
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QFont, QTextDocument, QTextCursor
from qfluentwidgets import LineEdit, PushButton, TextEdit, SubtitleLabel, BodyLabel, ListWidget, PlainTextEdit, PrimaryPushButton, TransparentToolButton, FluentIcon, ComboBox
from .constants import get_app_proxy
import os, json


class SearchableTextEdit(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.vbox = QVBoxLayout(self)
        self.searchLayout = QHBoxLayout()
        self.searchLineEdit = LineEdit(self)
        self.prevButton = PushButton("上一处", self)
        self.nextButton = PushButton("下一处", self)
        self.searchLayout.addWidget(self.searchLineEdit, 1)
        self.searchLayout.addWidget(self.prevButton)
        self.searchLayout.addWidget(self.nextButton)
        self.vbox.addLayout(self.searchLayout)

        self.textEdit = TextEdit(self)
        self.textEdit.setReadOnly(True)
        self.textEdit.setFont(QFont("Consolas", 10))
        self.vbox.addWidget(self.textEdit, 1)

        self.searchLineEdit.textChanged.connect(self.search_next)
        self.nextButton.clicked.connect(self.search_next)
        self.prevButton.clicked.connect(self.search_prev)

    def setText(self, text):
        self.textEdit.setText(text)

    def setPlainText(self, text):
        self.setText(text)

    def search_next(self):
        text = self.searchLineEdit.text()
        if not text:
            return
        doc = self.textEdit.document()
        cursor = self.textEdit.textCursor()
        cursor = doc.find(text, cursor)
        if cursor.isNull():
            cursor = doc.find(text, 0)
        if not cursor.isNull():
            self.textEdit.setTextCursor(cursor)
            self.textEdit.ensureCursorVisible()

    def search_prev(self):
        text = self.searchLineEdit.text()
        if not text:
            return
        doc = self.textEdit.document()
        cursor = self.textEdit.textCursor()
        pos = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        cursor = doc.find(text, pos, QTextDocument.FindBackward)
        if cursor.isNull():
            cursor = doc.find(text, doc.characterCount() - 1, QTextDocument.FindBackward)
        if not cursor.isNull():
            self.textEdit.setTextCursor(cursor)
            self.textEdit.ensureCursorVisible()


class CommandBlockWidget(QWidget):
    def __init__(self, name="", cmd="", block_type="SSH命令", module="linux", category="", del_callback=None, data_changed_callback=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        # Keep type/module/category as hidden attributes (left panel controls type)
        self._type = block_type
        self._module = module
        self._category = category

        self.nameEdit = LineEdit(self)
        self.nameEdit.setPlaceholderText("标题")
        self.nameEdit.setText(name)

        self.cmdEdit = LineEdit(self)
        self.cmdEdit.setPlaceholderText("命令 / 文件绝对路径")
        self.cmdEdit.setText(cmd)

        self.delBtn = TransparentToolButton(FluentIcon.DELETE, self)
        if del_callback:
            self.delBtn.clicked.connect(del_callback)

        # layout: title + command + delete
        layout.addWidget(self.nameEdit, 1)
        layout.addWidget(self.cmdEdit, 2)
        layout.addWidget(self.delBtn)

        if data_changed_callback:
            self.nameEdit.textChanged.connect(data_changed_callback)
            self.cmdEdit.textChanged.connect(data_changed_callback)


class BlockListWidget(ListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(ListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSpacing(5)

    def add_block(self, name="", cmd="", type_="SSH命令", module='linux', category=''):
        item = QListWidgetItem(self)
        item.setSizeHint(self.get_widget_size_hint())
        item.setData(Qt.UserRole, {"name": name, "cmd": cmd, "type": type_, "module": module, "category": category})
        self.addItem(item)
        self._bind_widget(item)

    def get_widget_size_hint(self):
        return QSize(0, 48)

    def _bind_widget(self, item):
        data = item.data(Qt.UserRole)
        # sanitize stored data to avoid non-string values (bools from clicked signals)
        name = data.get("name", "") if isinstance(data, dict) else ""
        cmd = data.get("cmd", "") if isinstance(data, dict) else ""
        type_ = data.get("type", "SSH命令") if isinstance(data, dict) else "SSH命令"
        module = data.get("module", "linux") if isinstance(data, dict) else "linux"
        category = data.get("category", "") if isinstance(data, dict) else ""
        if isinstance(name, bool) or name is None:
            name = ""
        if isinstance(cmd, bool) or cmd is None:
            cmd = ""

        def on_data_changed():
            if w:
                t = getattr(w, '_type', data.get('type', 'SSH命令'))
                m = getattr(w, '_module', data.get('module', 'linux'))
                c = getattr(w, '_category', data.get('category', ''))
                item.setData(Qt.UserRole, {"name": w.nameEdit.text(), "cmd": w.cmdEdit.text(), "type": t, "module": m, "category": c})

        def on_del():
            self.takeItem(self.row(item))

        w = CommandBlockWidget(name, cmd, type_, module, category, on_del, on_data_changed, self)
        self.setItemWidget(item, w)

    def dropEvent(self, event):
        super().dropEvent(event)
        for i in range(self.count()):
            item = self.item(i)
            if not self.itemWidget(item):
                self._bind_widget(item)

    def get_all_blocks(self):
        cmds = []
        for i in range(self.count()):
            item = self.item(i)
            data = item.data(Qt.UserRole)
            if data and data["name"].strip() and data["cmd"].strip():
                cmds.append({"name": data["name"].strip(), "cmd": data["cmd"].strip(), "type": data.get("type", "SSH命令"), "module": data.get("module", "linux"), "category": data.get("category", "")})
        return cmds

    def clear_blocks(self):
        self.clear()


class GitLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("上传进度")
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        self.logBox = PlainTextEdit(self)
        self.logBox.setReadOnly(True)
        layout.addWidget(self.logBox)

        self.closeBtn = PrimaryPushButton("关闭", self)
        self.closeBtn.clicked.connect(self.accept)
        self.closeBtn.setEnabled(False)
        layout.addWidget(self.closeBtn)

    def append_log(self, text):
        self.logBox.appendPlainText(text)

    def upload_finished(self):
        self.closeBtn.setEnabled(True)


class CommandRunnerThread(QThread):
    line_signal = Signal(str)
    finished_signal = Signal(int)

    def __init__(self, cmd, cwd=None):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self._proc = None

    def run(self):
        import subprocess
        try:
            # use shell for cross-platform simplicity
            self._proc = subprocess.Popen(self.cmd, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, shell=True, encoding='utf-8', errors='replace')
            for line in self._proc.stdout:
                self.line_signal.emit(line.rstrip())
            self._proc.wait()
            code = self._proc.returncode
        except Exception as e:
            self.line_signal.emit(f"[执行出错: {e}]")
            code = -1
        self.finished_signal.emit(code)

    def stop(self):
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass


class UploadWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)
    need_token_signal = Signal()

    def __init__(self, repo_url, name, plugin_obj, token=None):
        super().__init__()
        self.repo_url = repo_url
        self.name = name
        self.plugin_obj = plugin_obj
        self.token = token

    def run_cmd(self, cmd, cwd=None):
        import subprocess
        self.log_signal.emit(f"执行命令: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', shell=True)
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log_signal.emit(line)
            process.wait()
            if process.returncode != 0:
                return False
            return True
        except Exception as e:
            self.log_signal.emit(f"执行出错: {e}")
            return False

    def run(self):
        import tempfile, uuid, shutil
        tmp_dir = os.path.join(tempfile.gettempdir(), f'forensics_plugin_{uuid.uuid4().hex}')
        repo_url = self.repo_url
        if self.token:
            parsed_url = repo_url.replace("https://", f"https://{self.token}@")
        else:
            parsed_url = repo_url

        self.log_signal.emit(f"== 准备上传插件: {self.name} ==")
        self.log_signal.emit("拉取最新仓库 (git clone)...")

        proxy_cmd = []
        app_proxy = get_app_proxy()
        http_proxy = app_proxy or os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY') or ''
        https_proxy = app_proxy or os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY') or ''
        if http_proxy:
            proxy_cmd.extend(['-c', f'http.proxy={http_proxy}'])
        if https_proxy:
            proxy_cmd.extend(['-c', f'https.proxy={https_proxy}'])

        if not self.run_cmd(['git', 'clone', '--depth', '1'] + proxy_cmd + [parsed_url, tmp_dir]):
            self.finished_signal.emit(False, "Clone 失败")
            return

        plugin_file = os.path.join(tmp_dir, f"{self.name}.json")
        self.log_signal.emit(f"写入插件数据到文件: {self.name}.json")

        try:
            with open(plugin_file, 'w', encoding='utf-8') as f:
                json.dump(self.plugin_obj, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log_signal.emit(f"写入文件失败: {e}")
            self.finished_signal.emit(False, str(e))
            return

        self.log_signal.emit("添加文件到 Git (git add)...")
        if not self.run_cmd(['git', 'add', f'{self.name}.json'], cwd=tmp_dir):
            self.finished_signal.emit(False, "Add 失败")
            return

        market_file = os.path.join(tmp_dir, "market.json")
        if os.path.exists(market_file):
            self.log_signal.emit("发现旧版 market.json，执行清理...")
            self.run_cmd(['git', 'rm', 'market.json'], cwd=tmp_dir)

        self.log_signal.emit("提交更改 (git commit)...")
        import subprocess
        status_res = subprocess.run(['git', 'status', '--porcelain'], cwd=tmp_dir, capture_output=True, text=True, shell=True)
        if not status_res.stdout.strip():
            self.log_signal.emit("没有内容需要提交，结束。")
            self.finished_signal.emit(True, "no_change")
            return

        if not self.run_cmd(['git', 'commit', '-m', f'Update plugin: {self.name}'], cwd=tmp_dir):
            self.finished_signal.emit(False, "Commit 失败")
            return

        self.log_signal.emit("推送到远程 (git push)...")
        if not self.run_cmd(['git'] + proxy_cmd + ['push', 'origin', 'main'], cwd=tmp_dir):
            if not self.token:
                self.log_signal.emit("Push 失败。可能是未授权。请求输入 Token。")
                self.need_token_signal.emit()
            else:
                self.finished_signal.emit(False, "Push 带 Token 依然失败。")
            return

        self.log_signal.emit("== 上传成功 ==")
        self.finished_signal.emit(True, "success")


class CommandRunnerDialog(QDialog):
    def __init__(self, parent=None, title='命令输出'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 400)
        layout = QVBoxLayout(self)
        self.outputBox = PlainTextEdit(self)
        self.outputBox.setReadOnly(True)
        layout.addWidget(self.outputBox)

        btnLayout = QHBoxLayout()
        self.stopBtn = PrimaryPushButton('停止', self)
        self.closeBtn = PrimaryPushButton('关闭', self)
        self.closeBtn.setEnabled(False)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.stopBtn)
        btnLayout.addWidget(self.closeBtn)
        layout.addLayout(btnLayout)

        self.thread = None
        self.stopBtn.clicked.connect(self._on_stop)
        self.closeBtn.clicked.connect(self.accept)

    def append_line(self, text: str):
        self.outputBox.appendPlainText(text)
        sb = self.outputBox.verticalScrollBar()
        sb.setValue(sb.maximum())

    def run_command(self, cmd: str, cwd: str = None):
        if self.thread:
            return
        self.thread = CommandRunnerThread(cmd, cwd=cwd)
        self.thread.line_signal.connect(self.append_line)
        self.thread.finished_signal.connect(self._on_finished)
        self.thread.start()
        self.exec()

    def _on_stop(self):
        if self.thread:
            self.thread.stop()

    def _on_finished(self, code: int):
        self.append_line(f"\n[命令退出，退出码={code}]")
        self.closeBtn.setEnabled(True)
        self.thread = None
