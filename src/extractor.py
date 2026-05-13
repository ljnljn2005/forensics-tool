import glob
import json
import os
import re
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QListWidgetItem,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, LineEdit, ListWidget, PushButton, SegmentedWidget, SubtitleLabel

from .constants import PLUGINS_DIR, get_app_settings
from .widgets import FileListDialog, SearchableTextEdit


_LAST_TRIED_PATHS: list | None = None
MODULE_LABELS = {
    "windows": "Windows",
    "linux": "Linux",
    "android": "Android",
    "ios": "iOS",
}


PACKAGE_NAME_RE = re.compile(r"(?:^|[\\/])((?:[A-Za-z][A-Za-z0-9_]*\.)+[A-Za-z0-9_]+)(?=[\\/]|$)")
PACKAGE_TOKEN_RE = re.compile(r"\b((?:[A-Za-z][A-Za-z0-9_]*\.)+[A-Za-z0-9_]+)\b")
ANDROID_SYSTEM_ROOT_DEFAULTS = [
    "/data/user/0",
    "/data/data",
    "/data/user_de/0",
    "/data_mirror/data_ce/null/0",
]


def extract_android_package_name(text: str) -> str:
    if not text:
        return ""
    match = PACKAGE_NAME_RE.search(text)
    return match.group(1) if match else ""


def collect_android_template_packages(entries: list[dict]) -> dict[str, list[dict]]:
    packages: dict[str, list[dict]] = {}
    for entry in entries:
        if (entry.get("module") or "").lower() != "android":
            continue
        package_name = str(entry.get("package_name", "")).strip() or extract_android_package_name(entry.get("cmd", ""))
        if not package_name:
            continue
        packages.setdefault(package_name, []).append(entry)
    return packages


def collect_android_installed_packages(base_path: str) -> list[str]:
    if not base_path or not os.path.exists(base_path):
        return []

    packages: set[str] = set()

    def _read_package_lines(path: str):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    yield line.strip()
        except OSError:
            return

    def _read_packages_xml(path: str):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except (OSError, ET.ParseError):
            return set()

        discovered: set[str] = set()
        for package_node in root.iter("package"):
            package_name = str(package_node.attrib.get("name", "")).strip()
            if package_name and PACKAGE_TOKEN_RE.fullmatch(package_name):
                discovered.add(package_name)
        return discovered

    for rel_path in (
        os.path.join("data", "system", "packages.list"),
        os.path.join("system", "packages.list"),
    ):
        full_path = os.path.join(base_path, rel_path)
        if not os.path.isfile(full_path):
            continue
        for line in _read_package_lines(full_path):
            packages.update(PACKAGE_TOKEN_RE.findall(line))

    for rel_path in (
        os.path.join("data", "system", "packages.xml"),
        os.path.join("system", "packages.xml"),
    ):
        full_path = os.path.join(base_path, rel_path)
        if os.path.isfile(full_path):
            packages.update(_read_packages_xml(full_path))

    for rel_dir in (
        os.path.join("data", "data"),
        os.path.join("data", "user", "0"),
        os.path.join("data", "user_de", "0"),
        os.path.join("data_mirror", "data_ce", "null", "0"),
        "data",
    ):
        full_dir = os.path.join(base_path, rel_dir)
        if not os.path.isdir(full_dir):
            continue
        try:
            for name in os.listdir(full_dir):
                package_name = extract_android_package_name(name)
                if package_name:
                    packages.add(package_name)
        except OSError:
            continue

    return sorted(packages)


def get_android_system_roots() -> list[str]:
    settings = get_app_settings()
    configured = settings.get("android_system_roots", [])
    roots: list[str] = []
    if isinstance(configured, str):
        configured = [line.strip() for line in configured.splitlines() if line.strip()]
    if isinstance(configured, list):
        roots.extend(str(item).strip() for item in configured if str(item).strip())

    merged: list[str] = []
    for root in roots + ANDROID_SYSTEM_ROOT_DEFAULTS:
        normalized = "/" + root.strip().replace("\\", "/").strip("/")
        if normalized not in merged:
            merged.append(normalized)
    return merged


