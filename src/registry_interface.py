import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, LineEdit, ListWidget, PrimaryPushButton, PushButton, SubtitleLabel

from .constants import PLUGINS_DIR, get_app_settings
from .widgets import SearchableTextEdit
from .windows_registry import (
    RegistrySearchItem,
    extract_registry_search_items,
    lookup_default_apps_report,
    query_registry_path_report,
)


class RegistryScanInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("registryScanInterface")
        self.plugins_file = os.path.join(PLUGINS_DIR, "ssh_plugins.json")
        self.plugins_data = {}
        self.search_items = []

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.hBoxLayout.setSpacing(16)

        self.leftPanel = QVBoxLayout()
        self.leftPanel.addWidget(SubtitleLabel("注册表查找项", self))

        self.searchEdit = LineEdit(self)
        self.searchEdit.setPlaceholderText("搜索插件项、名称或注册表路径")
        self.searchEdit.textChanged.connect(self.filter_items)
        self.leftPanel.addWidget(self.searchEdit)

        self.itemList = ListWidget(self)
        self.itemList.itemClicked.connect(self.on_item_clicked)
        self.leftPanel.addWidget(self.itemList, 1)

        self.refreshBtn = PushButton("刷新插件项", self)
        self.refreshBtn.clicked.connect(self.load_plugins)
        self.leftPanel.addWidget(self.refreshBtn)

        self.rightPanelWidget = QWidget(self)
        self.rightPanel = QVBoxLayout(self.rightPanelWidget)
        self.rightPanel.setContentsMargins(0, 0, 0, 0)
        self.rightPanel.setSpacing(12)

        self.titleLabel = SubtitleLabel("扫描注册表", self.rightPanelWidget)
        self.rightPanel.addWidget(self.titleLabel)

        pathLayout = QHBoxLayout()
        pathLayout.addWidget(BodyLabel("映射路径:", self.rightPanelWidget))
        self.mappingPathEdit = LineEdit(self.rightPanelWidget)
        self.mappingPathEdit.setPlaceholderText("例如: D:/mnt/windows-image")
        pathLayout.addWidget(self.mappingPathEdit, 1)
        self.useSavedPathBtn = PushButton("使用主页路径", self.rightPanelWidget)
        self.useSavedPathBtn.clicked.connect(self.fill_saved_mapping_path)
        pathLayout.addWidget(self.useSavedPathBtn)
        self.rightPanel.addLayout(pathLayout)

        actionLayout = QHBoxLayout()
        self.runBtn = PrimaryPushButton("运行选中项", self.rightPanelWidget)
        self.runBtn.clicked.connect(self.run_selected_item)
        actionLayout.addWidget(self.runBtn)
        actionLayout.addStretch(1)
        self.rightPanel.addLayout(actionLayout)

        self.resultViewer = SearchableTextEdit(self.rightPanelWidget)
        self.resultViewer.setText("选择左侧注册表查找项后运行。插件项会从插件文件中自动导入。")
        self.rightPanel.addWidget(self.resultViewer, 1)

        self.hBoxLayout.addLayout(self.leftPanel, 1)
        self.hBoxLayout.addWidget(self.rightPanelWidget, 3)

        self.fill_saved_mapping_path()
        self.load_plugins()

    def fill_saved_mapping_path(self):
        path = self._current_mapping_path()
        if path:
            self.mappingPathEdit.setText(path)

    def _current_mapping_path(self):
        try:
            mw = self.window()
            if hasattr(mw, "mapping_path") and mw.mapping_path:
                return mw.mapping_path
        except Exception:
            pass
        try:
            return get_app_settings().get("mapping_path", "")
        except Exception:
            return ""

    def load_plugins(self):
        try:
            if os.path.exists(self.plugins_file):
                with open(self.plugins_file, "r", encoding="utf-8") as f:
                    self.plugins_data = json.load(f)
            else:
                self.plugins_data = {}
        except Exception:
            self.plugins_data = {}
        self.load_search_items()

    def load_search_items(self):
        self.search_items = [
            {
                "plugin": "内置",
                "name": "默认应用",
                "kind": "default_apps",
                "registry_path": "",
                "description": "读取用户默认应用关联",
            }
        ]
        for item in extract_registry_search_items(self.plugins_data):
            self.search_items.append(
                {
                    "plugin": item.plugin,
                    "name": item.name,
                    "kind": "registry_path",
                    "registry_path": item.registry_path,
                    "description": item.description,
                }
            )
        self._render_items()

    def _render_items(self):
        keyword = self.searchEdit.text().strip().lower()
        self.itemList.clear()
        for item in self.search_items:
            haystack = " ".join(
                [
                    item.get("plugin", ""),
                    item.get("name", ""),
                    item.get("registry_path", ""),
                    item.get("description", ""),
                ]
            ).lower()
            if keyword and keyword not in haystack:
                continue
            list_item = QListWidgetItem(self.itemList)
            list_item.setText(f"{item['plugin']} - {item['name']}")
            list_item.setData(Qt.UserRole, item)
            self.itemList.addItem(list_item)
        if self.itemList.count() > 0 and self.itemList.currentRow() < 0:
            self.itemList.setCurrentRow(0)

    def filter_items(self, _text):
        self._render_items()

    def on_item_clicked(self, item):
        data = item.data(Qt.UserRole) if item else None
        if not data:
            return
        path = data.get("registry_path") or "内置默认应用扫描"
        self.resultViewer.setText(f"已选择: {data.get('plugin')} - {data.get('name')}\n目标: {path}")

    def run_selected_item(self):
        item = self.itemList.currentItem()
        if not item:
            self.resultViewer.setText("请先选择一个注册表查找项。")
            return
        data = item.data(Qt.UserRole)
        if not data:
            self.resultViewer.setText("选中项没有可执行的注册表查找配置。")
            return

        mapping_path = self.mappingPathEdit.text().strip() or self._current_mapping_path()
        if data.get("kind") == "default_apps":
            report = lookup_default_apps_report(mapping_path)
        else:
            report = query_registry_path_report(mapping_path, data.get("registry_path", ""))
        self.resultViewer.setText(report)
