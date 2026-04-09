import sys

def patch(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    start_str = "class PluginEditorInterface(QWidget):"
    end_str = "class HomeWidget(QWidget):"

    start_idx = content.find(start_str)
    end_idx = content.find(end_str)

    if start_idx == -1 or end_idx == -1:
        print("Could not find start or end index.")
        return

    new_code = """class CommandBlockWidget(QWidget):
    def __init__(self, name="", cmd="", del_callback=None, data_changed_callback=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        self.nameEdit = LineEdit(self)
        self.nameEdit.setPlaceholderText("标题 (如: 网络端口)")
        self.nameEdit.setText(name)
        self.cmdEdit = LineEdit(self)
        self.cmdEdit.setPlaceholderText("命令 (如: netstat -an)")
        self.cmdEdit.setText(cmd)
        
        self.delBtn = TransparentToolButton(FluentIcon.DELETE, self)
        if del_callback:
            self.delBtn.clicked.connect(del_callback)
            
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

    def add_block(self, name="", cmd=""):
        item = QListWidgetItem(self)
        item.setSizeHint(self.get_widget_size_hint())
        item.setData(Qt.UserRole, {"name": name, "cmd": cmd})
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
                item.setData(Qt.UserRole, {"name": w.nameEdit.text(), "cmd": w.cmdEdit.text()})
                
        def on_del():
            self.takeItem(self.row(item))

        w = CommandBlockWidget(data["name"], data["cmd"], on_del, on_data_changed, self)
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
                cmds.append({"name": data["name"].strip(), "cmd": data["cmd"].strip()})
        return cmds

    def clear_blocks(self):
        self.clear()

class PluginEditorInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('pluginEditorInterface')
        import os, json
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.plugins_file = os.path.join(BASE_DIR, 'plugins', 'ssh_plugins.json')
        self.plugins_data = {}
        self.current_plugin = None

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.hBoxLayout.setSpacing(16)

        self.leftPanel = QVBoxLayout()
        self.leftPanel.addWidget(SubtitleLabel("保存的插件", self))
        
        self.pluginList = ListWidget(self)
        self.pluginList.itemClicked.connect(self.on_plugin_selected)
        self.leftPanel.addWidget(self.pluginList)
        
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
        
        self.blockList = BlockListWidget(self)
        self.rightPanel.addWidget(self.blockList, 1)
        
        self.rightBtnLayout = QHBoxLayout()
        self.addCmdBtn = PushButton("添加积木(命令)", self)
        self.addCmdBtn.clicked.connect(self.add_command_block)
        
        self.savePluginBtn = PrimaryPushButton("保存插件", self)
        self.savePluginBtn.clicked.connect(self.save_plugin)
        
        self.rightBtnLayout.addWidget(self.addCmdBtn)
        self.rightBtnLayout.addStretch(1)
        self.rightBtnLayout.addWidget(self.savePluginBtn)
        self.rightPanel.addLayout(self.rightBtnLayout)

        self.hBoxLayout.addLayout(self.rightPanel, 3)
        self.load_plugins()

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
        self.blockList.add_block(name, cmd)

    def on_plugin_selected(self, item):
        name = item.text()
        self.current_plugin = name
        self.pluginNameEdit.setText(name)
        self.blockList.clear_blocks()
        cmds = self.plugins_data.get(name, [])
        for c in cmds:
            self.blockList.add_block(c.get("name", ""), c.get("cmd", ""))

    def save_plugin(self):
        from PySide6.QtCore import Qt
        name = self.pluginNameEdit.text().strip()
        if not name: return
        cmds = self.blockList.get_all_blocks()
        self.plugins_data[name] = cmds
        self._save_to_file()
        self.refresh_list()
        items = self.pluginList.findItems(name, Qt.MatchExactly)
        if items: self.pluginList.setCurrentItem(items[0])

"""

    updated_content = content[:start_idx] + new_code + content[end_idx:]
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    print("Plugin editor drag n drop successfully updated.")

patch('d:/Coding/forensicstool/main.py')
