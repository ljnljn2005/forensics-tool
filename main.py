import sys
import os
import glob
import json
import paramiko
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextDocument, QTextCursor
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QStackedWidget, QListWidgetItem
from qfluentwidgets import PasswordLineEdit

# Create QApplication before importing qfluentwidgets as a workaround
# if globals instantiate Qt Objects.
QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
app = QApplication(sys.argv)

from qfluentwidgets import (NavigationItemPosition, FluentWindow, SubtitleLabel, FluentIcon, 
                            BodyLabel, LineEdit, PushButton, PrimaryPushButton, TextEdit, 
                            SegmentedWidget, setTheme, Theme, SearchLineEdit, ToolButton, ComboBox, EditableComboBox,
                            ListWidget, ScrollArea, CardWidget, TransparentToolButton)

class SettingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('settingInterface')
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)
        
        self.titleLabel = SubtitleLabel("设置", self)
        self.vBoxLayout.addWidget(self.titleLabel)
        
        # Theme Setting
        self.themeLayout = QHBoxLayout()
        self.themeLabel = BodyLabel("应用主题:", self)
        self.themeComboBox = ComboBox(self)
        self.themeComboBox.addItems(["跟随系统", "浅色模式 (Light)", "深色模式 (Dark)"])
        self.themeLayout.addWidget(self.themeLabel)
        self.themeLayout.addWidget(self.themeComboBox)
        self.themeLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.themeLayout)
        
        # Proxy Setting
        self.proxyLayout = QHBoxLayout()
        self.proxyLabel = BodyLabel("网络代理 (用于市场和GitHub下载):", self)
        from qfluentwidgets import LineEdit
        self.proxyEdit = LineEdit(self)
        self.proxyEdit.setPlaceholderText("例如: http://127.0.0.1:7897 (留空则不使用代理)")
        self.proxyEdit.setFixedWidth(300)
        self.proxyEdit.setText(get_app_proxy())
        
        self.proxyLayout.addWidget(self.proxyLabel)
        self.proxyLayout.addWidget(self.proxyEdit)
        self.proxyLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.proxyLayout)
        
        self.vBoxLayout.addStretch(1)
        
        self.themeComboBox.currentIndexChanged.connect(self.on_theme_changed)
        self.proxyEdit.textChanged.connect(self.on_proxy_changed)

    def on_theme_changed(self, index):
        if index == 0:
            setTheme(Theme.AUTO)
        elif index == 1:
            setTheme(Theme.LIGHT)
        elif index == 2:
            setTheme(Theme.DARK)
            
    def on_proxy_changed(self, text):
        save_app_proxy(text.strip())

