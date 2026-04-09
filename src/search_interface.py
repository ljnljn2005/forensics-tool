import os
import json
import re
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem, QDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from .widgets import SearchableTextEdit, CommandRunnerDialog
from .extractor import execute_command_for_ai
from qfluentwidgets import SubtitleLabel, LineEdit, PushButton, ListWidget, BodyLabel, TextEdit, InfoBar, InfoBarPosition
from qfluentwidgets import FluentIcon
from .constants import SETTINGS_DIR, PLUGINS_DIR


class SearchInterface(QWidget):
    """全局搜索配置/插件并提供 AI 分析入口（可替换成大模型回调）。"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('searchInterface')

        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(24, 24, 24, 24)
        self.vbox.setSpacing(12)

        self.title = SubtitleLabel("全局配置搜索", self)
        self.vbox.addWidget(self.title)

        header = QHBoxLayout()
        self.searchEdit = LineEdit(self)
        self.searchEdit.setPlaceholderText("输入要搜索的关键字或粘贴题目描述...")
        self.searchBtn = PushButton(FluentIcon.SEARCH, "搜索", self)
        header.addWidget(self.searchEdit, 2)
        header.addWidget(self.searchBtn)
        self.vbox.addLayout(header)

        self.resultsList = ListWidget(self)
        self.vbox.addWidget(self.resultsList, 2)

        self.searchBtn.clicked.connect(self.perform_search)
        # 按 Enter 触发搜索
        try:
            self.searchEdit.returnPressed.connect(self.perform_search)
        except Exception:
            pass
        self.resultsList.itemDoubleClicked.connect(self.on_result_activated)

    def on_result_activated(self, item):
        data = item.data(Qt.UserRole) if item else None
        if not data:
            return
        cmd = data.get('cmd', '')
        if not cmd:
            InfoBar.info('执行提示', '该功能没有关联命令。', parent=self)
            return

        dtype = data.get('type', '')
        # 本地文件提取型：直接读取映射盘/本地文件并展示
        if '文件' in (dtype or '') or '提取' in (dtype or ''):
            try:
                main_win = self.window()
                base = None
                if hasattr(main_win, 'extractorInterface'):
                    try:
                        base = getattr(main_win, 'extractorInterface').pathLineEdit.text().strip()
                    except Exception:
                        base = None
                out = execute_command_for_ai(cmd, base_path=base, btype=dtype)
            except Exception as e:
                out = f"本地读取失败: {e}"

            # show local read results in a modal dialog
            dlg = CommandRunnerDialog(self, title=f"{data.get('plugin','')} - {data.get('block_name','')}")
            for line in (out or '').splitlines():
                dlg.append_line(line)
            dlg.closeBtn.setEnabled(True)
            dlg.exec()
            return

        # 远程执行（SSH 命令）：在后台通过 ssh_client.exec_command 获取输出并在 LiveSshInterface 中新 tab 显示（不打开交互终端）
        try:
            main_win = self.window()
            if hasattr(main_win, 'liveSshInterface'):
                ls = getattr(main_win, 'liveSshInterface')
                ssh_client = getattr(ls, 'ssh_client', None)
                if ssh_client and ssh_client.get_transport() and ssh_client.get_transport().is_active():
                    try:
                        stdin, stdout, stderr = ssh_client.exec_command(cmd)
                        out = stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')
                    except Exception as e:
                        out = f"远程执行失败: {e}"
                    # show output in a modal dialog
                    dlg = CommandRunnerDialog(self, title=f"{data.get('plugin','')} - {data.get('block_name','')}")
                    for line in (out or '').splitlines():
                        dlg.append_line(line)
                    dlg.closeBtn.setEnabled(True)
                    dlg.exec()
                    InfoBar.success('已执行', '远程命令已执行并在弹窗中显示结果。', parent=self)
                    return
                else:
                    InfoBar.info('未连接', '远程 SSH 未连接。请先在动态取证页面连接主机，或复制命令手动执行。', parent=self)
        except Exception:
            pass

        # 回退：复制到剪贴板并提示
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(cmd)
            InfoBar.info('已复制', '命令已复制到剪贴板，请在目标主机/终端粘贴执行。', parent=self)
        except Exception:
            InfoBar.info('无法执行', '既无法远程执行，也无法复制到剪贴板。', parent=self)

    def perform_search(self):
        keyword = self.searchEdit.text().strip()
        self.resultsList.clear()
        if not keyword:
            InfoBar.info("搜索提示", "请输入关键字后再搜索。", parent=self)
            return

        # 搜索插件功能：从 plugins 目录和 ssh_plugins.json 中读取所有插件与积木
        matches = []
        # load central ssh_plugins.json if exists
        central_file = os.path.join(PLUGINS_DIR, 'ssh_plugins.json')
        central = {}
        if os.path.exists(central_file):
            try:
                with open(central_file, 'r', encoding='utf-8') as f:
                    central = json.load(f)
            except Exception:
                central = {}

        # normalize central into plugin objects
        for pname, pdata in central.items():
            if isinstance(pdata, dict):
                pblocks = pdata.get('blocks', [])
                pauthor = pdata.get('author', '')
                pdesc = pdata.get('description', '')
            else:
                pblocks = pdata
                pauthor = ''
                pdesc = ''
            for b in (pblocks or []):
                if not isinstance(b, dict):
                    continue
                hay = ' '.join([pname, pauthor, pdesc, b.get('name', ''), b.get('cmd', ''), b.get('type', ''), b.get('module', '')])
                if keyword.lower() in hay.lower():
                    matches.append({
                        'plugin': pname,
                        'author': pauthor,
                        'description': pdesc,
                        'block_name': b.get('name', ''),
                        'cmd': b.get('cmd', ''),
                        'type': b.get('type', ''),
                        'module': b.get('module', '')
                    })

        # also scan individual plugin files under PLUGINS_DIR
        try:
            for fn in os.listdir(PLUGINS_DIR):
                if not fn.endswith('.json'):
                    continue
                fp = os.path.join(PLUGINS_DIR, fn)
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        pj = json.load(f)
                        pname = pj.get('name', os.path.splitext(fn)[0]) if isinstance(pj, dict) else os.path.splitext(fn)[0]
                        pauthor = pj.get('author', '') if isinstance(pj, dict) else ''
                        pdesc = pj.get('description', '') if isinstance(pj, dict) else ''
                        blocks = pj.get('blocks', []) if isinstance(pj, dict) else pj
                        for b in (blocks or []):
                            if not isinstance(b, dict):
                                continue
                            hay = ' '.join([pname, pauthor, pdesc, b.get('name', ''), b.get('cmd', ''), b.get('type', ''), b.get('module', '')])
                            if keyword.lower() in hay.lower():
                                matches.append({
                                    'plugin': pname,
                                    'author': pauthor,
                                    'description': pdesc,
                                    'block_name': b.get('name', ''),
                                    'cmd': b.get('cmd', ''),
                                    'type': b.get('type', ''),
                                    'module': b.get('module', '')
                                })
                except Exception:
                    continue
        except Exception:
            pass

        # populate results list
        for m in matches:
            item = QListWidgetItem(self.resultsList)
            item.setText(f"{m['plugin']} -> {m['block_name']} [{m['module']}] : {m['cmd']}")
            item.setData(Qt.UserRole, m)
            self.resultsList.addItem(item)

        if not matches:
            InfoBar.info("未找到功能匹配", f"未找到与 '{keyword}' 匹配的插件功能。", parent=self)

    
