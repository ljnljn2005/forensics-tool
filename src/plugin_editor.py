import os
import json
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDialog
from PySide6.QtCore import Qt
from qfluentwidgets import SubtitleLabel, LineEdit, PushButton, SegmentedWidget, ListWidget, BodyLabel, PrimaryPushButton, ComboBox
from .constants import PLUGINS_DIR, get_app_settings
from .widgets import BlockListWidget, GitLogDialog, UploadWorker


class GitHubLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub 授权")
        self.setFixedWidth(400)
        from qfluentwidgets import LineEdit, PrimaryPushButton, BodyLabel
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.addWidget(BodyLabel("请输入 GitHub 个人访问令牌 (PAT)", self))
        self.tokenEdit = LineEdit(self)
        self.tokenEdit.setPlaceholderText("ghp_xxxxxxxxx...")
        layout.addWidget(self.tokenEdit)
        self.btn = PrimaryPushButton("确定", self)
        self.btn.clicked.connect(self.accept)
        layout.addWidget(self.btn)

    def get_token(self):
        return self.tokenEdit.text().strip()


class PluginEditorInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('pluginEditorInterface')
        self.plugins_file = os.path.join(PLUGINS_DIR, 'ssh_plugins.json')
        self.plugins_data = {}
        self.current_plugin = None

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.hBoxLayout.setSpacing(16)

        self.leftPanel = QVBoxLayout()
        self.leftPanel.addWidget(SubtitleLabel("保存的插件", self))
        self.editorTypeSelector = SegmentedWidget(self)
        self.editorTypeSelector.addItem('ssh', 'SSH 插件')
        self.editorTypeSelector.addItem('file', '文件提取插件')
        self.editorTypeSelector.currentItemChanged.connect(self.on_editor_type_changed)
        self.leftPanel.addWidget(self.editorTypeSelector)

        self.searchLayout = QHBoxLayout()
        self.searchEdit = LineEdit(self)
        self.searchEdit.setPlaceholderText("搜索插件或目录内容...")
        self.searchBtn = PushButton("搜索", self)
        self.chooseDirBtn = PushButton("选择目录", self)
        self.searchBtn.clicked.connect(self.perform_search)
        self.chooseDirBtn.clicked.connect(self.choose_search_dir)
        self.searchLayout.addWidget(self.searchEdit, 1)
        self.searchLayout.addWidget(self.searchBtn)
        self.searchLayout.addWidget(self.chooseDirBtn)
        self.leftPanel.addLayout(self.searchLayout)

        self.pluginList = ListWidget(self)
        self.pluginList.itemClicked.connect(self.on_plugin_selected)
        self.leftPanel.addWidget(self.pluginList)

        # new / delete plugin buttons
        self.pluginBtnLayout = QHBoxLayout()
        self.newPluginBtn = PushButton("新建插件", self)
        self.newPluginBtn.clicked.connect(self.new_plugin)
        self.deletePluginBtn = PushButton("删除插件", self)
        self.deletePluginBtn.clicked.connect(self.delete_plugin)
        self.pluginBtnLayout.addWidget(self.newPluginBtn)
        self.pluginBtnLayout.addWidget(self.deletePluginBtn)
        self.leftPanel.addLayout(self.pluginBtnLayout)

        # search results panel removed; search will highlight matching plugins

        self.hBoxLayout.addLayout(self.leftPanel, 1)

        self.rightPanel = QVBoxLayout()
        self.rightPanel.addWidget(SubtitleLabel("编辑插件区域", self))

        self.nameLayout = QHBoxLayout()
        self.nameLayout.addWidget(BodyLabel("插件名称: "))
        self.pluginNameEdit = LineEdit(self)
        self.nameLayout.addWidget(self.pluginNameEdit, 1)
        self.rightPanel.addLayout(self.nameLayout)

        # author and description
        self.metaLayout = QHBoxLayout()
        self.metaLayout.addWidget(BodyLabel("作者: "))
        self.authorEdit = LineEdit(self)
        self.authorEdit.setPlaceholderText("作者姓名或组织")
        self.metaLayout.addWidget(self.authorEdit, 1)
        self.rightPanel.addLayout(self.metaLayout)

        self.descLayout = QVBoxLayout()
        self.descLayout.addWidget(BodyLabel("描述: "))
        self.descEdit = LineEdit(self)
        self.descEdit.setPlaceholderText("插件简要描述")
        self.descLayout.addWidget(self.descEdit)
        self.rightPanel.addLayout(self.descLayout)

        # module / platform selector for the plugin (linux, android, ...)
        self.moduleLayout = QHBoxLayout()
        self.moduleLayout.addWidget(BodyLabel("目标平台: "))
        self.moduleSelector = ComboBox(self)
        # common platforms
        for m in ("linux", "android", "windows", "macos", "all"):
            self.moduleSelector.addItem(m)
        self.moduleSelector.setFixedWidth(160)
        self.moduleSelector.currentTextChanged.connect(lambda t: setattr(self, 'current_module', t))
        self.moduleLayout.addWidget(self.moduleSelector)
        self.moduleLayout.addStretch(1)
        self.rightPanel.addLayout(self.moduleLayout)

        self.sshBlockList = BlockListWidget(self)
        self.fileBlockList = BlockListWidget(self)
        self.fileBlockList.hide()
        self.rightPanel.addWidget(self.sshBlockList, 1)
        self.rightPanel.addWidget(self.fileBlockList, 1)

        self.rightBtnLayout = QHBoxLayout()
        self.uploadBtn = PushButton("发布到仓库(市场)", self)
        self.uploadBtn.clicked.connect(self.upload_plugin)
        self.addCmdBtn = PushButton("添加积木(命令)", self)
        self.addCmdBtn.clicked.connect(self.add_command_block)
        self.addFileBtn = PushButton("添加积木(文件提取)", self)
        self.addFileBtn.clicked.connect(self.add_file_block)
        self.savePluginBtn = PrimaryPushButton("保存插件", self)
        self.savePluginBtn.clicked.connect(self.save_plugin)
        self.rightBtnLayout.addWidget(self.uploadBtn)
        self.rightBtnLayout.addWidget(self.addCmdBtn)
        self.rightBtnLayout.addWidget(self.addFileBtn)
        self.rightBtnLayout.addStretch(1)
        self.rightBtnLayout.addWidget(self.savePluginBtn)
        self.rightPanel.addLayout(self.rightBtnLayout)

        self.hBoxLayout.addLayout(self.rightPanel, 3)
        # Ensure default editor type after widgets exist
        self.editorTypeSelector.setCurrentItem('ssh')
        self.load_plugins()
        # Default search directory
        self.search_dir = os.path.dirname(os.path.abspath(__file__))

    def choose_search_dir(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "选择要搜索的目录", self.search_dir)
        if d:
            self.search_dir = d

    def perform_search(self):
        keyword = self.searchEdit.text().strip()
        if not keyword:
            return
        # search in plugins and highlight matching plugin in the list
        matched_plugins = []
        for plugin_name, pdata in self.plugins_data.items():
            blocks = pdata.get('blocks', []) if isinstance(pdata, dict) else pdata
            for b in blocks:
                name = b.get('name', '')
                cmd = b.get('cmd', '')
                desc = b.get('type', '')
                if keyword in name or keyword in cmd or keyword in desc or keyword in plugin_name:
                    matched_plugins.append(plugin_name)
                    break

        from qfluentwidgets import InfoBar, InfoBarPosition
        if matched_plugins:
            self.refresh_list()
            first = matched_plugins[0]
            items = self.pluginList.findItems(first, Qt.MatchExactly)
            if items:
                self.pluginList.setCurrentItem(items[0])
                self.on_plugin_selected(items[0])
            InfoBar.success("搜索完成", f"匹配到 {len(matched_plugins)} 个插件。", parent=self, position=InfoBarPosition.TOP)
            return

        # search in files under search_dir (text files only)
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
                                InfoBar.success("文件匹配", f"{fp}\n{snippet}", parent=self, position=InfoBarPosition.TOP)
                                return
                except Exception:
                    continue

        InfoBar.info("未找到匹配项", f"在插件和文件中未找到包含 '{keyword}' 的项。", parent=self)

    

    def load_plugins(self):
        if os.path.exists(self.plugins_file):
            try:
                with open(self.plugins_file, 'r', encoding='utf-8') as f:
                    self.plugins_data = json.load(f)
            except Exception:
                self.plugins_data = {}
        if not self.plugins_data:
            self.plugins_data = {}
            self._save_to_file()
        self.refresh_list()

    def refresh_list(self):
        cur_type = getattr(self, 'current_editor_type', 'ssh')
        self.pluginList.clear()
        for name, pdata in self.plugins_data.items():
            blocks = pdata.get('blocks', []) if isinstance(pdata, dict) else pdata
            has_ssh = any(isinstance(b, dict) and ("SSH" in (b.get('type') or '') or "命令" in (b.get('type') or '')) for b in blocks)
            has_file = any(isinstance(b, dict) and ("文件" in (b.get('type') or '') or "提取" in (b.get('type') or '')) for b in blocks)
            if cur_type == 'ssh' and has_ssh:
                self.pluginList.addItem(name)
            elif cur_type == 'file' and has_file:
                self.pluginList.addItem(name)

    def _save_to_file(self):
        with open(self.plugins_file, 'w', encoding='utf-8') as f:
            json.dump(self.plugins_data, f, indent=4, ensure_ascii=False)

    def new_plugin(self):
        self.pluginList.setCurrentRow(-1)
        self.pluginNameEdit.clear()
        self.sshBlockList.clear_blocks()
        self.fileBlockList.clear_blocks()
        self.add_command_block()
        # reset module selector to default
        if hasattr(self, 'moduleSelector'):
            try:
                self.moduleSelector.setCurrentText('linux')
            except Exception:
                pass
        self.current_module = 'linux'

    def on_editor_type_changed(self, key):
        self.current_editor_type = key
        # ensure block lists exist (may be called early)
        if not hasattr(self, 'sshBlockList') or not hasattr(self, 'fileBlockList'):
            return
        if key == 'ssh':
            self.sshBlockList.show()
            self.fileBlockList.hide()
        else:
            self.sshBlockList.hide()
            self.fileBlockList.show()
        self.refresh_list()

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
        # QPushButton.clicked may pass a boolean checked arg; normalize inputs
        if isinstance(name, bool):
            name = ""
        if isinstance(cmd, bool):
            cmd = ""
        module = getattr(self, 'current_module', self.moduleSelector.currentText() if hasattr(self, 'moduleSelector') else 'linux')
        self.sshBlockList.add_block(name, cmd, "SSH命令", module, "")

    def add_file_block(self, name="", cmd=""):
        if isinstance(name, bool):
            name = ""
        if isinstance(cmd, bool):
            cmd = ""
        module = getattr(self, 'current_module', self.moduleSelector.currentText() if hasattr(self, 'moduleSelector') else 'linux')
        self.fileBlockList.add_block(name, cmd, "文件提取", module, "")

    def on_plugin_selected(self, item):
        name = item.text()
        self.current_plugin = name
        self.pluginNameEdit.setText(name)
        # populate metadata if present
        pdata = self.plugins_data.get(name, {})
        if isinstance(pdata, dict):
            self.authorEdit.setText(pdata.get('author', ''))
            self.descEdit.setText(pdata.get('description', ''))
            mod = pdata.get('module', None)
            if mod and hasattr(self, 'moduleSelector'):
                try:
                    self.moduleSelector.setCurrentText(mod)
                except Exception:
                    pass
        self.sshBlockList.clear_blocks()
        self.fileBlockList.clear_blocks()
        p_data = self.plugins_data.get(name, [])
        if isinstance(p_data, dict):
            cmds = p_data.get("blocks", [])
        else:
            cmds = p_data
        for c in cmds:
            ctype = c.get("type", "")
            if isinstance(ctype, str) and ("SSH" in ctype or "命令" in ctype):
                self.sshBlockList.add_block(c.get("name", ""), c.get("cmd", ""), c.get("type", "SSH命令"), c.get("module", getattr(self, 'current_module', 'linux')), c.get("category", ""))
            else:
                self.fileBlockList.add_block(c.get("name", ""), c.get("cmd", ""), c.get("type", "文件提取"), c.get("module", getattr(self, 'current_module', 'linux')), c.get("category", ""))

    def save_plugin(self):
        name = self.pluginNameEdit.text().strip()
        if not name: return
        ssh_cmds = self.sshBlockList.get_all_blocks()
        file_cmds = self.fileBlockList.get_all_blocks()
        # include chosen module as plugin-level metadata
        plugin_module = getattr(self, 'current_module', self.moduleSelector.currentText() if hasattr(self, 'moduleSelector') else 'linux')
        self.plugins_data[name] = {
            "name": name,
            "author": self.authorEdit.text().strip(),
            "description": self.descEdit.text().strip(),
            "module": plugin_module,
            "blocks": ssh_cmds + file_cmds
        }
        self._save_to_file()
        self.refresh_list()
        items = self.pluginList.findItems(name, Qt.MatchExactly)
        if items: self.pluginList.setCurrentItem(items[0])
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.success("保存成功", f"插件 [{name}] 已保存。", parent=self, position=InfoBarPosition.TOP)

    def upload_plugin(self):
        name = self.pluginNameEdit.text().strip()
        if not name:
            return
        ssh_cmds = self.sshBlockList.get_all_blocks()
        file_cmds = self.fileBlockList.get_all_blocks()
        plugin_obj = {
            "name": name,
            "author": self.authorEdit.text().strip(),
            "description": self.descEdit.text().strip(),
            "blocks": ssh_cmds + file_cmds
        }
        self.log_dialog = GitLogDialog(self)
        self.log_dialog.show()
        # allow overriding repo URL from global settings
        try:
            cfg = get_app_settings()
            repo_url = cfg.get('market_repo') or "https://github.com/ljnljn2005/forensics-plugin-market.git"
        except Exception:
            repo_url = "https://github.com/ljnljn2005/forensics-plugin-market.git"

        # If user supplied a GitHub API contents URL, convert to git clone URL
        try:
            import re
            m = re.search(r'https?://api\.github\.com/repos/([^/]+)/([^/]+)/contents/?', repo_url)
            if m:
                owner, repo = m.group(1), m.group(2)
                repo_url = f'https://github.com/{owner}/{repo}.git'
        except Exception:
            pass

        self.worker = UploadWorker(repo_url, name, plugin_obj)
        self.worker.log_signal.connect(self.log_dialog.append_log)
        self.worker.finished_signal.connect(self._on_upload_finished)
        self.worker.need_token_signal.connect(self._on_upload_need_token)
        self.worker.start()

    def _on_upload_finished(self, success, reason):
        self.log_dialog.upload_finished()

    def _on_upload_need_token(self):
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
