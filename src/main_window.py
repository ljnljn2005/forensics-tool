from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QApplication
from PySide6.QtCore import Qt
from qfluentwidgets import FluentWindow, FluentIcon, setTheme, Theme, SubtitleLabel, BodyLabel, LineEdit, PushButton, ComboBox, InfoBar, InfoBarPosition
from .extractor import ExtractorInterface
from .live_ssh import LiveSshInterface
from .plugin_editor import PluginEditorInterface
from .market import PluginMarketInterface
from .search_interface import SearchInterface
from .widgets import SearchableTextEdit
from .ai_interface import AiInterface
from .constants import get_app_proxy, get_app_settings, save_app_settings
import paramiko


class HomeWidget(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel("欢迎使用综合取证分析工具", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignCenter)

        # Mapping path (for Extractor)
        mapLayout = QHBoxLayout()
        self.mapLabel = BodyLabel('映射路径 (用于离线提取):', self)
        self.mapPathEdit = LineEdit(self)
        self.mapPathEdit.setPlaceholderText('例如: D:/mnt/image')
        self.mapSaveBtn = PushButton('保存映射路径', self)
        mapLayout.addWidget(self.mapLabel)
        mapLayout.addWidget(self.mapPathEdit, 1)
        mapLayout.addWidget(self.mapSaveBtn)
        self.vBoxLayout.addLayout(mapLayout)

        # SSH connection (for Live SSH)
        sshLayout = QHBoxLayout()
        self.sshHost = LineEdit(self)
        self.sshHost.setPlaceholderText('SSH 主机 IP')
        self.sshPort = LineEdit(self)
        self.sshPort.setPlaceholderText('端口')
        self.sshPort.setFixedWidth(80)
        self.sshUser = LineEdit(self)
        self.sshUser.setPlaceholderText('用户名')
        self.sshPass = LineEdit(self)
        self.sshPass.setPlaceholderText('密码')
        self.sshSaveBtn = PushButton('保存 SSH 配置', self)
        sshLayout.addWidget(self.sshHost)
        sshLayout.addWidget(self.sshPort)
        sshLayout.addWidget(self.sshUser)
        sshLayout.addWidget(self.sshPass)
        sshLayout.addWidget(self.sshSaveBtn)
        self.vBoxLayout.addLayout(sshLayout)

        # bind actions
        self.mapSaveBtn.clicked.connect(self.save_mapping)
        self.sshSaveBtn.clicked.connect(self.save_ssh)

        # Test connection button
        self.sshTestBtn = PushButton('检测连接', self)
        sshLayout.addWidget(self.sshTestBtn)
        self.sshTestBtn.clicked.connect(self.test_ssh)

        # initialize storage on parent (MainWindow)
        try:
            mw = parent
            if mw is not None:
                mw.mapping_path = ''
                mw.ssh_info = {}
        except Exception:
            pass

        # load saved settings
        try:
            app_conf = get_app_settings()
            mp = app_conf.get('mapping_path', '')
            if mp:
                self.mapPathEdit.setText(mp)
                mw = parent
                if mw is not None:
                    mw.mapping_path = mp
            ssh = app_conf.get('ssh', {})
            if ssh:
                self.sshHost.setText(ssh.get('host', ''))
                self.sshPort.setText(str(ssh.get('port', '')))
                self.sshUser.setText(ssh.get('user', ''))
                self.sshPass.setText(ssh.get('password', ''))
                mw = parent
                if mw is not None:
                    mw.ssh_info = ssh
        except Exception:
            pass

    def save_mapping(self):
        val = self.mapPathEdit.text().strip()
        if not val:
            InfoBar.info('提示', '请输入映射路径后保存。', parent=self)
            return
        try:
            mw = self.parent()
            if mw is not None:
                mw.mapping_path = val
            # persist
            save_app_settings({'mapping_path': val})
            InfoBar.success('已保存', '映射路径已保存到主页并写入配置。', parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error('保存失败', str(e), parent=self, position=InfoBarPosition.TOP)

    def save_ssh(self):
        host = self.sshHost.text().strip()
        port = self.sshPort.text().strip()
        user = self.sshUser.text().strip()
        pwd = self.sshPass.text()
        if not host or not user:
            InfoBar.info('提示', '请至少填写主机和用户名。', parent=self)
            return
        try:
            mw = self.parent()
            if mw is not None:
                conf = {'host': host, 'port': int(port) if port else 22, 'user': user, 'password': pwd}
                mw.ssh_info = conf
                save_app_settings({'ssh': conf})
            InfoBar.success('已保存', 'SSH 配置已保存到主页并写入配置。', parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error('保存失败', str(e), parent=self, position=InfoBarPosition.TOP)

    def test_ssh(self):
        host = self.sshHost.text().strip()
        port = self.sshPort.text().strip() or '22'
        user = self.sshUser.text().strip()
        pwd = self.sshPass.text()
        if not host or not user:
            InfoBar.info('提示', '请先填写主机和用户名。', parent=self)
            return
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, port=int(port), username=user, password=pwd, timeout=6)
            client.close()
            # on success, save and update parent
            conf = {'host': host, 'port': int(port), 'user': user, 'password': pwd}
            mw = self.parent()
            if mw is not None:
                mw.ssh_info = conf
            save_app_settings({'ssh': conf})
            InfoBar.success('连接成功', 'SSH 连接测试成功，配置已保存。', parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error('连接失败', str(e), parent=self, position=InfoBarPosition.TOP)


class SettingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('settingInterface')
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(16)
        self.titleLabel = SubtitleLabel("设置", self)
        self.vBoxLayout.addWidget(self.titleLabel)

        self.themeLayout = QHBoxLayout()
        self.themeLabel = BodyLabel("应用主题:", self)
        self.themeComboBox = ComboBox(self)
        self.themeComboBox.addItems(["跟随系统", "浅色模式 (Light)", "深色模式 (Dark)"])
        self.themeLayout.addWidget(self.themeLabel)
        self.themeLayout.addWidget(self.themeComboBox)
        self.themeLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.themeLayout)

        self.proxyLayout = QHBoxLayout()
        self.proxyLabel = BodyLabel("网络代理 (用于市场和GitHub下载):", self)
        self.proxyEdit = LineEdit(self)
        self.proxyEdit.setPlaceholderText("例如: http://127.0.0.1:7897 (留空则不使用代理)")
        self.proxyEdit.setFixedWidth(300)
        self.proxyEdit.setText(get_app_proxy())
        self.proxyLayout.addWidget(self.proxyLabel)
        self.proxyLayout.addWidget(self.proxyEdit)
        self.proxyLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.proxyLayout)
        # OpenAI compatible API settings
        self.aiLayout = QHBoxLayout()
        self.aiUrlLabel = BodyLabel("OpenAI API URL:", self)
        self.apiUrlEdit = LineEdit(self)
        self.apiUrlEdit.setPlaceholderText("例如: https://api.openai.com/v1/chat/completions 或 自托管 URL")
        self.apiUrlEdit.setFixedWidth(420)
        self.aiLayout.addWidget(self.aiUrlLabel)
        self.aiLayout.addWidget(self.apiUrlEdit)
        self.vBoxLayout.addLayout(self.aiLayout)

        self.aiCredLayout = QHBoxLayout()
        self.aiKeyLabel = BodyLabel("API Key:", self)
        self.apiKeyEdit = LineEdit(self)
        self.apiKeyEdit.setPlaceholderText("输入 API Key (保存在本地配置文件)")
        self.apiKeyEdit.setFixedWidth(360)
        self.modelLabel = BodyLabel("模型:", self)
        self.modelEdit = LineEdit(self)
        self.modelEdit.setPlaceholderText("例如: gpt-4o-mini 或 gpt-3.5-turbo")
        self.modelEdit.setFixedWidth(180)
        self.aiCredLayout.addWidget(self.aiKeyLabel)
        self.aiCredLayout.addWidget(self.apiKeyEdit, 1)
        self.aiCredLayout.addWidget(self.modelLabel)
        self.aiCredLayout.addWidget(self.modelEdit)
        self.vBoxLayout.addLayout(self.aiCredLayout)
        # Market repo URL
        self.marketLayout = QHBoxLayout()
        self.marketLabel = BodyLabel("插件市场仓库 URL:", self)
        self.marketRepoEdit = LineEdit(self)
        self.marketRepoEdit.setPlaceholderText("例如: https://github.com/your/repo.git 或 GitHub API URL")
        self.marketRepoEdit.setFixedWidth(520)
        self.marketLayout.addWidget(self.marketLabel)
        self.marketLayout.addWidget(self.marketRepoEdit)
        self.vBoxLayout.addLayout(self.marketLayout)
        self.saveBtn = PushButton("保存设置", self)
        self.vBoxLayout.addWidget(self.saveBtn)
        self.vBoxLayout.addStretch(1)
        # load saved settings
        from .constants import get_app_settings
        app_conf = get_app_settings()
        self.apiUrlEdit.setText(app_conf.get('api_url', ''))
        self.apiKeyEdit.setText(app_conf.get('api_key', ''))
        self.modelEdit.setText(app_conf.get('model', ''))
        self.marketRepoEdit.setText(app_conf.get('market_repo', ''))

    def save_settings(self):
        from .constants import save_app_proxy, save_app_settings
        proxy = self.proxyEdit.text().strip()
        save_app_proxy(proxy)
        ai_cfg = {
            'api_url': self.apiUrlEdit.text().strip(),
            'api_key': self.apiKeyEdit.text().strip(),
            'model': self.modelEdit.text().strip()
        }
        # include market repo setting
        ai_cfg.update({'market_repo': self.marketRepoEdit.text().strip()})
        save_app_settings(ai_cfg)
        InfoBar.success('保存成功', '设置已保存到本地。', parent=self, position=InfoBarPosition.TOP)


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.AUTO)

        self.homeInterface = HomeWidget('主页', self)
        self.homeInterface.setObjectName('homeInterface')
        self.extractorInterface = ExtractorInterface(self)
        self.extractorInterface.setObjectName('extractorInterface')
        self.liveSshInterface = LiveSshInterface(self)
        self.liveSshInterface.setObjectName('liveSshInterface')
        self.pluginEditorInterface = PluginEditorInterface(self)
        self.pluginEditorInterface.setObjectName('pluginEditorInterface')
        self.pluginMarketInterface = PluginMarketInterface(self)
        self.pluginMarketInterface.setObjectName('pluginMarketInterface')
        self.searchInterface = SearchInterface(self)
        self.searchInterface.setObjectName('searchInterface')
        self.aiInterface = AiInterface(self)
        self.aiInterface.setObjectName('aiInterface')
        self.settingInterface = SettingInterface(self)
        self.settingInterface.setObjectName('settingInterface')

        self.initNavigation()
        self.initWindow()
        # attempt auto SSH connect on startup using saved settings
        try:
            if hasattr(self, 'liveSshInterface'):
                try:
                    self.liveSshInterface.try_auto_connect()
                except Exception:
                    pass
        except Exception:
            pass

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FluentIcon.HOME, '主页')
        self.addSubInterface(self.extractorInterface, FluentIcon.DOCUMENT, '离线取证 (提取盘)')
        self.addSubInterface(self.liveSshInterface, FluentIcon.GLOBE, '动态取证 (SSH)')
        self.addSubInterface(self.pluginEditorInterface, FluentIcon.CALENDAR, '提取插件编辑')
        self.addSubInterface(self.pluginMarketInterface, FluentIcon.MARKET, '插件市场')
        self.addSubInterface(self.searchInterface, FluentIcon.SEARCH, '全局搜索')
        self.addSubInterface(self.aiInterface, FluentIcon.SEARCH, 'AI 分析')
        self.addSubInterface(self.settingInterface, FluentIcon.SETTING, '设置')

    def initWindow(self):
        self.resize(900, 700)
        self.setWindowTitle('综合取证分析工具')
        desktop = QApplication.primaryScreen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
