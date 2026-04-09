import os
import json
import urllib.request
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem
from qfluentwidgets import SubtitleLabel, BodyLabel, CaptionLabel, PrimaryPushButton, ListWidget, SearchLineEdit, LineEdit, PushButton, InfoBar, InfoBarPosition
from qfluentwidgets import FluentIcon
from PySide6.QtCore import Qt, QSize
from .constants import PLUGINS_DIR, get_app_proxy
from .constants import get_app_settings


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
        # revert to flexible description height for better layout
        blocks = plugin_data.get('blocks', []) or []
        has_ssh = any(isinstance(b, dict) and ("SSH" in (b.get('type') or '') or "命令" in (b.get('type') or '')) for b in blocks)
        has_file = any(isinstance(b, dict) and ("文件" in (b.get('type') or '') or "提取" in (b.get('type') or '')) for b in blocks)
        applicability = []
        if has_ssh:
            applicability.append('SSH')
        if has_file:
            applicability.append('文件提取')
        if not applicability:
            applicability_text = '通用'
        else:
            applicability_text = ' / '.join(applicability)
        self.appLabel = CaptionLabel(f"适用: {applicability_text}", self)

        infoLayout.addWidget(self.nameLabel)
        infoLayout.addWidget(self.authorLabel)
        infoLayout.addWidget(self.descLabel)
        infoLayout.addWidget(self.appLabel)

        layout.addLayout(infoLayout, 1)
        # restore original download text
        self.downloadBtn = PrimaryPushButton(FluentIcon.DOWNLOAD, "下载安装", self)
        layout.addWidget(self.downloadBtn)


class PluginMarketInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('pluginMarketInterface')
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)

        self.titleLabel = SubtitleLabel("插件市场", self)
        self.vBoxLayout.addWidget(self.titleLabel)

        self.headerLayout = QHBoxLayout()
        self.repoEdit = LineEdit(self)
        # default to global setting if present
        try:
            app_cfg = get_app_settings()
            default_repo = app_cfg.get('market_repo', '')
        except Exception:
            default_repo = ''
        if default_repo:
            self.repoEdit.setText(default_repo)
        else:
            self.repoEdit.setText("https://api.github.com/repos/ljnljn2005/forensics-plugin-market/contents/")
        self.repoEdit.setPlaceholderText("市场数据所在的远程 URL (如 GitHub API 或本地目录)")
        self.searchEdit = SearchLineEdit(self)
        self.searchEdit.setPlaceholderText("搜索插件...")
        self.refreshBtn = PushButton(FluentIcon.SYNC, "拉取列表", self)
        self.headerLayout.addWidget(self.repoEdit, 2)
        self.headerLayout.addWidget(self.searchEdit, 1)
        self.headerLayout.addWidget(self.refreshBtn)
        self.vBoxLayout.addLayout(self.headerLayout)

        self.marketList = ListWidget(self)
        self.vBoxLayout.addWidget(self.marketList, 1)

        self.refreshBtn.clicked.connect(self.fetch_market)
        self.searchEdit.textChanged.connect(self.filter_list)
        self.market_data = []

    def fetch_market(self):
        url = self.repoEdit.text().strip()
        if not url: return
        proxy_str = get_app_proxy()
        try:
            self.market_data = []
            # prepare urllib opener honoring proxy setting
            opener = None
            if proxy_str:
                proxy_handler = urllib.request.ProxyHandler({'http': proxy_str, 'https': proxy_str})
                opener = urllib.request.build_opener(proxy_handler)

            if url.startswith('http'):
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ForensicTool'})
                response = opener.open(req, timeout=10) if opener else urllib.request.urlopen(req, timeout=10)
                files = json.loads(response.read().decode('utf-8'))
                for file_info in files:
                    if isinstance(file_info, dict) and file_info.get("name", "").endswith(".json") and file_info.get("name") != "market.json":
                        download_url = file_info.get("download_url")
                        if download_url:
                            try:
                                from urllib import parse as urllib_parse
                                parsed = urllib_parse.urlsplit(download_url)
                                encoded_path = urllib_parse.quote(urllib_parse.unquote(parsed.path))
                                safe_url = urllib_parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment))
                                child_req = urllib.request.Request(safe_url, headers={'User-Agent': 'Mozilla/5.0 ForensicTool'})
                                child_res = opener.open(child_req, timeout=10) if opener else urllib.request.urlopen(child_req, timeout=10)
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
                                except:
                                    pass
                else:
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
        self.marketList.clear()
        for p in data:
            item = QListWidgetItem(self.marketList)
            item.setSizeHint(QSize(0, 100))
            item.setData(Qt.UserRole, p)
            self.marketList.addItem(item)
            w = MarketCardWidget(p, self.marketList)
            w.downloadBtn.clicked.connect(lambda _, p_data=p: self.install_plugin(p_data))
            self.marketList.setItemWidget(item, w)

    def filter_list(self, text):
        for i in range(self.marketList.count()):
            item = self.marketList.item(i)
            p = item.data(Qt.UserRole)
            match = text.lower() in p.get("name", "").lower() or text.lower() in p.get("description", "").lower()
            item.setHidden(not match)

    def install_plugin(self, plugin_data):
        plugins_file = os.path.join(PLUGINS_DIR, 'ssh_plugins.json')
        local_data = {}
        if os.path.exists(plugins_file):
            try:
                with open(plugins_file, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
            except:
                pass
        name = plugin_data.get("name", "未命名插件")
        blocks = plugin_data.get("blocks", [])
        # Ensure each block has a module/platform field and normalize structure
        normalized_blocks = []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            blk = dict(b)
            # keep existing module if present, otherwise default by type
            if not blk.get('module'):
                # try to infer from type or leave default 'linux'
                typ = (blk.get('type') or '').lower()
                if 'windows' in typ or 'win' in typ:
                    blk['module'] = 'windows'
                elif 'android' in typ:
                    blk['module'] = 'android'
                elif 'ios' in typ:
                    blk['module'] = 'ios'
                else:
                    blk['module'] = 'linux'
            normalized_blocks.append(blk)

        # Save as a dict with metadata to keep structure consistent with PluginEditor
        plugin_obj = {
            "name": name,
            "author": plugin_data.get("author", ""),
            "description": plugin_data.get("description", ""),
            "blocks": normalized_blocks
        }
        local_data[name] = plugin_obj

        # Also write individual plugin file to plugins directory (download)
        try:
            plugin_file_path = os.path.join(PLUGINS_DIR, f"{name}.json")
            with open(plugin_file_path, 'w', encoding='utf-8') as pf:
                json.dump(plugin_obj, pf, indent=4, ensure_ascii=False)
        except Exception as e:
            InfoBar.error("保存失败", f"无法保存插件文件: {e}", parent=self, position=InfoBarPosition.TOP)
            return
        try:
            with open(plugins_file, 'w', encoding='utf-8') as f:
                json.dump(local_data, f, indent=4, ensure_ascii=False)
            InfoBar.success("安装成功", f"插件 [{name}] 已安装并下载到 {plugin_file_path}！", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("安装失败", f"无法保存本地配置: {e}", parent=self, position=InfoBarPosition.TOP)
