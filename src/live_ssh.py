import os
import json
import paramiko
import re
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QFileDialog
from qfluentwidgets import SegmentedWidget
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QTextCursor
from qfluentwidgets import LineEdit, PushButton, SubtitleLabel, ListWidget, EditableComboBox, PrimaryPushButton, InfoBar, InfoBarPosition
from .constants import SETTINGS_DIR, PLUGINS_DIR
from .widgets import SearchableTextEdit


class SshShellThread(QThread):
    output_received = Signal(str)

    def __init__(self, channel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.running = True

    def run(self):
        while self.running and self.channel and not self.channel.closed:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(4096).decode('utf-8', errors='replace')
                    if data:
                        self.output_received.emit(data)
                elif self.channel.recv_stderr_ready():
                    data = self.channel.recv_stderr(4096).decode('utf-8', errors='replace')
                    if data:
                        self.output_received.emit(data)
                else:
                    self.msleep(50)
            except Exception:
                break

    def stop(self):
        self.running = False


class TerminalWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(None)
        self.setWindowTitle("简单终端 - 交互式 SSH")
        self.resize(800, 500)
        self.ssh_client = None
        self.shell_channel = None
        self.shell_thread = None

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(10, 10, 10, 10)

        self.termOutput = SearchableTextEdit(self)
        self.termOutput.textEdit.setReadOnly(True)
        self.termOutput.textEdit.setFont(QFont("Consolas", 10))

        cmdLayout = QHBoxLayout()
        self.termInput = LineEdit(self)
        self.termInput.setPlaceholderText("输入交互式终端命令并按回车...")
        self.termInput.returnPressed.connect(self.execute_terminal_cmd)

        execBtn = PushButton("发送", self)
        execBtn.clicked.connect(self.execute_terminal_cmd)

        cmdLayout.addWidget(self.termInput)
        cmdLayout.addWidget(execBtn)

        self.vBoxLayout.addWidget(self.termOutput, 1)
        self.vBoxLayout.addLayout(cmdLayout)

    def set_ssh_client(self, ssh_client):
        if self.shell_thread:
            self.shell_thread.stop()
            self.shell_thread.wait()
            self.shell_thread = None
        if self.shell_channel:
            self.shell_channel.close()
            self.shell_channel = None

        self.ssh_client = ssh_client
        self.termOutput.textEdit.clear()

        if not self.ssh_client or not self.ssh_client.get_transport() or not self.ssh_client.get_transport().is_active():
            self.append_terminal_output("状态：尚未连接！请先在 SSH 界面输入信息并连接。\n")
            return

        self.start_interactive_shell()

    def start_interactive_shell(self):
        try:
            self.shell_channel = self.ssh_client.invoke_shell(term='xterm', width=120, height=40)
            self.shell_thread = SshShellThread(self.shell_channel)
            self.shell_thread.output_received.connect(self.append_terminal_output)
            self.shell_thread.start()
        except Exception as e:
            self.append_terminal_output(f"\n[启动交互式终端失败: {e}]\n")

    def append_terminal_output(self, text):
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]|\x1B\].*?(?:\x07|\x1B\\)')
        clean_text = ansi_escape.sub('', text)
        cursor = self.termOutput.textEdit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(clean_text)
        self.termOutput.textEdit.setTextCursor(cursor)
        scrollbar = self.termOutput.textEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def execute_terminal_cmd(self):
        if not self.shell_channel or self.shell_channel.closed:
            self.append_terminal_output("\n[错误：SSH 未连接或通道已关闭]\n")
            return
        cmd = self.termInput.text()
        self.termInput.clear()
        try:
            self.shell_channel.send(cmd + "\n")
        except Exception as e:
            self.append_terminal_output(f"\n[执行异常: {e}]\n")

    def closeEvent(self, event):
        if self.shell_thread:
            self.shell_thread.stop()
            self.shell_thread.wait()
            self.shell_thread = None
        event.accept()


class LiveSshInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('liveSshInterface')
        self.ssh_client = None
        self.terminal_window = None

        self.history_file = os.path.join(SETTINGS_DIR, 'ssh_history.json')
        self.ssh_history = {}
        self.plugins_file = os.path.join(PLUGINS_DIR, 'ssh_plugins.json')
        self.plugins_data = {}

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.hBoxLayout.setSpacing(16)

        self.leftPanel = QVBoxLayout()
        self.leftPanel.addWidget(SubtitleLabel("插件选择", self))
        self.pluginList = ListWidget(self)
        self.leftPanel.addWidget(self.pluginList)

        self.openTerminalBtn = PushButton("简单终端", self)
        self.openTerminalBtn.clicked.connect(self.open_terminal)
        self.leftPanel.addWidget(self.openTerminalBtn)

        self.reloadPluginBtn = PushButton("刷新插件", self)
        self.reloadPluginBtn.clicked.connect(self.load_plugins)
        self.leftPanel.addWidget(self.reloadPluginBtn)

        self.hBoxLayout.addLayout(self.leftPanel, 1)

        self.rightPanelWidget = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.rightPanelWidget)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(16)

        self.titleLabel = SubtitleLabel("SSH 动态信息提取", self.rightPanelWidget)
        self.vBoxLayout.addWidget(self.titleLabel)

        self.connLayout = QHBoxLayout()
        self.hostInput = EditableComboBox(self.rightPanelWidget)
        self.hostInput.setPlaceholderText("主机 IP")
        self.hostInput.setMinimumWidth(150)
        self.hostInput.currentTextChanged.connect(self.on_host_changed)
        # hide inputs here; SSH config moved to HomeWidget
        self.hostInput.setVisible(False)

        self.portInput = LineEdit(self.rightPanelWidget)
        self.portInput.setText("22")
        self.portInput.setPlaceholderText("端口")
        self.portInput.setFixedWidth(80)
        self.portInput.setVisible(False)

        self.userInput = LineEdit(self.rightPanelWidget)
        self.userInput.setPlaceholderText("用户名 (例如 root)")
        self.userInput.setVisible(False)

        self.passInput = LineEdit(self.rightPanelWidget)
        self.passInput.setPlaceholderText("密码")
        self.passInput.setVisible(False)

        self.connLayout.addWidget(self.hostInput)
        self.connLayout.addWidget(self.portInput)
        self.connLayout.addWidget(self.userInput)
        self.connLayout.addWidget(self.passInput)

        self.vBoxLayout.addLayout(self.connLayout)

        self.btnLayout = QHBoxLayout()
        self.saveBtn = PushButton("保存当前记录", self.rightPanelWidget)
        self.saveBtn.clicked.connect(self.save_current_history)
        self.saveBtn.setVisible(False)
        self.extractBtn = PrimaryPushButton("按选中插件执行并提取", self.rightPanelWidget)
        self.extractBtn.clicked.connect(self.extract_live_info)
        self.btnLayout.addWidget(self.saveBtn)
        self.btnLayout.addWidget(self.extractBtn)
        self.btnLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.btnLayout)

        # Tabs for live data
        self.tabBar = SegmentedWidget(self.rightPanelWidget)
        self.stackedWidget = QStackedWidget(self.rightPanelWidget)

        self.vBoxLayout.addWidget(self.tabBar)
        self.vBoxLayout.addWidget(self.stackedWidget, 1)

        # ensure tab changes update stacked widget
        try:
            self.tabBar.currentItemChanged.connect(self.on_tab_changed)
        except Exception:
            pass

        self.hBoxLayout.addWidget(self.rightPanelWidget, 3)

        self.tab_widgets = {}

        self.load_history()
        self.load_plugins()

    def open_terminal(self):
        if self.terminal_window is None:
            self.terminal_window = TerminalWindow()
        # ensure we have an active ssh_client; try to connect using saved MainWindow.ssh_info if needed
        if not self.ssh_client or not (self.ssh_client.get_transport() and self.ssh_client.get_transport().is_active()):
            try:
                if hasattr(self.window(), 'ssh_info') and isinstance(self.window().ssh_info, dict) and self.window().ssh_info.get('host'):
                    sinfo = self.window().ssh_info
                    h = sinfo.get('host')
                    p = int(sinfo.get('port', 22))
                    u = sinfo.get('user')
                    pw = sinfo.get('password', '')
                    # attempt connect
                    try:
                        if self.ssh_client:
                            try:
                                self.ssh_client.close()
                            except Exception:
                                pass
                        self.ssh_client = paramiko.SSHClient()
                        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        self.ssh_client.connect(hostname=h, port=p, username=u, password=pw, timeout=8)
                        InfoBar.success('SSH 连接成功', f'{h}:{p} 已连接 (自动)', parent=self, position=InfoBarPosition.TOP)
                    except Exception:
                        # leave ssh_client as None/closed so TerminalWindow will show not-connected message
                        try:
                            if self.ssh_client:
                                self.ssh_client.close()
                        except Exception:
                            pass
            except Exception:
                pass

        self.terminal_window.set_ssh_client(self.ssh_client)
        self.terminal_window.show()
        self.terminal_window.raise_()
        self.terminal_window.activateWindow()

    def try_auto_connect(self):
        """Try to establish SSH connection from MainWindow.ssh_info at startup."""
        try:
            mw = self.window()
            if not mw:
                return False
            if hasattr(mw, 'ssh_info') and isinstance(mw.ssh_info, dict) and mw.ssh_info.get('host'):
                sinfo = mw.ssh_info
                h = sinfo.get('host')
                p = int(sinfo.get('port', 22))
                u = sinfo.get('user')
                pw = sinfo.get('password', '')
                try:
                    if self.ssh_client:
                        try:
                            self.ssh_client.close()
                        except Exception:
                            pass
                    self.ssh_client = paramiko.SSHClient()
                    self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    self.ssh_client.connect(hostname=h, port=p, username=u, password=pw, timeout=8)
                    InfoBar.success('自动 SSH 连接', f'{h}:{p} 已连接', parent=self, position=InfoBarPosition.TOP)
                    return True
                except Exception as e:
                    InfoBar.info('自动连接失败', f'无法连接 {h}:{p} - {e}', parent=self)
                    try:
                        if self.ssh_client:
                            self.ssh_client.close()
                    except Exception:
                        pass
        except Exception:
            pass
        return False

    def on_tab_changed(self, route_key):
        if route_key in self.tab_widgets:
            self.stackedWidget.setCurrentWidget(self.tab_widgets[route_key])

    def clear_live_tabs(self):
        # remove all tabs and stacked widgets from previous runs
        try:
            keys = list(self.tab_widgets.keys())
            for k in keys:
                try:
                    w = self.tab_widgets.get(k)
                    if w:
                        try:
                            self.stackedWidget.removeWidget(w)
                        except Exception:
                            pass
                        try:
                            w.deleteLater()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    # remove from tabBar (Pivot.removeWidget)
                    self.tabBar.removeWidget(k)
                except Exception:
                    try:
                        # fallback: if method name differs
                        self.tabBar.removeWidget(k)
                    except Exception:
                        pass
                try:
                    del self.tab_widgets[k]
                except Exception:
                    pass
        except Exception:
            self.tab_widgets = {}

    def load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.ssh_history = json.load(f)
                self.hostInput.clear()
                self.hostInput.addItems(list(self.ssh_history.keys()))
                self.hostInput.setCurrentIndex(-1)
                self.hostInput.setText("")
        except Exception as e:
            print(f"Load history failed: {e}")

    def load_plugins(self):
        try:
            if os.path.exists(self.plugins_file):
                with open(self.plugins_file, 'r', encoding='utf-8') as f:
                    self.plugins_data = json.load(f)
            else:
                self.plugins_data = {}
            self.pluginList.clear()
            for name, pdata in self.plugins_data.items():
                blocks = []
                if isinstance(pdata, dict):
                    blocks = pdata.get('blocks', [])
                elif isinstance(pdata, list):
                    blocks = pdata
                has_ssh = False
                for b in blocks:
                    if isinstance(b, dict) and ("SSH" in (b.get('type') or '') or "命令" in (b.get('type') or '')):
                        has_ssh = True
                        break
                if has_ssh:
                    self.pluginList.addItem(name)
            if self.pluginList.count() > 0:
                self.pluginList.setCurrentRow(0)
        except Exception as e:
            print(f"Load plugins failed: {e}")

    def add_tab_for_category(self, route_key, tab_name, content):
        # allow optional action button by passing a tuple in content: (text, action_label, action_callback)
        widget_container = QWidget(self)
        v = QVBoxLayout(widget_container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        text = content
        action_label = None
        action_callback = None
        if isinstance(content, tuple) and len(content) == 3:
            text, action_label, action_callback = content

        te = SearchableTextEdit(self)
        te.setText(text)
        v.addWidget(te, 1)

        if action_label and callable(action_callback):
            btn_layout = QHBoxLayout()
            btn_layout.addStretch(1)
            act_btn = PushButton(action_label, self)
            act_btn.clicked.connect(action_callback)
            btn_layout.addWidget(act_btn)
            v.addLayout(btn_layout)

        self.stackedWidget.addWidget(widget_container)
        # store the container (stacked widget holds the container)
        self.tab_widgets[route_key] = widget_container
        self.tabBar.addItem(route_key, tab_name)

    def save_current_history(self):
        import json
        host = self.hostInput.text().strip()
        port = self.portInput.text().strip()
        user = self.userInput.text().strip()
        password = self.passInput.text()
        if host and user:
            self.ssh_history[host] = {"port": port, "user": user, "password": password}
            try:
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump(self.ssh_history, f, indent=4, ensure_ascii=False)
                current_text = self.hostInput.text()
                self.hostInput.clear()
                self.hostInput.addItems(list(self.ssh_history.keys()))
                self.hostInput.setText(current_text)
            except Exception as e:
                print(f"Save history failed: {e}")

    def on_host_changed(self, host):
        # keep backward compatibility if history exists; otherwise prefer HomeWidget ssh_info
        if host in self.ssh_history:
            info = self.ssh_history[host]
            self.portInput.setText(info.get("port", "22"))
            self.userInput.setText(info.get("user", ""))
            self.passInput.setText(info.get("password", ""))

    def extract_live_info(self):
        # simplified: only perform basic connection and close
        # prefer SSH info from HomeWidget (MainWindow.ssh_info)
        host = ''
        port_str = ''
        user = ''
        password = ''
        try:
            mw = self.window()
            if hasattr(mw, 'ssh_info') and isinstance(mw.ssh_info, dict) and mw.ssh_info.get('host'):
                sinfo = mw.ssh_info
                host = sinfo.get('host', '').strip()
                port_str = str(sinfo.get('port', '22')).strip()
                user = sinfo.get('user', '').strip()
                password = sinfo.get('password', '')
            else:
                host = self.hostInput.text().strip()
                port_str = self.portInput.text().strip()
                user = self.userInput.text().strip()
                password = self.passInput.text()
        except Exception:
            host = self.hostInput.text().strip()
            port_str = self.portInput.text().strip()
            user = self.userInput.text().strip()
            password = self.passInput.text()

        if not host or not user:
            return
        try:
            port = int(port_str)
        except Exception:
            return
        # ensure ssh_client is set and connected
        try:
            # clear previous run tabs to start fresh
            try:
                self.clear_live_tabs()
            except Exception:
                pass
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                except Exception:
                    pass
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                self.ssh_client.connect(hostname=host, port=port, username=user, password=password, timeout=10)
                InfoBar.success('SSH 连接成功', f'{host}:{port} 已连接', parent=self, position=InfoBarPosition.TOP)
            except Exception as e:
                InfoBar.error('SSH 连接失败', str(e), parent=self, position=InfoBarPosition.TOP)
                return

            # determine selected plugin/commands
            current_item = self.pluginList.currentItem()
            if current_item:
                plugin_name = current_item.text()
                p_data = self.plugins_data.get(plugin_name, [])
                cmds = p_data.get('blocks', []) if isinstance(p_data, dict) else p_data
            else:
                cmds = [{'name': '系统信息', 'cmd': 'uname -a'}]

            # execute each command and create a tab showing output
            executed = 0
            for b in (cmds or []):
                cmd = b.get('cmd') if isinstance(b, dict) else None
                title = b.get('name', '') if isinstance(b, dict) else ''
                btype = b.get('type', '') if isinstance(b, dict) else ''
                if not cmd:
                    continue
                # If this block is a file-extraction type, do NOT execute over SSH here.
                # Instead, show guidance to use the Extractor (离线取证) interface which reads files from mapped paths.
                if '文件' in (btype or '') or '提取' in (btype or ''):
                    # prepare action to jump to extractor and run the specific plugin block
                    def make_jump(gname, bname, base_cmd):
                        def jump():
                            try:
                                main_win = self.window()
                                if hasattr(main_win, 'extractorInterface'):
                                    ei = getattr(main_win, 'extractorInterface')
                                    # set base path hint from command if possible
                                    base_path = None
                                    import re
                                    m = re.search(r'/[^\s;]+', base_cmd)
                                    if not m:
                                        m = re.search(r'[A-Za-z]:\\\\[^\\s;]+', base_cmd)
                                    if m:
                                        base_path = m.group(0)
                                    ei.select_and_run_plugin(gname, bname, base_path=base_path)
                            except Exception:
                                pass
                        return jump

                    content_text = f"此为文件提取型积木，因需读取映射盘文件，工具不会通过 SSH 在此处打开终端。\n\n建议：切换到【离线取证 (提取盘)】页面，设置映射路径后在左侧选择插件并运行提取。\n\n命令/路径示例：\n{cmd}"
                    route_key = f"{plugin_name}-{title}-file" if current_item else (title or 'file_output')
                    tab_name = (title or plugin_name or '文件输出')
                    try:
                        self.add_tab_for_category(route_key, tab_name, (content_text, '跳转并在离线取证运行', make_jump(plugin_name, title, cmd)))
                    except Exception:
                        print(content_text)
                    continue

                try:
                    stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
                    out = stdout.read().decode('utf-8', errors='replace')
                    err = stderr.read().decode('utf-8', errors='replace')
                    content = out if out else err
                    executed += 1
                except Exception as e:
                    content = f"[执行命令失败: {e}]"

                # add a new tab to display result (route key unique)
                route_key = f"{plugin_name}-{title}" if current_item else title or 'output'
                tab_name = title or plugin_name or '输出'
                try:
                    self.add_tab_for_category(route_key, tab_name, content)
                except Exception:
                    # fallback: append to console
                    print(content)

            if executed == 0:
                InfoBar.info('未执行命令', '未检测到可执行的插件积木或命令为空。请检查所选插件。', parent=self)
            else:
                InfoBar.success('执行完成', f'已执行 {executed} 条命令，结果以标签页展示。', parent=self, position=InfoBarPosition.TOP)

        except Exception as e:
            print(f"SSH connect failed: {e}")