class SearchableTextEdit(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(10)
        
        # Search bar
        self.searchLayout = QHBoxLayout()
        self.searchLineEdit = SearchLineEdit(self)
        self.searchLineEdit.setPlaceholderText("搜索关键字...")
        self.searchLineEdit.textChanged.connect(self.search_text)
        self.searchLineEdit.returnPressed.connect(self.search_next)
        
        self.prevButton = ToolButton(FluentIcon.UP, self)
        self.prevButton.setToolTip("查找上一个")
        self.prevButton.clicked.connect(self.search_prev)
        
        self.nextButton = ToolButton(FluentIcon.DOWN, self)
        self.nextButton.setToolTip("查找下一个")
        self.nextButton.clicked.connect(self.search_next)
        
        self.searchLayout.addWidget(self.searchLineEdit)
        self.searchLayout.addWidget(self.prevButton)
        self.searchLayout.addWidget(self.nextButton)
        self.vBoxLayout.addLayout(self.searchLayout)
        
        # Text edit
        self.textEdit = TextEdit(self)
        self.textEdit.setReadOnly(True)
        # Using QFont guarantees it adapts to qfluentwidgets theme colors automatically
        font = QFont("Consolas", 10)
        self.textEdit.setFont(font)
        self.vBoxLayout.addWidget(self.textEdit, 1)
        
    def setText(self, text):
        self.textEdit.setText(text)
        
    def search_text(self, text):
        # Triggered when text changes, just search next
        self.search_next()

    def search_next(self):
        text = self.searchLineEdit.text()
        cursor = self.textEdit.textCursor()
        cursor.clearSelection()
        self.textEdit.setTextCursor(cursor)
        
        if not text:
            cursor.setPosition(0)
            self.textEdit.setTextCursor(cursor)
            return
            
        document = self.textEdit.document()
        # Find next occurrence
        cursor = document.find(text, self.textEdit.textCursor())
        
        if cursor.isNull():
            # If not found from current position, wrap to beginning
            cursor = self.textEdit.textCursor()
            cursor.setPosition(0)
            cursor = document.find(text, cursor)
            
        if not cursor.isNull():
            self.textEdit.setTextCursor(cursor)
            self.textEdit.ensureCursorVisible()

    def search_prev(self):
        text = self.searchLineEdit.text()
        cursor = self.textEdit.textCursor()
        
        if not text:
            return
            
        document = self.textEdit.document()
        options = QTextDocument.FindBackward
        
        # Position is start of current selection to avoid finding the exact same match we're on
        position = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        cursor = document.find(text, position, options)
        
        if cursor.isNull():
            # Wrap to end
            cursor = document.find(text, document.characterCount() - 1, options)
            
        if not cursor.isNull():
            self.textEdit.setTextCursor(cursor)
            self.textEdit.ensureCursorVisible()

class ExtractorInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('extractorInterface')
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)
        
        self.titleLabel = SubtitleLabel("Linux 映射盘信息提取", self)
        self.vBoxLayout.addWidget(self.titleLabel)
        
        # Path selection layout
        self.pathLayout = QHBoxLayout()
        self.pathLabel = BodyLabel("映射磁盘根路径:", self)
        self.pathLineEdit = LineEdit(self)
        self.pathLineEdit.setPlaceholderText(r"例如 C:\hlnet\3-1774527990\ubuntu-vg(...)\分区0")
        self.browseButton = PushButton("浏览...", self)
        self.browseButton.clicked.connect(self.browse_folder)
        
        self.pathLayout.addWidget(self.pathLabel)
        self.pathLayout.addWidget(self.pathLineEdit)
        self.pathLayout.addWidget(self.browseButton)
        
        self.vBoxLayout.addLayout(self.pathLayout)
        
        # Extractor Action
        self.btnLayout = QHBoxLayout()
        self.btnLayout.setSpacing(10)
        self.extractAllButton = PrimaryPushButton("一键提取", self)
        self.extractAllButton.clicked.connect(self.extract_all)
        
        self.btnLayout.addWidget(self.extractAllButton)
        self.btnLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.btnLayout)
        
        # Segmented Tabs for Categories
        self.tabBar = SegmentedWidget(self)
        self.stackedWidget = QStackedWidget(self)
        
        self.vBoxLayout.addWidget(self.tabBar)
        self.vBoxLayout.addWidget(self.stackedWidget, 1)
        
        # Store route_key mapping to widget
        self.tab_widgets = {}
        self.tabBar.currentItemChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, route_key):
        if route_key in self.tab_widgets:
            self.stackedWidget.setCurrentWidget(self.tab_widgets[route_key])

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择被映射的Linux根目录")
        if folder:
            self.pathLineEdit.setText(folder)

    def read_file_content(self, base_path, rel_path):
        full_path = os.path.join(base_path, rel_path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except Exception as e:
                return f"[读取失败: {e}]"
        return None

    def find_files(self, base_path, exact_files, glob_patterns):
        results = {}
        for rel_path in exact_files:
            curr_path = rel_path.replace('/', os.sep)
            content = self.read_file_content(base_path, curr_path)
            if content is not None:
                results[rel_path] = content
                
        for pattern in glob_patterns:
            curr_pattern = os.path.join(base_path, pattern.replace('/', os.sep))
            for filepath in glob.glob(curr_pattern):
                if os.path.isfile(filepath):
                    rel_name = os.path.relpath(filepath, base_path).replace(os.sep, '/')
                    if rel_name not in results:
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                results[rel_name] = f.read()
                        except Exception as e:
                            results[rel_name] = f"[读取失败: {e}]"
        return results

    def _create_text_edit(self):
        # We now return the composite searchable widget
        return SearchableTextEdit(self)

    def add_tab_for_category(self, route_key, tab_name, files_dict):
        searchable_edit = self._create_text_edit()
        
        if not files_dict:
            searchable_edit.setText("未找到相关配置文件。")
        else:
            output_text = ""
            for name, content in files_dict.items():
                output_text += f"{'='*30} {name} {'='*30}\n{content}\n\n"
            searchable_edit.setText(output_text)
            
        self.stackedWidget.addWidget(searchable_edit)
        self.tab_widgets[route_key] = searchable_edit
        self.tabBar.addItem(route_key, tab_name)

    def extract_all(self):
        base_path = self.pathLineEdit.text().strip()
        
        # Clear existing tabs
        self.tabBar.clear()
        self.tab_widgets.clear()
        for i in range(self.stackedWidget.count() - 1, -1, -1):
            widget = self.stackedWidget.widget(i)
            self.stackedWidget.removeWidget(widget)
            widget.deleteLater()
            
        if not base_path or not os.path.exists(base_path):
            text_edit = self._create_text_edit()
            text_edit.setText("错误: 无效路径。请选择或输入一个存在的映射盘目录。")
            self.stackedWidget.addWidget(text_edit)
            self.tab_widgets["错误"] = text_edit
            self.tabBar.addItem("错误", "错误信息")
            self.tabBar.setCurrentItem("错误")
            return

        # Network
        net_exact = ['etc/hostname', 'etc/hosts', 'etc/resolv.conf', 'etc/network/interfaces']
        net_glob = ['etc/network/interfaces.d/*', 'etc/netplan/*.yaml', 'etc/NetworkManager/system-connections/*']
        net_res = self.find_files(base_path, net_exact, net_glob)
        self.add_tab_for_category("network", "网络配置", net_res)

        # SSH
        ssh_exact = ['etc/ssh/sshd_config', 'etc/ssh/ssh_config', 'root/.ssh/config', 'root/.ssh/id_rsa', 'root/.ssh/id_ed25519', 'root/.ssh/authorized_keys', 'root/.ssh/known_hosts']
        ssh_glob = ['home/*/.ssh/config', 'home/*/.ssh/id_rsa', 'home/*/.ssh/id_ed25519', 'home/*/.ssh/authorized_keys', 'home/*/.ssh/known_hosts', 'home/*/.ssh/*.pub', 'root/.ssh/*.pub']
        ssh_res = self.find_files(base_path, ssh_exact, ssh_glob)
        self.add_tab_for_category("ssh", "SSH日志与配置", ssh_res)

        # Other System Info
        sys_exact = ['etc/os-release', 'etc/fstab', 'etc/passwd', 'etc/shadow', 'etc/timezone']
        sys_glob = ['etc/cron.*/*', 'var/spool/cron/crontabs/*']
        sys_res = self.find_files(base_path, sys_exact, sys_glob)
        self.add_tab_for_category("system", "系统配置文件", sys_res)
        
        # User History
        hist_exact = ['root/.bash_history', 'root/.zsh_history', 'root/.viminfo']
        hist_glob = ['home/*/.bash_history', 'home/*/.zsh_history', 'home/*/.viminfo']
        hist_res = self.find_files(base_path, hist_exact, hist_glob)
        self.add_tab_for_category("history", "命令历史", hist_res)

        # Set default active tab
        self.tabBar.setCurrentItem("network")


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


import re

class TerminalWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(None) # Free floating window
        self.setWindowTitle("简单终端 - 交互式 SSH")
        self.resize(800, 500)
        self.ssh_client = None
        self.shell_channel = None
        self.shell_thread = None
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(10, 10, 10, 10)
        
        self.termOutput = TextEdit(self)
        self.termOutput.setReadOnly(True)
        self.termOutput.setFont(QFont("Consolas", 10))
        
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
        self.termOutput.clear()
        
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
        import re
        from PySide6.QtGui import QTextCursor
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]|\x1B\].*?(?:\x07|\x1B\\)')
        clean_text = ansi_escape.sub('', text)
        
        cursor = self.termOutput.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(clean_text)
        self.termOutput.setTextCursor(cursor)
        scrollbar = self.termOutput.verticalScrollBar()
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
        
        import os, json
        self.history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssh_history.json')
        self.ssh_history = {}
        self.plugins_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssh_plugins.json')
        self.plugins_data = {}
        
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.hBoxLayout.setSpacing(16)
        
        # Left Panel: Plugin Selector
        self.leftPanel = QVBoxLayout()
        self.leftPanel.addWidget(SubtitleLabel("插件选择", self))
        self.pluginList = ListWidget(self)
        self.leftPanel.addWidget(self.pluginList)
        
        # Simple Terminal Button
        self.openTerminalBtn = PushButton("简单终端", self)
        self.openTerminalBtn.clicked.connect(self.open_terminal)
        self.leftPanel.addWidget(self.openTerminalBtn)
        
        self.reloadPluginBtn = PushButton("刷新插件", self)
        self.reloadPluginBtn.clicked.connect(self.load_plugins)
        self.leftPanel.addWidget(self.reloadPluginBtn)
        
        self.leftPanel.setContentsMargins(0, 0, 10, 0)
        self.hBoxLayout.addLayout(self.leftPanel, 1)

        # Right Panel: SSH Info
        self.rightPanelWidget = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.rightPanelWidget)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(16)
        
        self.titleLabel = SubtitleLabel("SSH 动态信息提取", self.rightPanelWidget)
        self.vBoxLayout.addWidget(self.titleLabel)
        
        # Connection Layout
        self.connLayout = QHBoxLayout()
        
        self.hostInput = EditableComboBox(self.rightPanelWidget)
        self.hostInput.setPlaceholderText("主机 IP")
        self.hostInput.setMinimumWidth(150)
        self.hostInput.currentTextChanged.connect(self.on_host_changed)
        
        self.portInput = LineEdit(self.rightPanelWidget)
        self.portInput.setText("22")
        self.portInput.setPlaceholderText("端口")
        self.portInput.setFixedWidth(80)
        
        self.userInput = LineEdit(self.rightPanelWidget)
        self.userInput.setPlaceholderText("用户名 (例如 root)")
        
        self.passInput = PasswordLineEdit(self.rightPanelWidget)
        self.passInput.setPlaceholderText("密码")
        
        self.connLayout.addWidget(self.hostInput)
        self.connLayout.addWidget(self.portInput)
        self.connLayout.addWidget(self.userInput)
        self.connLayout.addWidget(self.passInput)
        
        self.vBoxLayout.addLayout(self.connLayout)
        
        # Action Buttons Layout
        self.btnLayout = QHBoxLayout()
        self.btnLayout.setSpacing(10)
        
        self.saveBtn = PushButton("保存当前记录", self.rightPanelWidget)
        self.saveBtn.clicked.connect(self.save_current_history)
        
        self.extractBtn = PrimaryPushButton("按选中插件执行并提取", self.rightPanelWidget)
        self.extractBtn.clicked.connect(self.extract_live_info)
        
        self.btnLayout.addWidget(self.saveBtn)
        self.btnLayout.addWidget(self.extractBtn)
        self.btnLayout.addStretch(1)
        
        self.vBoxLayout.addLayout(self.btnLayout)
        
        # Segmented Tabs for Live Data
        self.tabBar = SegmentedWidget(self.rightPanelWidget)
        self.stackedWidget = QStackedWidget(self.rightPanelWidget)
        
        self.vBoxLayout.addWidget(self.tabBar)
        self.vBoxLayout.addWidget(self.stackedWidget, 1)
        
        self.hBoxLayout.addWidget(self.rightPanelWidget, 3)

        # Store route_key mapping to widget
        self.tab_widgets = {}
        self.tabBar.currentItemChanged.connect(self.on_tab_changed)

        # Load history and plugins
        self.load_history()
        self.load_plugins()

    def open_terminal(self):
        if self.terminal_window is None:
            self.terminal_window = TerminalWindow()
        self.terminal_window.set_ssh_client(self.ssh_client)
        self.terminal_window.show()
        self.terminal_window.raise_()
        self.terminal_window.activateWindow()

    def load_history(self):
        import os, json
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
        import os, json
        try:
            if os.path.exists(self.plugins_file):
                with open(self.plugins_file, 'r', encoding='utf-8') as f:
                    self.plugins_data = json.load(f)
            else:
                self.plugins_data = {
                    "默认基础信息": [
                        {"name": "进程信息 (ps)", "cmd": "ps aux"},
                        {"name": "网络端口 (netstat)", "cmd": "netstat -ntlp || ss -ntlp"},
                        {"name": "当前登录用户 (w)", "cmd": "w"},
                        {"name": "系统信息 (uname)", "cmd": "uname -a"},
                        {"name": "磁盘挂载 (df)", "cmd": "df -h"}
                    ],
                    "面板管理端解析": [
                        {"name": "宝塔面板 (BT)", "cmd": "echo '面板入口:'; cat /www/server/panel/data/admin_path.pl 2>/dev/null; echo '\n面板端口:'; cat /www/server/panel/data/port.pl 2>/dev/null; echo '\n面板默认信息:'; cat /www/server/panel/default.pl 2>/dev/null; echo '\n\nBT命令行信息:'; bt default 2>/dev/null", "type": "SSH命令"},
                        {"name": "1Panel 面板", "cmd": "1pctl user-info 2>/dev/null || echo '未找到 1Panel 或命令执行失败'", "type": "SSH命令"}
                    ]
                }
                
            self.pluginList.clear()
            for name in self.plugins_data.keys():
                self.pluginList.addItem(name)
                
            if self.pluginList.count() > 0:
                self.pluginList.setCurrentRow(0)
        except Exception as e:
            print(f"Load plugins failed: {e}")

    def save_current_history(self):
        import json
        host = self.hostInput.text().strip()
        port = self.portInput.text().strip()
        user = self.userInput.text().strip()
        password = self.passInput.text()
        
        if host and user:
            self.ssh_history[host] = {
                "port": port,
                "user": user,
                "password": password
            }
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
        if host in self.ssh_history:
            info = self.ssh_history[host]
            self.portInput.setText(info.get("port", "22"))
            self.userInput.setText(info.get("user", ""))
            self.passInput.setText(info.get("password", ""))

    def on_tab_changed(self, route_key):
        if route_key in self.tab_widgets:
            self.stackedWidget.setCurrentWidget(self.tab_widgets[route_key])

    def _create_text_edit(self):
        return SearchableTextEdit(self)

    def add_tab_for_category(self, route_key, tab_name, content):
        widget = self._create_text_edit()
        widget.setText(content)
        self.stackedWidget.addWidget(widget)
        self.tab_widgets[route_key] = widget
        self.tabBar.addItem(route_key, tab_name)

    def exec_ssh_command(self, ssh, cmd):
        import re
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
            out = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]|\x1B\].*?(?:\x07|\x1B\\)')
            out = ansi_escape.sub('', out)
            err = ansi_escape.sub('', err)
            
            if err:
                return f"--- 标准输出 ---\n{out}\n\n--- 错误输出 ---\n{err}"
            return out if out else "[无输出]"
        except Exception as e:
            return f"[执行异常: {e}]"

    def extract_live_info(self):
        host = self.hostInput.text().strip()
        port_str = self.portInput.text().strip()
        user = self.userInput.text().strip()
        password = self.passInput.text()

        self.tabBar.clear()
        self.tab_widgets.clear()
        for i in range(self.stackedWidget.count() - 1, -1, -1):
            widget = self.stackedWidget.widget(i)
            self.stackedWidget.removeWidget(widget)
            widget.deleteLater()

        if not host or not user:
            self.add_tab_for_category("Error", "错误", "缺少主机IP或用户名。")
            self.tabBar.setCurrentItem("Error")
            return
            
        try:
            port = int(port_str)
        except ValueError:
            self.add_tab_for_category("Error", "错误", "端口必须为数字。")
            self.tabBar.setCurrentItem("Error")
            return

        if self.ssh_client:
            self.ssh_client.close()
            
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        self.add_tab_for_category("Log", "连接日志", "")
        log_widget = self.tab_widgets["Log"]
        self.tabBar.setCurrentItem("Log")

        try:
            log_widget.setText(f"正在连接到 {user}@{host}:{port} ...")
            QApplication.processEvents()
            
            self.ssh_client.connect(hostname=host, port=port, username=user, password=password, timeout=10)
            log_widget.setText(log_widget.textEdit.toPlainText() + "\n连接成功！开始提取信息...")
            QApplication.processEvents()

            current_item = self.pluginList.currentItem()
            if current_item:
                plugin_name = current_item.text()
                p_data = self.plugins_data.get(plugin_name, [])
                cmds = p_data.get("blocks", []) if isinstance(p_data, dict) else p_data
            else:
                cmds = [{"name": "默认测试", "cmd": "w"}]

            for i, cmd_info in enumerate(cmds):
                tab_name = cmd_info.get("name", f"任务 {i+1}")
                cmd = cmd_info.get("cmd", "")
                block_type = cmd_info.get("type", "SSH命令")
                
                if cmd:
                    if block_type == "文件提取":
                        result = self.exec_sftp_download(self.ssh_client, cmd)
                    else:
                        result = self.exec_ssh_command(self.ssh_client, cmd)
                    route_key = f"tab_{i}"
                    self.add_tab_for_category(route_key, tab_name, result)
                    QApplication.processEvents()
            
            log_widget.setText(log_widget.textEdit.toPlainText() + "\n\n提取完毕！")
            
            # Reconnect terminal if open
            if self.terminal_window and self.terminal_window.isVisible():
                self.terminal_window.set_ssh_client(self.ssh_client)

        except Exception as e:
            log_widget.setText(log_widget.textEdit.toPlainText() + f"\n连接或执行失败:\n{e}")
            if self.ssh_client:
                self.ssh_client.close()
                self.ssh_client = None