def extract_android_plugin_relative_path(cmd: str, package_name: str) -> str:
    normalized = str(cmd or "").strip().replace("\\", "/")
    if not normalized:
        return ""

    if package_name:
        package_marker = f"/{package_name}"
        marker_index = normalized.find(package_marker)
        if marker_index >= 0:
            suffix = normalized[marker_index + len(package_marker):]
            return "/" + suffix.strip("/") if suffix.strip("/") else ""

    for root in get_android_system_roots():
        if normalized == root:
            return ""
        if normalized.startswith(root + "/"):
            remainder = normalized[len(root):]
            package_marker = f"/{package_name}" if package_name else ""
            if package_marker and remainder.startswith(package_marker):
                suffix = remainder[len(package_marker):]
                return "/" + suffix.strip("/") if suffix.strip("/") else ""
            return "/" + remainder.strip("/") if remainder.strip("/") else ""

    return "/" + normalized.strip("/") if normalized.strip("/") else ""


def resolve_android_entry_candidates(mapping_path: str, package_name: str, cmd: str) -> list[str]:
    if not mapping_path or not package_name:
        return []

    mapping_root = os.path.normpath(mapping_path)
    package_segment = package_name.replace(".", os.sep)
    relative_suffix = extract_android_plugin_relative_path(cmd, package_name)
    suffix_segments = [segment for segment in relative_suffix.strip("/").split("/") if segment]

    candidates: list[str] = []
    for system_root in get_android_system_roots():
        system_segments = [segment for segment in system_root.strip("/").split("/") if segment]
        candidate = os.path.join(mapping_root, *system_segments, package_name, *suffix_segments)
        alt_candidate = os.path.join(mapping_root, *system_segments, package_segment, *suffix_segments)
        for path in (candidate, alt_candidate):
            normalized = os.path.normpath(path)
            if normalized not in candidates:
                candidates.append(normalized)
    return candidates


def resolve_mapped_path_candidates(base_path: str | None, target_path: str) -> list[str]:
    if not target_path:
        return []

    normalized = target_path.replace("/", os.sep).replace("\\", os.sep)
    candidates: list[str] = []

    if base_path and not os.path.isabs(target_path):
        candidates.extend(
            [
                os.path.join(base_path, target_path),
                os.path.join(base_path, normalized),
                os.path.join(base_path, target_path.lstrip("/\\")),
                normalized,
                target_path,
            ]
        )
    else:
        candidates.extend([target_path, normalized])
        if base_path and target_path.startswith(("/", "\\")):
            candidates.append(os.path.join(base_path, target_path.lstrip("/\\")))

    deduped: list[str] = []
    for candidate in candidates:
        normalized_candidate = os.path.normpath(candidate)
        if normalized_candidate not in deduped:
            deduped.append(normalized_candidate)
    return deduped


def _archive_member_from_target(base_path: str, target_path: str) -> str:
    base_norm = os.path.normpath(base_path)
    target_norm = os.path.normpath(target_path)
    if target_norm.startswith(base_norm):
        member = target_norm[len(base_norm):].lstrip("/\\")
    else:
        member = str(target_path).lstrip("/\\")
    return member.replace("\\", "/")


def load_mapped_file_bytes(target_path: str, base_path: str | None = None) -> tuple[bytes, str, list[str]]:
    tried_paths = resolve_mapped_path_candidates(base_path, target_path)

    for try_path in tried_paths:
        if os.path.isfile(try_path):
            with open(try_path, "rb") as handle:
                return handle.read(), try_path, tried_paths

    if base_path and os.path.isfile(base_path):
        member_candidates = [_archive_member_from_target(base_path, target_path)]
        member_candidates.extend(_archive_member_from_target(base_path, item) for item in tried_paths)
        deduped_members: list[str] = []
        for member in member_candidates:
            member = member.strip("/")
            if member and member not in deduped_members:
                deduped_members.append(member)

        try:
            if tarfile.is_tarfile(base_path):
                with tarfile.open(base_path, "r") as archive:
                    for member in deduped_members:
                        try:
                            file_obj = archive.extractfile(member)
                        except KeyError:
                            file_obj = None
                        if file_obj:
                            return file_obj.read(), f"{base_path}:{member}", tried_paths
        except Exception:
            pass

        try:
            if zipfile.is_zipfile(base_path):
                with zipfile.ZipFile(base_path, "r") as archive:
                    names = set(archive.namelist())
                    for member in deduped_members:
                        if member in names:
                            return archive.read(member), f"{base_path}:{member}", tried_paths
        except Exception:
            pass

    raise FileNotFoundError(f"target file not found: {target_path}")


