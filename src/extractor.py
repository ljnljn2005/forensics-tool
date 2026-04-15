import os
import json
import glob
import re
import subprocess
import tarfile
import zipfile
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QWidget, QListWidgetItem, QStackedWidget, QDialog
from PySide6.QtCore import Qt
from qfluentwidgets import SubtitleLabel, LineEdit, PushButton, SegmentedWidget, ListWidget
from .constants import PLUGINS_DIR
from .widgets import SearchableTextEdit

# last tried paths (for UI/terminal reporting)
_LAST_TRIED_PATHS: list | None = None


class ExtractorInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('extractorInterface')

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)

        self.moduleBar = SegmentedWidget(self)
        self.moduleBar.addItem('windows', 'Windows分析')
        self.moduleBar.addItem('linux', 'Linux分析')
        self.moduleBar.addItem('android', 'Android分析')
        self.moduleBar.addItem('ios', 'iOS分析')
        self.moduleBar.currentItemChanged.connect(self.on_module_changed)
        self.vBoxLayout.addWidget(self.moduleBar)

        self.current_module = 'linux'
        self.titleLabel = SubtitleLabel("Linux 映射盘信息提取", self)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.moduleBar.setCurrentItem('linux')

        self.pathLayout = QHBoxLayout()
        # input moved to HomeWidget; keep hidden field for backward compatibility
        self.pathLabel = SubtitleLabel('映射路径', self)
        self.pathLineEdit = LineEdit(self)
        self.pathLineEdit.setVisible(False)
        self.browseButton = PushButton("浏览...", self)
        self.browseButton.setVisible(False)
        self.browseButton.clicked.connect(self.browse_folder)
        self.pathLayout.addWidget(self.pathLabel)
        self.pathLayout.addWidget(self.pathLineEdit)
        self.pathLayout.addWidget(self.browseButton)
        self.scanButton = PushButton("扫描并加载", self)
        self.scanButton.clicked.connect(self.extract_all)
        self.pathLayout.addWidget(self.scanButton)
        self.vBoxLayout.addLayout(self.pathLayout)

        self.contentLayout = QHBoxLayout()
        self.leftPanel = QVBoxLayout()
        self.leftPanel.addWidget(SubtitleLabel("插件（当前模块）", self))
        self.pluginSearch = LineEdit(self)
        self.pluginSearch.setPlaceholderText("搜索插件...")
        self.pluginSearch.textChanged.connect(self.filter_extractor_plugin_list)
        self.leftPanel.addWidget(self.pluginSearch)

        self.extractorPluginList = ListWidget(self)
        self.extractorPluginList.itemClicked.connect(self.on_extractor_plugin_clicked)
        self.leftPanel.addWidget(self.extractorPluginList, 1)

        leftWidget = QWidget(self)
        leftWidget.setLayout(self.leftPanel)

        self.rightPanel = QVBoxLayout()
        self.rightPanel.addWidget(SubtitleLabel("提取结果", self))
        self.extractViewer = self._create_text_edit()
        self.rightPanel.addWidget(self.extractViewer, 1)

        rightWidget = QWidget(self)
        rightWidget.setLayout(self.rightPanel)

        self.contentLayout.addWidget(leftWidget, 1)
        self.contentLayout.addWidget(rightWidget, 3)
        self.vBoxLayout.addLayout(self.contentLayout)

        self.plugins_file = os.path.join(PLUGINS_DIR, 'ssh_plugins.json')

    def browse_folder(self):
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, '选择目录')
        if folder:
            self.pathLineEdit.setText(folder)

    def on_module_changed(self, module_key):
        self.current_module = module_key
        # simplified: just refresh
        try:
            self.populate_extractor_plugins()
        except Exception:
            pass

    def load_plugins_for_module(self):
        try:
            with open(self.plugins_file, 'r', encoding='utf-8') as f:
                pdata = json.load(f)
        except Exception:
            pdata = {}
        # noop

    def populate_extractor_plugins(self):
        self.extractorPluginList.clear()
        try:
            with open(self.plugins_file, 'r', encoding='utf-8') as f:
                pdata = json.load(f)
        except Exception:
            pdata = {}
        cur_mod = getattr(self, 'current_module', 'linux')
        count = 0
        for group_name, group_data in pdata.items():
            blocks = group_data.get('blocks', []) if isinstance(group_data, dict) else group_data
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                b_mod = b.get('module')
                btype = b.get('type', '')
                if b_mod and b_mod != cur_mod:
                    continue
                if '文件' not in btype and '提取' not in btype:
                    continue
                name = b.get('name', '')
                cmd = b.get('cmd', '')
                it = QListWidgetItem(self.extractorPluginList)
                it.setText(f"{group_name} - {name}")
                it.setData(Qt.UserRole, {"group": group_name, "name": name, "cmd": cmd, "type": btype})
                self.extractorPluginList.addItem(it)
                count += 1
        self.extractViewer.setText(f"已加载 {count} 个插件。选择左侧插件以运行提取并在此查看结果。")

    def filter_extractor_plugin_list(self, text):
        kw = text.strip().lower()
        for i in range(self.extractorPluginList.count()):
            it = self.extractorPluginList.item(i)
            txt = it.text()
            it.setHidden(bool(kw) and kw not in txt.lower())

    def on_extractor_plugin_clicked(self, item):
        if not item:
            return
        self.run_block_item(item)

    def select_and_run_plugin(self, group: str, name: str, base_path: str | None = None):
        """Set mapping path (if provided), refresh plugin list for current module, select the plugin by group/name and run its block.
        This is used by LiveSshInterface to jump and auto-run file-extraction blocks."""
        try:
            if base_path and isinstance(base_path, str):
                self.pathLineEdit.setText(base_path)
            # refresh list
            self.populate_extractor_plugins()
            # find matching item
            target_text = f"{group} - {name}"
            found = None
            for i in range(self.extractorPluginList.count()):
                it = self.extractorPluginList.item(i)
                if it.text() == target_text:
                    found = it
                    break
            if not found:
                # try fuzzy match
                for i in range(self.extractorPluginList.count()):
                    it = self.extractorPluginList.item(i)
                    if group in it.text() and name in it.text():
                        found = it
                        break
            if found:
                self.extractorPluginList.setCurrentItem(found)
                self.run_block_item(found)
            else:
                if hasattr(self, 'extractViewer') and self.extractViewer:
                    self.extractViewer.setText(f"未在当前模块找到插件: {group} - {name}。请确认模块选择或先导入/刷新插件列表。")
        except Exception as e:
            if hasattr(self, 'extractViewer') and self.extractViewer:
                self.extractViewer.setText(f"跳转并运行时出错: {e}")

    def run_block_item(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        cmd = data.get('cmd', '')
        btype = data.get('type', '')
        try:
            base = self.pathLineEdit.text().strip() or None
            out = execute_command_for_ai(cmd, base_path=base, btype=btype)
            # If the output indicates a directory listing, open FileListDialog instead of dumping text
            try:
                _LAST_TRIED_PATHS = globals().get('_LAST_TRIED_PATHS', None)
            except Exception:
                _LAST_TRIED_PATHS = None
            if isinstance(out, str) and out.startswith('目录列出:'):
                # parse listing lines
                lines = out.splitlines()
                # first line is like '目录列出: <path_or_member>' ; rest are children
                if len(lines) >= 1:
                    header = lines[0]
                    children = [l for l in lines[1:] if l.strip()]
                    # prefer using last tried path to find archive or filesystem dir
                    if _LAST_TRIED_PATHS:
                        lp = _LAST_TRIED_PATHS[0]
                        # archive member format: archive_path:member (dir) or archive_path:member
                        if ':' in lp and (lp.endswith('(dir)') or os.path.isfile(lp.split(':', 1)[0])):
                            # archive mode
                            archive_part = lp
                            # strip possible suffix
                            archive_part = archive_part.replace(' (dir)', '')
                            archive_base, member = archive_part.split(':', 1)
                            dlg = None
                            try:
                                from .widgets import FileListDialog
                                dlg = FileListDialog(self.window(), None)
                                dlg.archive_base = archive_base
                                dlg.archive_member_prefix = member
                                dlg.archive_members = children
                                dlg.populate()
                                dlg.exec()
                                return
                            except Exception:
                                pass
                    # fallback: treat header path as filesystem dir if possible
                    # header might be like '目录列出: C:\path' or '目录列出: member'
                    try:
                        hdr_path = header.split(':', 1)[1].strip()
                        if os.path.isdir(hdr_path):
                            from .widgets import FileListDialog
                            dlg = FileListDialog(self.window(), hdr_path)
                            dlg.populate()
                            dlg.exec()
                            return
                    except Exception:
                        pass
                # if we couldn't open dialog, fall back to showing text
            # show in extractor viewer
            if hasattr(self, 'extractViewer') and self.extractViewer:
                self.extractViewer.setText(out)
            # also push tried paths to in-app terminal if available
            try:
                if _LAST_TRIED_PATHS:
                    mw = self.window()
                    if mw and hasattr(mw, 'liveSshInterface'):
                        ls = getattr(mw, 'liveSshInterface')
                        if getattr(ls, 'terminal_window', None):
                            try:
                                ls.terminal_window.append_terminal_output('\n'.join([f"[Extractor] 尝试路径: {p}" for p in _LAST_TRIED_PATHS]) + '\n')
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception as e:
            if hasattr(self, 'extractViewer') and self.extractViewer:
                self.extractViewer.setText(f"执行/读取失败: {e}")

    def _create_text_edit(self):
        return SearchableTextEdit(self)

    def extract_all(self):
        # prefer mapping path from main window HomeWidget
        base_path = None
        try:
            mw = self.window()
            if hasattr(mw, 'mapping_path') and mw.mapping_path:
                base_path = mw.mapping_path
                print("ok")
        except Exception:
            base_path = None
        if not base_path:
            base_path = self.pathLineEdit.text().strip()
        if not base_path or not os.path.exists(base_path):
            msg = "错误: 无效路径。请选择或输入一个存在的提取路径。"
            if hasattr(self, 'extractViewer') and self.extractViewer:
                self.extractViewer.setText(msg)
            return
        self.populate_extractor_plugins()


def execute_command_for_ai(cmd: str, base_path: str | None = None, btype: str = '') -> str:
    """Execute or read the target for extractor/AI use.
    If the block type indicates file extraction, try to read the file from the mapped base_path
    instead of executing via shell/SSH. Otherwise fall back to running the command locally.
    Returns the textual output or an error message.
    """
    # If file-type extraction, try to extract file path
    try:
        # if caller didn't provide base_path, try to read saved mapping_path from settings
        if not base_path:
            try:
                from .constants import get_app_settings
                cfg = get_app_settings()
                mp = cfg.get('mapping_path')
                if mp:
                    base_path = mp
            except Exception:
                base_path = base_path
        if btype and '文件' in btype and cmd:
            # try to find absolute or relative paths in the command (support both / and \\)
            m = re.search(r'([A-Za-z]:[\\/][^\s;\'" ]+)|([\\/][^\s;\'" ]+)|([^\s;\'" ]+[\\/][^\s;\'" ]+)', cmd)
            if m:
                fpath = m.group(0)
                # normalize separators to current OS
                norm_sep = fpath.replace('/', os.sep).replace('\\', os.sep)
                candidates: list[str] = []

                # If base_path provided and fpath is not an absolute path for current OS,
                # prefer joining base_path + fpath first (user expects mapping_path + relative_path).
                if base_path and not os.path.isabs(fpath):
                    # join raw and normalized variants under base_path first
                    candidates.append(os.path.join(base_path, fpath))
                    if norm_sep != fpath:
                        candidates.append(os.path.join(base_path, norm_sep))
                    # also consider stripping leading separators and joining
                    tail = fpath.lstrip('/\\')
                    if tail and tail != fpath:
                        candidates.append(os.path.join(base_path, tail))
                    # fallback to normalized and raw paths
                    candidates.append(norm_sep)
                    candidates.append(fpath)
                else:
                    # treat as absolute (or no base_path): try the path as-is first
                    candidates.append(fpath)
                    if norm_sep != fpath:
                        candidates.append(norm_sep)
                    # if it looks like an absolute unix-style path but base_path provided, also try join as a fallback
                    if base_path and fpath.startswith(('/', '\\')):
                        tail = fpath.lstrip('/\\')
                        candidates.append(os.path.join(base_path, tail))

                # normalize and try candidates
                tried = []
                for c in candidates:
                    try_path = os.path.normpath(c)
                    print(f"尝试路径: {try_path}")
                    tried.append(try_path)
                    # Special-case: if base_path is an archive (tar/zip) and candidates point inside it,
                    # try to read the member from the archive directly.
                    try:
                        if base_path and os.path.isfile(base_path):
                            member = try_path[len(os.path.normpath(base_path)):].lstrip('/\\')
                            # tar
                            try:
                                if tarfile.is_tarfile(base_path):
                                    with tarfile.open(base_path, 'r') as tf:
                                        # exact file
                                        try:
                                            fobj = tf.extractfile(member)
                                            if fobj:
                                                data = fobj.read().decode('utf-8', errors='replace')
                                                try:
                                                    globals()['_LAST_TRIED_PATHS'] = [f"{base_path}:{member}"]
                                                except Exception:
                                                    pass
                                                return data
                                        except KeyError:
                                            pass
                                        # directory inside tar: list members with this prefix
                                        prefix = member.rstrip('/') + '/'
                                        members = [m for m in tf.getnames() if m.startswith(prefix)]
                                        if members:
                                            # compute immediate children
                                            children = set()
                                            for m in members:
                                                tail = m[len(prefix):].split('/', 1)[0]
                                                children.add(tail)
                                            lst = sorted(children)
                                            try:
                                                globals()['_LAST_TRIED_PATHS'] = [f"{base_path}:{member} (dir)"]
                                            except Exception:
                                                pass
                                            return f"目录列出: {member}\n" + "\n".join(lst)
                            except Exception:
                                pass
                            # zip
                            try:
                                if zipfile.is_zipfile(base_path):
                                    with zipfile.ZipFile(base_path, 'r') as zf:
                                        namelist = zf.namelist()
                                        if member in namelist:
                                            try:
                                                data = zf.read(member).decode('utf-8', errors='replace')
                                                try:
                                                    globals()['_LAST_TRIED_PATHS'] = [f"{base_path}:{member}"]
                                                except Exception:
                                                    pass
                                                return data
                                            except KeyError:
                                                pass
                                        # directory inside zip
                                        prefix = member.rstrip('/') + '/'
                                        members = [m for m in namelist if m.startswith(prefix)]
                                        if members:
                                            children = set()
                                            for m in members:
                                                tail = m[len(prefix):].split('/', 1)[0]
                                                children.add(tail)
                                            lst = sorted(children)
                                            try:
                                                globals()['_LAST_TRIED_PATHS'] = [f"{base_path}:{member} (dir)"]
                                            except Exception:
                                                pass
                                            return f"目录列出: {member}\n" + "\n".join(lst)
                            except Exception:
                                pass

                    except Exception:
                        pass

                    if os.path.exists(try_path) and os.path.isfile(try_path):
                        try:
                            with open(try_path, 'r', encoding='utf-8', errors='replace') as rf:
                                # record which path was used
                                try:
                                    globals()['_LAST_TRIED_PATHS'] = [try_path]
                                except Exception:
                                    pass
                                return rf.read()
                        except Exception as e:
                            return f"读取文件失败: {e}"
                    # if it's a directory on local filesystem, list contents
                    if os.path.exists(try_path) and os.path.isdir(try_path):
                        try:
                            entries = sorted(os.listdir(try_path))
                            try:
                                globals()['_LAST_TRIED_PATHS'] = [try_path]
                            except Exception:
                                pass
                            return f"目录列出: {try_path}\n" + "\n".join(entries)
                        except Exception as e:
                            return f"列出目录失败: {e}"

                try:
                    globals()['_LAST_TRIED_PATHS'] = tried
                except Exception:
                    pass
                # Print attempted candidate paths to stdout (visible in the terminal that started the app)
                try:
                    print(f"[Extractor] 目标文件未找到，尝试过的候选路径：{tried}")
                except Exception:
                    pass
                return f"目标文件未找到（尝试过的路径）：{tried}"

        # fallback: run command locally
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (res.stdout or '') + (res.stderr or '')
    except Exception as e:
        return f"执行失败: {e}"
