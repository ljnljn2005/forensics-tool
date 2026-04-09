import os, re

def main():
    path = "d:/Coding/forensicstool/main.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update LiveSshInterface extract_live_info
    old_live_extract = """            current_item = self.pluginList.currentItem()
            if current_item:
                plugin_name = current_item.text()
                cmds = self.plugins_data.get(plugin_name, [])
            else:
                cmds = [{"name": "默认测试", "cmd": "w"}]"""
                
    new_live_extract = """            current_item = self.pluginList.currentItem()
            if current_item:
                plugin_name = current_item.text()
                p_data = self.plugins_data.get(plugin_name, [])
                cmds = p_data.get("blocks", []) if isinstance(p_data, dict) else p_data
            else:
                cmds = [{"name": "默认测试", "cmd": "w"}]"""
    content = content.replace(old_live_extract, new_live_extract)


    # 2. Add Author and Desc fields to PluginEditorInterface
    old_editor_init = """        self.nameLayout = QHBoxLayout()
        self.nameLayout.addWidget(BodyLabel("插件名称: "))
        self.pluginNameEdit = LineEdit(self)
        self.nameLayout.addWidget(self.pluginNameEdit, 1)
        self.rightPanel.addLayout(self.nameLayout)

        self.blockList = BlockListWidget(self)"""
        
    new_editor_init = """        self.nameLayout = QHBoxLayout()
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

        self.blockList = BlockListWidget(self)"""
    content = content.replace(old_editor_init, new_editor_init)


    # 3. Add Upload Button
    old_btn_layout = """        self.rightBtnLayout = QHBoxLayout()
        self.addCmdBtn = PushButton("添加积木(命令)", self)
        self.addCmdBtn.clicked.connect(self.add_command_block)

        self.savePluginBtn = PrimaryPushButton("保存插件", self)"""
        
    new_btn_layout = """        self.rightBtnLayout = QHBoxLayout()
        
        self.uploadBtn = PushButton(FluentIcon.SHARE, "发布到仓库(市场)", self)
        self.uploadBtn.clicked.connect(self.upload_plugin)
        
        self.addCmdBtn = PushButton("添加积木(命令)", self)
        self.addCmdBtn.clicked.connect(self.add_command_block)

        self.savePluginBtn = PrimaryPushButton("保存插件", self)"""
    content = content.replace(old_btn_layout, new_btn_layout)
    
    old_btn_layout2 = """        self.rightBtnLayout.addWidget(self.addCmdBtn)
        self.rightBtnLayout.addStretch(1)
        self.rightBtnLayout.addWidget(self.savePluginBtn)"""
        
    new_btn_layout2 = """        self.rightBtnLayout.addWidget(self.uploadBtn)
        self.rightBtnLayout.addWidget(self.addCmdBtn)
        self.rightBtnLayout.addStretch(1)
        self.rightBtnLayout.addWidget(self.savePluginBtn)"""
    content = content.replace(old_btn_layout2, new_btn_layout2)


    # 4. Rewrite on_plugin_selected and save_plugin
    old_on_selected = """    def on_plugin_selected(self, item):
        name = item.text()
        self.current_plugin = name
        self.pluginNameEdit.setText(name)
        self.blockList.clear_blocks()
        cmds = self.plugins_data.get(name, [])
        for c in cmds:
            self.blockList.add_block(c.get("name", ""), c.get("cmd", ""), c.get("type", "SSH命令"))

    def save_plugin(self):
        from PySide6.QtCore import Qt
        name = self.pluginNameEdit.text().strip()
        if not name: return
        cmds = self.blockList.get_all_blocks()
        self.plugins_data[name] = cmds
        self._save_to_file()
        self.refresh_list()
        items = self.pluginList.findItems(name, Qt.MatchExactly)
        if items: self.pluginList.setCurrentItem(items[0])"""
        
    new_on_selected = """    def on_plugin_selected(self, item):
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
        import os, json, subprocess
        
        name = self.pluginNameEdit.text().strip()
        if not name:
            InfoBar.error("发布失败", "请先输入插件名称", parent=self, position=InfoBarPosition.TOP)
            return
            
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'forensicstool-plugins'))
        if not os.path.exists(repo_dir):
            InfoBar.error("发布失败", f"找不到本地仓库: {repo_dir}", parent=self, position=InfoBarPosition.TOP)
            return

        market_file = os.path.join(repo_dir, "market.json")
        market_data = []
        if os.path.exists(market_file):
            try:
                with open(market_file, 'r', encoding='utf-8') as f:
                    market_data = json.load(f)
            except: pass
            
        plugin_obj = {
            "name": name,
            "author": self.authorEdit.text().strip() or "Anonymous",
            "description": self.descEdit.text().strip() or "No description",
            "blocks": self.blockList.get_all_blocks()
        }
        
        # update if exists
        updated = False
        for i, p in enumerate(market_data):
            if p.get("name") == name:
                market_data[i] = plugin_obj
                updated = True
                break
        if not updated:
            market_data.append(plugin_obj)
            
        try:
            with open(market_file, 'w', encoding='utf-8') as f:
                json.dump(market_data, f, indent=4, ensure_ascii=False)
                
            subprocess.run(['git', 'add', 'market.json'], cwd=repo_dir, shell=True)
            subprocess.run(['git', 'commit', '-m', f'Update plugin {name}'], cwd=repo_dir, capture_output=True, shell=True)
            
            InfoBar.success("发布成功", f"插件 {name} 已发布到本地市场仓库并 Commit！", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("发布失败", f"写入市场文件或 Git Commit 时出错: {e}", parent=self, position=InfoBarPosition.TOP)"""
    content = content.replace(old_on_selected, new_on_selected)
    
    # 5. Make fetch_market support local file://
    old_fetch = """        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ForensicTool'})
            with urllib.request.urlopen(req, timeout=5) as response:
                self.market_data = json.loads(response.read().decode('utf-8'))
            self.populate_list(self.market_data)
            InfoBar.success("刷新成功", f"拉取到 {len(self.market_data)} 个插件", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("获取失败", f"无法拉取市场数据 (请检查是否需要创建服务端库):\\n{e}", parent=self, position=InfoBarPosition.TOP)"""

    new_fetch = """        try:
            if url.startswith('http'):
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ForensicTool'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    self.market_data = json.loads(response.read().decode('utf-8'))
            else:
                local_path = url
                if url.startswith('file:///'):
                    local_path = url[8:]
                elif url.startswith('file://'):
                    local_path = url[7:]
                with open(local_path, 'r', encoding='utf-8') as f:
                    self.market_data = json.load(f)
            self.populate_list(self.market_data)
            InfoBar.success("刷新成功", f"拉取到 {len(self.market_data)} 个插件", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("获取失败", f"无法拉取市场数据: {e}", parent=self, position=InfoBarPosition.TOP)"""
            
    content = content.replace(old_fetch, new_fetch)
    
    # Update default URL to the local repo
    content = content.replace('"https://raw.githubusercontent.com/liang-sh/forensicstool-plugins/main/market.json"', 
                              'os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "forensicstool-plugins", "market.json")).replace("\\\\", "/")')
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Upload patch applied successfully.")

main()