def materialize_mapped_file(target_path: str, base_path: str | None = None, suffix: str = "") -> tuple[str, str, list[str]]:
    file_bytes, source_path, tried_paths = load_mapped_file_bytes(target_path, base_path=base_path)
    temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_handle.write(file_bytes)
        temp_handle.flush()
    finally:
        temp_handle.close()
    return temp_handle.name, source_path, tried_paths


class ExtractorInterface(QWidget):
    def __init__(self, parent=None, initial_module: str = "linux", show_module_bar: bool = True, auto_analyze_mode: bool = False):
        super().__init__(parent=parent)
        self.setObjectName("extractorInterface")

        self.current_module = initial_module
        self.fixed_module = initial_module if not show_module_bar else None
        self.auto_analyze_mode = auto_analyze_mode
        self.plugins_file = os.path.join(PLUGINS_DIR, "ssh_plugins.json")
        self._plugin_entries: list[dict] = []

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(16, 16, 16, 16)
        self.vBoxLayout.setSpacing(12)

        self._build_module_bar()
        self._build_title_bar()
        self.vBoxLayout.addLayout(self._build_toolbar())

        self.contentSplitter = QSplitter(Qt.Horizontal, self)
        self.contentSplitter.addWidget(self._build_left_panel())
        self.contentSplitter.addWidget(self._build_center_panel())
        self.contentSplitter.addWidget(self._build_preview_panel())
        self.contentSplitter.setStretchFactor(0, 1)
        self.contentSplitter.setStretchFactor(1, 2)
        self.contentSplitter.setStretchFactor(2, 2)
        self.vBoxLayout.addWidget(self.contentSplitter, 1)

        self.moduleBar.setVisible(show_module_bar)
        self.moduleBar.setCurrentItem(initial_module)
        self._update_mode_labels()
        self.fill_saved_mapping_path()
        self.populate_extractor_plugins()

    def _build_module_bar(self):
        self.moduleBar = SegmentedWidget(self)
        self.moduleBar.addItem("windows", "Windows 分析")
        self.moduleBar.addItem("linux", "Linux 分析")
        self.moduleBar.addItem("android", "Android 分析")
        self.moduleBar.addItem("ios", "iOS 分析")
        self.moduleBar.currentItemChanged.connect(self.on_module_changed)
        self.vBoxLayout.addWidget(self.moduleBar)

    def _build_title_bar(self):
        self.titleLabel = SubtitleLabel("Linux 离线取证工作台", self)
        self.vBoxLayout.addWidget(self.titleLabel)

    def _build_toolbar(self):
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.mappingPathEdit = LineEdit(self)
        self.mappingPathEdit.setPlaceholderText("映射路径，例如: D:/mnt/image 或取证分区根目录")
        layout.addWidget(self.mappingPathEdit, 1)

        self.pathLineEdit = self.mappingPathEdit

        self.useSavedPathBtn = PushButton("使用主页映射路径", self)
        self.useSavedPathBtn.clicked.connect(self.fill_saved_mapping_path)
        self.browseButton = PushButton("浏览...", self)
        self.browseButton.clicked.connect(self.browse_folder)
        self.scanButton = PushButton("扫描并加载", self)
        self.scanButton.clicked.connect(self.extract_all)
        self.copyOutputBtn = PushButton("复制结果", self)
        self.copyOutputBtn.clicked.connect(self.copy_output)

        layout.addWidget(self.useSavedPathBtn)
        layout.addWidget(self.browseButton)
        layout.addWidget(self.scanButton)
        layout.addWidget(self.copyOutputBtn)
        return layout

    def _update_mode_labels(self):
        module_name = MODULE_LABELS.get(self.current_module, self.current_module.capitalize())
        if self.auto_analyze_mode and self.current_module == "android":
            self.titleLabel.setText(f"{module_name} 自动取证工作台")
            self.scanButton.setText("扫描应用并自动分析")
        else:
            self.titleLabel.setText(f"{module_name} 离线取证工作台")
            self.scanButton.setText("扫描并加载")

    def _build_left_panel(self):
        panel = QFrame(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(SubtitleLabel("提取插件", panel))

        self.pluginSummaryLabel = BodyLabel("选择左侧插件，右侧查看目标路径和提取结果。", panel)
        self.pluginSummaryLabel.setWordWrap(True)
        layout.addWidget(self.pluginSummaryLabel)

        self.pluginSearch = LineEdit(panel)
        self.pluginSearch.setPlaceholderText("搜索插件...")
        self.pluginSearch.textChanged.connect(self.filter_extractor_plugin_list)
        layout.addWidget(self.pluginSearch)

        self.extractorPluginList = ListWidget(panel)
        self.extractorPluginList.setObjectName("extractorPluginList")
        self.extractorPluginList.itemClicked.connect(self.on_extractor_plugin_clicked)
        layout.addWidget(self.extractorPluginList, 1)
        return panel

    def _build_center_panel(self):
        panel = QFrame(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("提取积木列表", panel))
        header.addStretch(1)
        self.blockSearch = LineEdit(panel)
        self.blockSearch.setPlaceholderText("搜索名称、路径或来源插件")
        self.blockSearch.textChanged.connect(self.on_block_search_changed)
        header.addWidget(self.blockSearch)
        layout.addLayout(header)

        self.blockTable = QTableWidget(0, 4, panel)
        self.blockTable.setObjectName("extractorBlockTable")
        self.blockTable.setHorizontalHeaderLabels(["名称", "类型", "来源插件", "目标路径/命令"])
        self.blockTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.blockTable.setSelectionMode(QTableWidget.SingleSelection)
        self.blockTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.blockTable.setAlternatingRowColors(True)
        self.blockTable.verticalHeader().setVisible(False)
        self.blockTable.horizontalHeader().setStretchLastSection(True)
        self.blockTable.itemSelectionChanged.connect(self.on_block_selection_changed)
        self.blockTable.itemDoubleClicked.connect(lambda _: self.run_selected_block())
        layout.addWidget(self.blockTable, 1)
        return panel

    def _build_preview_panel(self):
        self.previewPanel = QFrame(self)
        self.previewPanel.setObjectName("extractorPreviewPanel")

        layout = QVBoxLayout(self.previewPanel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.previewTitle = SubtitleLabel("提取结果预览", self.previewPanel)
        layout.addWidget(self.previewTitle)

        self.previewMetaLabel = BodyLabel("未选中文件 / 记录", self.previewPanel)
        self.previewMetaLabel.setWordWrap(True)
        layout.addWidget(self.previewMetaLabel)

        self.previewOutput = SearchableTextEdit(self.previewPanel)
        layout.addWidget(self.previewOutput, 1)

        self.extractViewer = self.previewOutput
        return self.previewPanel

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择目录")
        if folder:
            self.mappingPathEdit.setText(folder)

    def fill_saved_mapping_path(self):
        path = self._current_mapping_path()
        if path:
            self.mappingPathEdit.setText(path)

    def on_module_changed(self, module_key):
        if self.fixed_module:
            module_key = self.fixed_module
        self.current_module = module_key
        self._update_mode_labels()
        self.populate_extractor_plugins()

    def populate_extractor_plugins(self):
        self.extractorPluginList.clear()
        payload = self._load_plugin_payload()

        self._plugin_entries = []
        for group_name, group_data in payload.items():
            blocks = group_data.get("blocks", []) if isinstance(group_data, dict) else group_data
            for block in blocks or []:
                if not isinstance(block, dict):
                    continue
                block_module = (block.get("module") or "").lower()
                block_type = block.get("type", "")
                if block_module and block_module != self.current_module:
                    continue
                if "文件" not in block_type and "提取" not in block_type:
                    continue
                entry = {
                    "group": group_name,
                    "plugin": group_name,
                    "name": block.get("name", ""),
                    "cmd": block.get("cmd", ""),
                    "type": block_type,
                    "module": block_module or self.current_module,
                }
                self._plugin_entries.append(entry)

        for entry in self._plugin_entries:
            item = QListWidgetItem(f"{entry['group']} - {entry['name']}")
            item.setData(Qt.UserRole, entry)
            self.extractorPluginList.addItem(item)

        self.pluginSummaryLabel.setText(
            f"{MODULE_LABELS.get(self.current_module, self.current_module)} 模块已加载 {len(self._plugin_entries)} 个文件提取积木。"
        )
        self._render_block_table(self._plugin_entries)
        if self.extractorPluginList.count():
            self.extractorPluginList.setCurrentRow(0)
            self.on_extractor_plugin_clicked(self.extractorPluginList.item(0))
        else:
            self.previewTitle.setText("提取结果预览")
            self.previewMetaLabel.setText("当前模块未找到文件提取积木")
            self.previewOutput.setText("当前模块没有可用的文件提取插件。")

    def filter_extractor_plugin_list(self, text):
        keyword = text.strip().lower()
        for index in range(self.extractorPluginList.count()):
            item = self.extractorPluginList.item(index)
            item.setHidden(bool(keyword) and keyword not in item.text().lower())

    def on_block_search_changed(self, text):
        keyword = text.strip().lower()
        if not keyword:
            self._render_block_table(self._plugin_entries)
            return

        filtered = []
        for entry in self._plugin_entries:
            haystack = " ".join([entry.get("group", ""), entry.get("name", ""), entry.get("cmd", ""), entry.get("type", "")]).lower()
            if keyword in haystack:
                filtered.append(entry)
        self._render_block_table(filtered)

    def on_extractor_plugin_clicked(self, item):
        if not item:
            return
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        self._select_entry_in_table(entry)
        self.on_block_selection_changed()

    def select_and_run_plugin(self, group: str, name: str, base_path: str | None = None):
        try:
            if base_path and isinstance(base_path, str):
                self.mappingPathEdit.setText(base_path)
            self.populate_extractor_plugins()
            target = None
            for entry in self._plugin_entries:
                if entry.get("group") == group and entry.get("name") == name:
                    target = entry
                    break
            if target is None:
                for entry in self._plugin_entries:
                    if group in entry.get("group", "") and name in entry.get("name", ""):
                        target = entry
                        break
            if not target:
                self.previewOutput.setText(f"未在当前模块找到插件: {group} - {name}。请确认模块选择或先刷新插件列表。")
                return
            self._select_entry_in_table(target)
            self.run_selected_block()
        except Exception as exc:
            self.previewOutput.setText(f"跳转并运行时出错: {exc}")

    def run_selected_block(self):
        row = self.blockTable.currentRow()
        if row < 0:
            self.previewOutput.setText("请先选择一个文件提取积木。")
            return
        item = QListWidgetItem()
        item.setData(Qt.UserRole, self._current_table_entry())
        self.run_block_item(item)

    def run_block_item(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return

        self.previewTitle.setText(f"提取结果 / {data.get('name') or '未命名积木'}")
        self.previewMetaLabel.setText(
            f"来源插件: {data.get('group', '')}    类型: {data.get('type', '')}    映射路径: {self.mappingPathEdit.text().strip() or '未设置'}"
        )
        self.previewOutput.setText(self._execute_plugin_entry(data, show_listing_dialog=True))

    def _execute_plugin_entry(self, entry: dict, show_listing_dialog: bool = False) -> str:
        cmd = entry.get("cmd", "")
        btype = entry.get("type", "")
        base = self.mappingPathEdit.text().strip() or None
        try:
            out = execute_command_for_ai(cmd, base_path=base, btype=btype)
            tried_paths = globals().get("_LAST_TRIED_PATHS", None)
            if show_listing_dialog and isinstance(out, str) and out.startswith("目录列出:"):
                self._open_listing_dialog(out, tried_paths)
            return out
        except Exception as exc:
            return f"执行/读取失败: {exc}"

    def _open_listing_dialog(self, output_text: str, tried_paths):
        lines = output_text.splitlines()
        if not lines:
            return

        header = lines[0]
        children = [line for line in lines[1:] if line.strip()]
        if tried_paths:
            first_path = tried_paths[0]
            if ":" in first_path and os.path.isfile(first_path.split(":", 1)[0]):
                archive_base, member = first_path.replace(" (dir)", "").split(":", 1)
                dialog = FileListDialog(self.window(), None)
                dialog.archive_base = archive_base
                dialog.archive_member_prefix = member
                dialog.archive_members = children
                dialog.populate()
                dialog.exec()
                return

        try:
            dir_path = header.split(":", 1)[1].strip()
            if os.path.isdir(dir_path):
                dialog = FileListDialog(self.window(), dir_path)
                dialog.populate()
                dialog.exec()
        except Exception:
            pass

    def _current_mapping_path(self):
        try:
            window = self.window()
            if hasattr(window, "mapping_path") and window.mapping_path:
                return window.mapping_path
        except Exception:
            pass
        try:
            return get_app_settings().get("mapping_path", "") or self.mappingPathEdit.text().strip()
        except Exception:
            return self.mappingPathEdit.text().strip()

    def extract_all(self):
        base_path = self._current_mapping_path()
        if not base_path or not os.path.exists(base_path):
            self.previewTitle.setText("提取结果预览")
            self.previewMetaLabel.setText("映射路径不可用")
            self.previewOutput.setText("错误: 无效路径。请选择或输入一个存在的提取路径。")
            return

        self.mappingPathEdit.setText(base_path)
        self.populate_extractor_plugins()
        self.previewMetaLabel.setText(f"映射路径: {base_path}")
        if self.current_module == "android" and self.auto_analyze_mode:
            self._auto_analyze_android_apps(base_path)

    def _auto_analyze_android_apps(self, base_path: str):
        installed_packages = collect_android_installed_packages(base_path)
        template_map = collect_android_template_packages(self._plugin_entries)

        lines = [
            "已安装应用扫描结果",
            f"映射路径: {base_path}",
            f"已识别应用数量: {len(installed_packages)}",
        ]

        if installed_packages:
            preview_packages = ", ".join(installed_packages[:15])
            if len(installed_packages) > 15:
                preview_packages += " ..."
            lines.append(f"应用包名: {preview_packages}")
        else:
            lines.append("未识别到已安装应用包名。")

        matched_packages = [package_name for package_name in installed_packages if package_name in template_map]
        if not matched_packages:
            lines.append("")
            lines.append("未命中内置应用模板。")
            self.previewTitle.setText("Android 自动分析")
            self.previewMetaLabel.setText("已完成应用扫描，当前没有匹配模板。")
            self.previewOutput.setText("\n".join(lines))
            return

        lines.append(f"命中模板数量: {len(matched_packages)}")
        lines.append("")
        lines.append("自动分析结果")

        for package_name in matched_packages:
            lines.append(f"[{package_name}]")
            for entry in template_map.get(package_name, []):
                lines.append(f"- {entry.get('group', '')} / {entry.get('name', '')}")
                result = self._execute_plugin_entry(entry, show_listing_dialog=False).strip()
                lines.append(result if result else "(无结果)")
                lines.append("")

        self.previewTitle.setText("Android 自动分析")
        self.previewMetaLabel.setText(f"已自动分析 {len(matched_packages)} 个命中模板的应用。")
        self.previewOutput.setText("\n".join(lines).strip())

    def copy_output(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.previewOutput.textEdit.toPlainText())

    def _render_block_table(self, entries: list[dict]):
        self.blockTable.setRowCount(0)
        for row, entry in enumerate(entries):
            self.blockTable.insertRow(row)
            values = [
                entry.get("name", ""),
                entry.get("type", ""),
                entry.get("group", ""),
                entry.get("cmd", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, entry)
                if column == 0:
                    item.setForeground(QBrush(QColor("#c25f30")))
                self.blockTable.setItem(row, column, item)

    def _select_entry_in_table(self, entry: dict):
        for row in range(self.blockTable.rowCount()):
            row_entry = self.blockTable.item(row, 0).data(Qt.UserRole)
            if row_entry == entry:
                self.blockTable.selectRow(row)
                return

    def _current_table_entry(self):
        row = self.blockTable.currentRow()
        if row < 0:
            return None
        item = self.blockTable.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    def on_block_selection_changed(self):
        entry = self._current_table_entry()
        if not entry:
            return
        self.previewTitle.setText(f"提取预览 / {entry.get('name') or '未命名积木'}")
        self.previewMetaLabel.setText(
            f"来源插件: {entry.get('group', '')}    类型: {entry.get('type', '')}    当前模块: {MODULE_LABELS.get(self.current_module, self.current_module)}"
        )
        self.previewOutput.setText(
            f"目标路径/命令:\n{entry.get('cmd', '')}\n\n双击表格行可直接运行提取。"
        )

    def _load_plugin_payload(self) -> dict:
        try:
            with open(self.plugins_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def execute_command_for_ai(cmd: str, base_path: str | None = None, btype: str = "") -> str:
    """Read mapped files for extractor/search use, or fall back to running a local command."""
    try:
        if not base_path:
            try:
                base_path = get_app_settings().get("mapping_path")
            except Exception:
                base_path = base_path

        if btype and "文件" in btype and cmd:
            match = re.search(r'([A-Za-z]:[\\/][^\s;\'" ]+)|([\\/][^\s;\'" ]+)|([^\s;\'" ]+[\\/][^\s;\'" ]+)|([^\s;\'"]+\.[A-Za-z0-9_]+)', cmd)
            if match:
                fpath = match.group(0)
                normalized = fpath.replace("/", os.sep).replace("\\", os.sep)
                candidates: list[str] = []

                if base_path and not os.path.isabs(fpath):
                    candidates.extend(
                        [
                            os.path.join(base_path, fpath),
                            os.path.join(base_path, normalized),
                            os.path.join(base_path, fpath.lstrip("/\\")),
                            normalized,
                            fpath,
                        ]
                    )
                else:
                    candidates.extend([fpath, normalized])
                    if base_path and fpath.startswith(("/", "\\")):
                        candidates.append(os.path.join(base_path, fpath.lstrip("/\\")))

                tried = []
                for candidate in candidates:
                    try_path = os.path.normpath(candidate)
                    tried.append(try_path)

                    archive_output = _try_read_from_archive(base_path, try_path)
                    if archive_output is not None:
                        return archive_output

                    if os.path.isfile(try_path):
                        with open(try_path, "r", encoding="utf-8", errors="replace") as handle:
                            globals()["_LAST_TRIED_PATHS"] = [try_path]
                            return handle.read()
                    if os.path.isdir(try_path):
                        globals()["_LAST_TRIED_PATHS"] = [try_path]
                        return "目录列出: " + try_path + "\n" + "\n".join(sorted(os.listdir(try_path)))

                globals()["_LAST_TRIED_PATHS"] = tried
                return f"目标文件未找到（尝试过的路径）: {tried}"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (result.stdout or "") + (result.stderr or "")
    except Exception as exc:
        return f"执行失败: {exc}"


def _try_read_from_archive(base_path: str | None, try_path: str) -> str | None:
    if not base_path or not os.path.isfile(base_path):
        return None

    member = try_path[len(os.path.normpath(base_path)):].lstrip("/\\")
    if not member:
        return None

    try:
        if tarfile.is_tarfile(base_path):
            with tarfile.open(base_path, "r") as archive:
                try:
                    file_obj = archive.extractfile(member)
                    if file_obj:
                        globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member}"]
                        return file_obj.read().decode("utf-8", errors="replace")
                except KeyError:
                    pass
                prefix = member.rstrip("/") + "/"
                members = [name for name in archive.getnames() if name.startswith(prefix)]
                if members:
                    children = sorted({name[len(prefix):].split("/", 1)[0] for name in members})
                    globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member} (dir)"]
                    return "目录列出: " + member + "\n" + "\n".join(children)
    except Exception:
        pass

    try:
        if zipfile.is_zipfile(base_path):
            with zipfile.ZipFile(base_path, "r") as archive:
                names = archive.namelist()
                if member in names:
                    globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member}"]
                    return archive.read(member).decode("utf-8", errors="replace")
                prefix = member.rstrip("/") + "/"
                members = [name for name in names if name.startswith(prefix)]
                if members:
                    children = sorted({name[len(prefix):].split("/", 1)[0] for name in members})
                    globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member} (dir)"]
                    return "目录列出: " + member + "\n" + "\n".join(children)
    except Exception:
        pass

    return None