class CommandBlockWidget(QWidget):
    def __init__(self, name="", cmd="", block_type="SSH命令", del_callback=None, data_changed_callback=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        from qfluentwidgets import ComboBox
        self.typeCombo = ComboBox(self)
        self.typeCombo.addItems(["SSH命令", "文件提取"])
        self.typeCombo.setCurrentText(block_type if block_type in ["SSH命令", "文件提取"] else "SSH命令")
        self.typeCombo.setFixedWidth(100)
        
        self.nameEdit = LineEdit(self)
        self.nameEdit.setPlaceholderText("标题")
        self.nameEdit.setText(name)
        
        self.cmdEdit = LineEdit(self)
        self.cmdEdit.setPlaceholderText("命令 / 文件绝对路径")
        self.cmdEdit.setText(cmd)
        
        self.delBtn = TransparentToolButton(FluentIcon.DELETE, self)
        if del_callback:
            self.delBtn.clicked.connect(del_callback)
            
        layout.addWidget(self.typeCombo)
        layout.addWidget(self.nameEdit, 1)
        layout.addWidget(self.cmdEdit, 2)
        layout.addWidget(self.delBtn)

        if data_changed_callback:
            self.nameEdit.textChanged.connect(data_changed_callback)
            self.cmdEdit.textChanged.connect(data_changed_callback)
            self.typeCombo.currentTextChanged.connect(data_changed_callback)

class BlockListWidget(ListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(ListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSpacing(5)

    def add_block(self, name="", cmd="", type_="SSH命令"):
        item = QListWidgetItem(self)
        item.setSizeHint(self.get_widget_size_hint())
        item.setData(Qt.UserRole, {"name": name, "cmd": cmd, "type": type_})
        self.addItem(item)
        self._bind_widget(item)

    def get_widget_size_hint(self):
        from PySide6.QtCore import QSize
        return QSize(0, 48)

    def _bind_widget(self, item):
        data = item.data(Qt.UserRole)
        
        def on_data_changed():
            # Update data in item when lineEdit changed
            if w:
                item.setData(Qt.UserRole, {"name": w.nameEdit.text(), "cmd": w.cmdEdit.text(), "type": w.typeCombo.currentText()})

        def on_del():
            self.takeItem(self.row(item))

        w = CommandBlockWidget(data["name"], data["cmd"], data.get("type", "SSH命令"), on_del, on_data_changed, self)
        self.setItemWidget(item, w)

    def dropEvent(self, event):
        super().dropEvent(event)
        # Re-bind widgets after internal drag drop since Qt QListWidget
        # drops the widget instance during standard internal move.
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
                cmds.append({"name": data["name"].strip(), "cmd": data["cmd"].strip(), "type": data.get("type", "SSH命令")})
        return cmds

    def clear_blocks(self):
        self.clear()

from PySide6.QtCore import QThread, Signal
from qfluentwidgets import PlainTextEdit, PrimaryPushButton

from PySide6.QtWidgets import QDialog
class GitLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("上传进度")
        self.resize(600, 400)
        from PySide6.QtWidgets import QVBoxLayout
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

class UploadWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str) # success, error_message or token validation request
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
            # Popen to capture stdout and stderr
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
        import os, tempfile, json, uuid, shutil
        
        # 每次都使用全新的临时目录来Clone，完全避免Windows下旧.git对象锁定时Pull抛错或无法删除的问题
        tmp_dir = os.path.join(tempfile.gettempdir(), f'forensics_plugin_{uuid.uuid4().hex}')
        
        repo_url = self.repo_url
        if self.token:
            parsed_url = repo_url.replace("https://", f"https://{self.token}@")
        else:
            parsed_url = repo_url
            
        self.log_signal.emit(f"== 准备上传插件: {self.name} ==")
        self.log_signal.emit("拉取最新仓库 (git clone)...")
        
        # 直接全新 clone，无惧历史冲突 (添加系统代理支持解决 Connection reset)
        import os as _os
        proxy_cmd = []
        # 优先读取 App 的自定义代理
        app_proxy = get_app_proxy()
        http_proxy = app_proxy or _os.environ.get('http_proxy') or _os.environ.get('HTTP_PROXY') or ''
        https_proxy = app_proxy or _os.environ.get('https_proxy') or _os.environ.get('HTTPS_PROXY') or ''
        
        # 将代理自动注入给 git 命令
        proxy_cmd = []
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
        # Check if anything to commit
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


class PluginEditorInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('pluginEditorInterface')
        import os, json
        self.plugins_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssh_plugins.json')
        self.plugins_data = {}
        self.current_plugin = None

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.hBoxLayout.setSpacing(16)

        self.leftPanel = QVBoxLayout()
        self.leftPanel.addWidget(SubtitleLabel("保存的插件", self))

        # 搜索栏：可搜索插件内容和目录中文件内容
        self.searchLayout = QHBoxLayout()
        self.searchEdit = LineEdit(self)
        self.searchEdit.setPlaceholderText("搜索插件或目录内容...")
        self.searchBtn = PushButton("搜索", self)
        self.searchBtn.clicked.connect(self.perform_search)
        self.chooseDirBtn = PushButton("选择目录", self)
        self.chooseDirBtn.clicked.connect(self.choose_search_dir)
        self.searchLayout.addWidget(self.searchEdit, 1)
        self.searchLayout.addWidget(self.searchBtn)
        self.searchLayout.addWidget(self.chooseDirBtn)
        self.leftPanel.addLayout(self.searchLayout)

        self.pluginList = ListWidget(self)
        self.pluginList.itemClicked.connect(self.on_plugin_selected)
        self.leftPanel.addWidget(self.pluginList)

        # 搜索结果列表（展示插件匹配或文件匹配）
        self.searchResults = ListWidget(self)
        self.searchResults.itemClicked.connect(self.on_search_result_clicked)
        self.leftPanel.addWidget(SubtitleLabel("搜索结果", self))
        self.leftPanel.addWidget(self.searchResults, 1)
        
        self.leftBtnLayout = QHBoxLayout()
        self.newPluginBtn = PushButton("新建", self)
        self.newPluginBtn.clicked.connect(self.new_plugin)
        self.delPluginBtn = PushButton("删除", self)
        self.delPluginBtn.clicked.connect(self.delete_plugin)
        self.leftBtnLayout.addWidget(self.newPluginBtn)
        self.leftBtnLayout.addWidget(self.delPluginBtn)
        self.leftPanel.addLayout(self.leftBtnLayout)
        
        self.hBoxLayout.addLayout(self.leftPanel, 1)

        self.rightPanel = QVBoxLayout()
        self.rightPanel.addWidget(SubtitleLabel("编辑插件区域", self))
        
        self.nameLayout = QHBoxLayout()
        self.nameLayout.addWidget(BodyLabel("插件名称: "))
        self.pluginNameEdit = LineEdit(self)
        self.nameLayout.addWidget(self.pluginNameEdit, 1)
        self.rightPanel.addLayout(self.nameLayout)

        self.infoLayout = QHBoxLayout()
        self.infoLayout.addWidget(BodyLabel("作者: "))
        self.authorEdit = LineEdit(self)
        self.authorEdit.setPlaceholderText("您的名字")
        self.infoLayout.addWidget(self.authorEdit, 1)
        
        self.infoLayout.addWidget(BodyLabel("描述: "))
        self.descEdit = LineEdit(self)
        self.descEdit.setPlaceholderText("一句话描述插件功能")
        self.infoLayout.addWidget(self.descEdit, 3)
        self.rightPanel.addLayout(self.infoLayout)

        self.blockList = BlockListWidget(self)
        self.rightPanel.addWidget(self.blockList, 1)
        
        self.rightBtnLayout = QHBoxLayout()
        self.uploadBtn = PushButton(FluentIcon.SHARE, "发布到仓库(市场)", self)
        self.uploadBtn.clicked.connect(self.upload_plugin)
        self.addCmdBtn = PushButton("添加积木(命令)", self)
        self.addCmdBtn.clicked.connect(self.add_command_block)
        
        self.savePluginBtn = PrimaryPushButton("保存插件", self)
        self.savePluginBtn.clicked.connect(self.save_plugin)
        
        self.rightBtnLayout.addWidget(self.uploadBtn)
        self.rightBtnLayout.addWidget(self.addCmdBtn)
        self.rightBtnLayout.addStretch(1)
        self.rightBtnLayout.addWidget(self.savePluginBtn)
        self.rightPanel.addLayout(self.rightBtnLayout)

        self.hBoxLayout.addLayout(self.rightPanel, 3)
        self.load_plugins()

        # 默认搜索目录为项目根
        self.search_dir = os.path.dirname(os.path.abspath(__file__))

    def choose_search_dir(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "选择要搜索的目录", self.search_dir)
        if d:
            self.search_dir = d

    def perform_search(self):
        import os
        keyword = self.searchEdit.text().strip()
        self.searchResults.clear()
        if not keyword:
            return

        # 1) 在插件配置组中搜索
        for plugin_name, pdata in self.plugins_data.items():
            # pdata 可能是 dict 或 list
            blocks = []
            if isinstance(pdata, dict):
                blocks = pdata.get('blocks', [])
            elif isinstance(pdata, list):
                blocks = pdata
            for b in blocks:
                name = b.get('name', '')
                cmd = b.get('cmd', '')
                desc = b.get('type', '')
                if keyword in name or keyword in cmd or keyword in desc:
                    item = QListWidgetItem(self.searchResults)
                    item.setText(f"插件: {plugin_name} -> {name}")
                    item.setData(Qt.UserRole, {"type": "plugin", "plugin": plugin_name, "block": name})
                    self.searchResults.addItem(item)

        # 2) 在选定目录中递归搜索文件内容（只搜索文本文件，略过大文件）
        max_file_size = 2 * 1024 * 1024
        for root, dirs, files in os.walk(self.search_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                try:
                    if os.path.getsize(fp) > max_file_size:
                        continue
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if keyword in line:
                                snippet = line.strip()
                                display = f"文件: {fp} (L{i}) -> {snippet[:200]}"
                                item = QListWidgetItem(self.searchResults)
                                item.setText(display)
                                item.setData(Qt.UserRole, {"type": "file", "path": fp, "line": i, "snippet": snippet})
                                self.searchResults.addItem(item)
                                break
                except Exception:
                    continue

    def on_search_result_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        if data.get('type') == 'plugin':
            plugin = data.get('plugin')
            # 选中并展开插件
            items = self.pluginList.findItems(plugin, Qt.MatchExactly)
            if items:
                self.pluginList.setCurrentItem(items[0])
                self.on_plugin_selected(items[0])
        elif data.get('type') == 'file':
            # 打开一个简单的查看器对话框显示匹配行
            from qfluentwidgets import InfoBar, InfoBarPosition
            snippet = data.get('snippet', '')
            path = data.get('path')
            InfoBar.success("文件匹配", f"{path}\n{snippet}", parent=self, position=InfoBarPosition.TOP)

    def load_plugins(self):
        import os, json
        if os.path.exists(self.plugins_file):
            try:
                with open(self.plugins_file, 'r', encoding='utf-8') as f:
                    self.plugins_data = json.load(f)
            except Exception:
                self.plugins_data = {}
        if not self.plugins_data:
            self.plugins_data = {
                "默认基础信息": [
                    {"name": "进程信息 (ps)", "cmd": "ps aux"},
                    {"name": "网络端口 (netstat)", "cmd": "netstat -ntlp || ss -ntlp"},
                    {"name": "当前登录用户 (w)", "cmd": "w"},
                    {"name": "系统信息 (uname)", "cmd": "uname -a"},
                    {"name": "磁盘挂载 (df)", "cmd": "df -h"}
                ],
                "面板管理端解析": [
                    {"name": "宝塔面板 (BT)", "cmd": "echo '面板入口:'; cat /www/server/panel/data/admin_path.pl 2>/dev/null; echo '\n面板端口:'; cat /www/server/panel/data/port.pl 2>/dev/null; echo '\n面板密码信息:'; cat /www/server/panel/default.pl 2>/dev/null; echo '\n\nBT命令行信息:'; sudo bt default 2>/dev/null", "type": "SSH命令"},
                    {"name": "1Panel 面板", "cmd": "sudo 1pctl user-info 2>/dev/null || echo '未找到 1Panel'", "type": "SSH命令"}
                ]
            }
            self._save_to_file()
        self.refresh_list()

    def refresh_list(self):
        self.pluginList.clear()
        for name in self.plugins_data.keys():
            self.pluginList.addItem(name)

    def _save_to_file(self):
        import json
        with open(self.plugins_file, 'w', encoding='utf-8') as f:
            json.dump(self.plugins_data, f, indent=4, ensure_ascii=False)

    def new_plugin(self):
        self.pluginList.setCurrentRow(-1)
        self.pluginNameEdit.clear()
        self.blockList.clear_blocks()
        self.add_command_block()

    def delete_plugin(self):
        item = self.pluginList.currentItem()
        if item:
            name = item.text()
            if name in self.plugins_data:
                del self.plugins_data[name]
                self._save_to_file()
                self.refresh_list()
                self.new_plugin()

    def add_command_block(self, name="", cmd=""):
        if isinstance(name, bool):
            name = ""
        if isinstance(cmd, bool):
            cmd = ""
        self.blockList.add_block(name, cmd)

    def on_plugin_selected(self, item):
        name = item.text()
        self.current_plugin = name
        self.pluginNameEdit.setText(name)
        self.blockList.clear_blocks()
        
        p_data = self.plugins_data.get(name, [])
        if isinstance(p_data, dict):
            cmds = p_data.get("blocks", [])
            self.authorEdit.setText(p_data.get("author", ""))
            self.descEdit.setText(p_data.get("description", ""))
        else:
            cmds = p_data
            self.authorEdit.setText("")
            self.descEdit.setText("")
            
        for c in cmds:
            self.blockList.add_block(c.get("name", ""), c.get("cmd", ""), c.get("type", "SSH命令"))

    def save_plugin(self):
        from PySide6.QtCore import Qt
        name = self.pluginNameEdit.text().strip()
        if not name: return
        cmds = self.blockList.get_all_blocks()
        
        # Save as dictionary
        self.plugins_data[name] = {
            "name": name,
            "author": self.authorEdit.text().strip(),
            "description": self.descEdit.text().strip(),
            "blocks": cmds
        }
        
        self._save_to_file()
        self.refresh_list()
        items = self.pluginList.findItems(name, Qt.MatchExactly)
        if items: self.pluginList.setCurrentItem(items[0])

    def upload_plugin(self):
        from qfluentwidgets import InfoBar, InfoBarPosition
        
        name = self.pluginNameEdit.text().strip()
        if not name:
            InfoBar.error("发布失败", "请先输入插件名称", parent=self, position=InfoBarPosition.TOP)
            return
            
        repo_url = "https://github.com/ljnljn2005/forensics-plugin-market.git"
        
        plugin_obj = {
            "name": name,
            "author": self.authorEdit.text().strip() or "Anonymous",
            "description": self.descEdit.text().strip() or "No description",
            "blocks": self.blockList.get_all_blocks()
        }
        
        self.log_dialog = GitLogDialog(self)
        self.log_dialog.show()
        
        self.worker = UploadWorker(repo_url, name, plugin_obj)
        self.worker.log_signal.connect(self.log_dialog.append_log)
        self.worker.finished_signal.connect(self._on_upload_finished)
        self.worker.need_token_signal.connect(self._on_upload_need_token)
        self.worker.start()

    def _on_upload_finished(self, success, reason):
        from qfluentwidgets import InfoBar, InfoBarPosition
        self.log_dialog.upload_finished()
        if success:
            if reason == "no_change":
                InfoBar.success("发布完成", "插件数据未发生更改，无需重新推送。", parent=self, position=InfoBarPosition.TOP)
            else:
                InfoBar.success("发布成功", "插件已成功推送！", parent=self, position=InfoBarPosition.TOP)
        else:
            InfoBar.error("发布失败", reason, parent=self, position=InfoBarPosition.TOP)

    def _on_upload_need_token(self):
        from qfluentwidgets import InfoBar, InfoBarPosition
        from PySide6.QtWidgets import QDialog
        dlg = GitHubLoginDialog(self)
        if dlg.exec() == QDialog.Accepted:
            token = dlg.get_token()
            if token:
                name = self.worker.name
                plugin_obj = self.worker.plugin_obj
                repo_url = self.worker.repo_url
                self.log_dialog.append_log("\n>> 重新尝试使用 Token 推送...")
                self.worker = UploadWorker(repo_url, name, plugin_obj, token=token)
                self.worker.log_signal.connect(self.log_dialog.append_log)
                self.worker.finished_signal.connect(self._on_upload_finished)
                self.worker.need_token_signal.connect(self._on_upload_need_token)
                self.worker.start()
            else:
                self.log_dialog.append_log("用户取消了 Token 输入，推送中止。")
                self.log_dialog.upload_finished()
        else:
            self.log_dialog.append_log("由于未授权，推送中止。")
            self.log_dialog.upload_finished()

class GitHubLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub 授权")
        self.setFixedWidth(400)
        from qfluentwidgets import LineEdit, PrimaryPushButton, BodyLabel
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.addWidget(BodyLabel("当前 Git 未配置或未授权，未能直接 Push。\n请输入 GitHub 个人访问令牌 (PAT) 用于发布上传。\n您可以前往 GitHub Developer Settings 生成 token。", self))
        self.tokenEdit = LineEdit(self)
        self.tokenEdit.setPlaceholderText("ghp_xxxxxxxxx...")
        layout.addWidget(self.tokenEdit)
        self.btn = PrimaryPushButton("确定", self)
        self.btn.clicked.connect(self.accept)
        layout.addWidget(self.btn)
        
    def get_token(self):
        return self.tokenEdit.text().strip()

class MarketCardWidget(QWidget):
    def __init__(self, plugin_data, parent=None):
        super().__init__(parent)
        from qfluentwidgets import SubtitleLabel, CaptionLabel, BodyLabel, PrimaryPushButton
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
        self.plugin_data = plugin_data
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        infoLayout = QVBoxLayout()
        self.nameLabel = SubtitleLabel(plugin_data.get("name", "未命名插件"), self)
        self.authorLabel = CaptionLabel(f"作者: {plugin_data.get('author', '佚名')}", self)
        self.descLabel = BodyLabel(plugin_data.get("description", "暂无描述"), self)
        self.descLabel.setWordWrap(True)
        
        infoLayout.addWidget(self.nameLabel)
        infoLayout.addWidget(self.authorLabel)
        infoLayout.addWidget(self.descLabel)
        
        layout.addLayout(infoLayout, 1)
        
        from qfluentwidgets import PrimaryPushButton
        self.downloadBtn = PrimaryPushButton(FluentIcon.DOWNLOAD, "下载安装", self)
        layout.addWidget(self.downloadBtn)

class PluginMarketInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('pluginMarketInterface')
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)
        
        # Header
        from qfluentwidgets import LargeTitleLabel
        self.titleLabel = LargeTitleLabel("插件市场", self)
        self.vBoxLayout.addWidget(self.titleLabel)
        
        # Config & Search
        self.headerLayout = QHBoxLayout()
        from qfluentwidgets import LineEdit, SearchLineEdit, PushButton, InfoBar, InfoBarPosition
        self.repoEdit = LineEdit(self)
        self.repoEdit.setText("https://api.github.com/repos/ljnljn2005/forensics-plugin-market/contents/")
        self.repoEdit.setPlaceholderText("市场数据所在的远程 URL (如 GitHub API 或本地目录)")
        
        self.searchEdit = SearchLineEdit(self)
        self.searchEdit.setPlaceholderText("搜索插件...")
        
        self.refreshBtn = PushButton(FluentIcon.SYNC, "拉取列表", self)
        
        self.headerLayout.addWidget(self.repoEdit, 2)
        self.headerLayout.addWidget(self.searchEdit, 1)
        self.headerLayout.addWidget(self.refreshBtn)
        self.vBoxLayout.addLayout(self.headerLayout)
        
        # List
        from qfluentwidgets import ListWidget
        self.marketList = ListWidget(self)
        self.vBoxLayout.addWidget(self.marketList, 1)
        
        self.refreshBtn.clicked.connect(self.fetch_market)
        self.searchEdit.textChanged.connect(self.filter_list)
        self.market_data = []

    def fetch_market(self):
        url = self.repoEdit.text().strip()
        if not url: return
        import urllib.request, json, os
        from qfluentwidgets import InfoBar, InfoBarPosition
        
        # Setup Proxy if configured
        proxy_str = get_app_proxy()
        if proxy_str:
            proxy_handler = urllib.request.ProxyHandler({'http': proxy_str, 'https': proxy_str})
            opener = urllib.request.build_opener(proxy_handler)
            urllib.request.install_opener(opener)
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            urllib.request.install_opener(opener)
            
        try:
            self.market_data = []
            if url.startswith('http'):
                # Fetch contents from GitHub API
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ForensicTool'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    files = json.loads(response.read().decode('utf-8'))
                    
                # Iterate each file and fetch if it's a json
                for file_info in files:
                    if isinstance(file_info, dict) and file_info.get("name", "").endswith(".json") and file_info.get("name") != "market.json":
                        download_url = file_info.get("download_url")
                        if download_url:
                            try:
                                # Ensure non-ASCII URL characters (mostly Chinese names) are properly encoded for urllib
                                # Usually download_url from Github API is already somehow encoded, but Python might choke
                                # Safest to parse and unquote/quote it properly if it fails
                                import urllib.parse
                                parsed = urllib.parse.urlsplit(download_url)
                                encoded_path = urllib.parse.quote(urllib.parse.unquote(parsed.path))
                                safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment))
                                
                                child_req = urllib.request.Request(safe_url, headers={'User-Agent': 'Mozilla/5.0 ForensicTool'})
                                with urllib.request.urlopen(child_req, timeout=10) as child_res:
                                    plugin_content = json.loads(child_res.read().decode('utf-8'))
                                    self.market_data.append(plugin_content)
                            except Exception as ex:
                                print(f"Error loading {file_info.get('name')} from {download_url}: {ex}")
            else:
                local_path = url
                if url.startswith('file:///'):
                    local_path = url[8:]
                elif url.startswith('file://'):
                    local_path = url[7:]
                
                if os.path.isdir(local_path):
                    for fname in os.listdir(local_path):
                        if fname.endswith(".json") and fname != "market.json":
                            with open(os.path.join(local_path, fname), 'r', encoding='utf-8') as f:
                                try:
                                    self.market_data.append(json.load(f))
                                except: pass
                else:
                    # In case they point to a specific json file for some reason
                    with open(local_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self.market_data = data
                        else:
                            self.market_data.append(data)
                            
            self.populate_list(self.market_data)
            InfoBar.success("刷新成功", f"拉取到 {len(self.market_data)} 个插件", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("获取失败", f"无法拉取市场数据: {e}", parent=self, position=InfoBarPosition.TOP)

    def populate_list(self, data):
        from PySide6.QtCore import Qt, QSize
        self.marketList.clear()
        for idx, p in enumerate(data):
            item = QListWidgetItem(self.marketList)
            item.setSizeHint(QSize(0, 100))
            item.setData(Qt.UserRole, p)
            self.marketList.addItem(item)
            
            w = MarketCardWidget(p, self.marketList)
            w.downloadBtn.clicked.connect(lambda _, p_data=p: self.install_plugin(p_data))
            self.marketList.setItemWidget(item, w)

    def filter_list(self, text):
        from PySide6.QtCore import Qt
        for i in range(self.marketList.count()):
            item = self.marketList.item(i)
            p = item.data(Qt.UserRole)
            match = text.lower() in p.get("name", "").lower() or text.lower() in p.get("description", "").lower()
            item.setHidden(not match)

    def install_plugin(self, plugin_data):
        import os, json
        from qfluentwidgets import InfoBar, InfoBarPosition
        plugins_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssh_plugins.json')
        local_data = {}
        if os.path.exists(plugins_file):
            try:
                with open(plugins_file, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
            except:
                pass
        
        name = plugin_data.get("name", "未命名插件")
        blocks = plugin_data.get("blocks", [])
        local_data[name] = blocks
        
        try:
            with open(plugins_file, 'w', encoding='utf-8') as f:
                json.dump(local_data, f, indent=4, ensure_ascii=False)
            InfoBar.success("安装成功", f"插件 [{name}] 已安装到本地！可以在 左侧面板 刷新查看到它。", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("安装失败", f"无法保存本地配置: {e}", parent=self, position=InfoBarPosition.TOP)

class HomeWidget(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel("欢迎使用综合取证分析工具", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)



def get_app_proxy():
    import os, json
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_settings.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('proxy', '')
        except:
            pass
    return ''

def save_app_proxy(proxy_str):
    import os, json
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_settings.json')
    config = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            pass
    config['proxy'] = proxy_str
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        
        # Ensure theme auto-switches based on OS dark/light mode
        setTheme(Theme.AUTO)

        self.homeInterface = HomeWidget('主页', self)
        self.homeInterface.setObjectName('homeInterface')
        
        self.extractorInterface = ExtractorInterface(self)
        self.liveSshInterface = LiveSshInterface(self)
        self.pluginEditorInterface = PluginEditorInterface(self)
        self.pluginMarketInterface = PluginMarketInterface(self)
        self.settingInterface = SettingInterface(self)

        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FluentIcon.HOME, '主页')
        self.addSubInterface(self.extractorInterface, FluentIcon.DOCUMENT, '离线取证 (提取盘)')
        self.addSubInterface(self.liveSshInterface, FluentIcon.GLOBE, '动态取证 (SSH)')
        self.addSubInterface(self.pluginEditorInterface, FluentIcon.CALENDAR, '提取插件编辑')
        self.addSubInterface(self.pluginMarketInterface, FluentIcon.MARKET, '插件市场')
        self.addSubInterface(self.settingInterface, FluentIcon.SETTING, '设置', NavigationItemPosition.BOTTOM)

    def initWindow(self):
        self.resize(900, 700)
        self.setWindowTitle('综合取证分析工具')
        
        # Move window to center
        desktop = QApplication.primaryScreen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)


if __name__ == '__main__':
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
