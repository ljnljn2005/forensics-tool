import paramiko
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    NavigationItemPosition,
    PushButton,
    SubtitleLabel,
    Theme,
    setTheme,
)

from .ai_interface import AiInterface
from .constants import get_app_proxy, get_app_settings, save_app_settings
from .extractor import ExtractorInterface
from .live_ssh import LiveSshInterface
from .log_analysis import LogAnalysisInterface
from .local_terminal import LocalTerminalInterface
from .market import PluginMarketInterface
from .memory_forensics import MemoryForensicsInterface
from .plugin_editor import PluginEditorInterface
from .registry_interface import RegistryScanInterface
from .search_interface import SearchInterface


class HomeWidget(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel("欢迎使用综合取证分析工具", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignCenter)

        mapLayout = QHBoxLayout()
        self.mapLabel = BodyLabel("映射路径（用于离线提取）:", self)
        self.mapPathEdit = LineEdit(self)
        self.mapPathEdit.setPlaceholderText("例如: D:/mnt/image")
        self.mapSaveBtn = PushButton("保存映射路径", self)
        mapLayout.addWidget(self.mapLabel)
        mapLayout.addWidget(self.mapPathEdit, 1)
        mapLayout.addWidget(self.mapSaveBtn)
        self.vBoxLayout.addLayout(mapLayout)

        sshLayout = QHBoxLayout()
        self.sshHost = LineEdit(self)
        self.sshHost.setPlaceholderText("SSH 主机 IP")
        self.sshPort = LineEdit(self)
        self.sshPort.setPlaceholderText("端口")
        self.sshPort.setFixedWidth(80)
        self.sshUser = LineEdit(self)
        self.sshUser.setPlaceholderText("用户名")
        self.sshPass = LineEdit(self)
        self.sshPass.setPlaceholderText("密码")
        self.sshSaveBtn = PushButton("保存 SSH 配置", self)
        sshLayout.addWidget(self.sshHost)
        sshLayout.addWidget(self.sshPort)
        sshLayout.addWidget(self.sshUser)
        sshLayout.addWidget(self.sshPass)
        sshLayout.addWidget(self.sshSaveBtn)
        self.vBoxLayout.addLayout(sshLayout)

        self.mapSaveBtn.clicked.connect(self.save_mapping)
        self.sshSaveBtn.clicked.connect(self.save_ssh)

        self.sshTestBtn = PushButton("测试连接", self)
        sshLayout.addWidget(self.sshTestBtn)
        self.sshTestBtn.clicked.connect(self.test_ssh)

        try:
            if parent is not None:
                parent.mapping_path = ""
                parent.ssh_info = {}
        except Exception:
            pass

        try:
            app_conf = get_app_settings()
            mapping_path = app_conf.get("mapping_path", "")
            if mapping_path:
                self.mapPathEdit.setText(mapping_path)
                if parent is not None:
                    parent.mapping_path = mapping_path

            ssh = app_conf.get("ssh", {})
            if ssh:
                self.sshHost.setText(ssh.get("host", ""))
                self.sshPort.setText(str(ssh.get("port", "")))
                self.sshUser.setText(ssh.get("user", ""))
                self.sshPass.setText(ssh.get("password", ""))
                if parent is not None:
                    parent.ssh_info = ssh
        except Exception:
            pass

    def save_mapping(self):
        value = self.mapPathEdit.text().strip()
        if not value:
            InfoBar.info("提示", "请输入映射路径后再保存。", parent=self)
            return
        try:
            main_window = self.parent()
            if main_window is not None:
                main_window.mapping_path = value
            save_app_settings({"mapping_path": value})
            InfoBar.success("已保存", "映射路径已写入本地配置。", parent=self, position=InfoBarPosition.TOP)
        except Exception as exc:
            InfoBar.error("保存失败", str(exc), parent=self, position=InfoBarPosition.TOP)

    def save_ssh(self):
        host = self.sshHost.text().strip()
        port = self.sshPort.text().strip()
        user = self.sshUser.text().strip()
        password = self.sshPass.text()
        if not host or not user:
            InfoBar.info("提示", "请至少填写主机和用户名。", parent=self)
            return
        try:
            config = {"host": host, "port": int(port) if port else 22, "user": user, "password": password}
            main_window = self.parent()
            if main_window is not None:
                main_window.ssh_info = config
            save_app_settings({"ssh": config})
            InfoBar.success("已保存", "SSH 配置已写入本地配置。", parent=self, position=InfoBarPosition.TOP)
        except Exception as exc:
            InfoBar.error("保存失败", str(exc), parent=self, position=InfoBarPosition.TOP)

    def test_ssh(self):
        host = self.sshHost.text().strip()
        port = self.sshPort.text().strip() or "22"
        user = self.sshUser.text().strip()
        password = self.sshPass.text()
        if not host or not user:
            InfoBar.info("提示", "请先填写主机和用户名。", parent=self)
            return
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, port=int(port), username=user, password=password, timeout=6)
            client.close()
            config = {"host": host, "port": int(port), "user": user, "password": password}
            main_window = self.parent()
            if main_window is not None:
                main_window.ssh_info = config
            save_app_settings({"ssh": config})
            InfoBar.success("连接成功", "SSH 连接测试成功，配置已保存。", parent=self, position=InfoBarPosition.TOP)
        except Exception as exc:
            InfoBar.error("连接失败", str(exc), parent=self, position=InfoBarPosition.TOP)


class SettingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("settingInterface")
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
        self.proxyLabel = BodyLabel("网络代理（用于市场和 GitHub 下载）:", self)
        self.proxyEdit = LineEdit(self)
        self.proxyEdit.setPlaceholderText("例如: http://127.0.0.1:7897")
        self.proxyEdit.setFixedWidth(300)
        self.proxyEdit.setText(get_app_proxy())
        self.proxyLayout.addWidget(self.proxyLabel)
        self.proxyLayout.addWidget(self.proxyEdit)
        self.proxyLayout.addStretch(1)
        self.vBoxLayout.addLayout(self.proxyLayout)

        self.aiLayout = QHBoxLayout()
        self.aiUrlLabel = BodyLabel("OpenAI API URL:", self)
        self.apiUrlEdit = LineEdit(self)
        self.apiUrlEdit.setPlaceholderText("例如: https://api.openai.com/v1/chat/completions")
        self.apiUrlEdit.setFixedWidth(420)
        self.aiLayout.addWidget(self.aiUrlLabel)
        self.aiLayout.addWidget(self.apiUrlEdit)
        self.vBoxLayout.addLayout(self.aiLayout)

        self.aiCredLayout = QHBoxLayout()
        self.aiKeyLabel = BodyLabel("API Key:", self)
        self.apiKeyEdit = LineEdit(self)
        self.apiKeyEdit.setPlaceholderText("输入 API Key（保存在本地配置文件）")
        self.apiKeyEdit.setFixedWidth(360)
        try:
            from PySide6.QtWidgets import QLineEdit

            self.apiKeyEdit.setEchoMode(QLineEdit.Password)
        except Exception:
            pass
        self.modelLabel = BodyLabel("模型:", self)
        self.modelEdit = LineEdit(self)
        self.modelEdit.setPlaceholderText("例如: gpt-4o-mini")
        self.modelEdit.setFixedWidth(180)
        self.aiCredLayout.addWidget(self.aiKeyLabel)
        self.aiCredLayout.addWidget(self.apiKeyEdit, 1)
        self.aiCredLayout.addWidget(self.modelLabel)
        self.aiCredLayout.addWidget(self.modelEdit)
        self.vBoxLayout.addLayout(self.aiCredLayout)

        self.marketLayout = QHBoxLayout()
        self.marketLabel = BodyLabel("插件市场仓库 URL:", self)
        self.marketRepoEdit = LineEdit(self)
        self.marketRepoEdit.setPlaceholderText("例如: https://github.com/your/repo.git")
        self.marketRepoEdit.setFixedWidth(520)
        self.marketLayout.addWidget(self.marketLabel)
        self.marketLayout.addWidget(self.marketRepoEdit)
        self.vBoxLayout.addLayout(self.marketLayout)

        self.saveBtn = PushButton("保存设置", self)
        self.saveBtn.clicked.connect(self.save_settings)
        self.vBoxLayout.addWidget(self.saveBtn)
        self.vBoxLayout.addStretch(1)

        app_conf = get_app_settings()
        self.apiUrlEdit.setText(app_conf.get("api_url", ""))
        self.apiKeyEdit.setText(app_conf.get("api_key", ""))
        self.modelEdit.setText(app_conf.get("model", ""))
        self.marketRepoEdit.setText(app_conf.get("market_repo", ""))

    def save_settings(self):
        from .constants import save_app_proxy

        proxy = self.proxyEdit.text().strip()
        save_app_proxy(proxy)
        config = {
            "api_url": self.apiUrlEdit.text().strip(),
            "api_key": self.apiKeyEdit.text().strip(),
            "model": self.modelEdit.text().strip(),
            "market_repo": self.marketRepoEdit.text().strip(),
        }
        save_app_settings(config)
        InfoBar.success("保存成功", "设置已保存到本地。", parent=self, position=InfoBarPosition.TOP)


class SystemCategoryWidget(QWidget):
    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent=parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(24, 24, 24, 24)
        self.vBoxLayout.setSpacing(12)

        self.titleLabel = SubtitleLabel(title, self)
        self.bodyLabel = BodyLabel(description, self)
        self.bodyLabel.setWordWrap(True)

        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addWidget(self.bodyLabel)
        self.vBoxLayout.addStretch(1)


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.AUTO)

        self.homeInterface = HomeWidget("主页", self)
        self.homeInterface.setObjectName("homeInterface")

        self.windowsCategoryInterface = SystemCategoryWidget(
            "Windows 取证分析",
            "聚合 Windows 本地取证与注册表取证入口。",
            self,
        )
        self.windowsCategoryInterface.setObjectName("windowsCategoryInterface")
        self.windowsLocalForensicsInterface = ExtractorInterface(self, initial_module="windows", show_module_bar=False)
        self.windowsLocalForensicsInterface.setObjectName("windowsLocalForensicsInterface")
        self.windowsMemoryForensicsInterface = MemoryForensicsInterface(self, module="windows")
        self.windowsMemoryForensicsInterface.setObjectName("windowsMemoryForensicsInterface")
        self.windowsLogAnalysisInterface = LogAnalysisInterface(self, module="windows")
        self.windowsLogAnalysisInterface.setObjectName("windowsLogAnalysisInterface")

        self.linuxCategoryInterface = SystemCategoryWidget(
            "Linux 取证分析",
            "聚合 Linux 本地取证与 SSH 远程取证入口。",
            self,
        )
        self.linuxCategoryInterface.setObjectName("linuxCategoryInterface")
        self.linuxLocalForensicsInterface = ExtractorInterface(self, initial_module="linux", show_module_bar=False)
        self.linuxLocalForensicsInterface.setObjectName("linuxLocalForensicsInterface")
        self.linuxMemoryForensicsInterface = MemoryForensicsInterface(self, module="linux")
        self.linuxMemoryForensicsInterface.setObjectName("linuxMemoryForensicsInterface")
        self.linuxLogAnalysisInterface = LogAnalysisInterface(self, module="linux")
        self.linuxLogAnalysisInterface.setObjectName("linuxLogAnalysisInterface")

        self.androidCategoryInterface = SystemCategoryWidget(
            "Android 取证分析",
            "聚合 Android 本地取证入口。",
            self,
        )
        self.androidCategoryInterface.setObjectName("androidCategoryInterface")
        self.androidLocalForensicsInterface = ExtractorInterface(self, initial_module="android", show_module_bar=False)
        self.androidLocalForensicsInterface.setObjectName("androidLocalForensicsInterface")
        self.androidAutoForensicsInterface = ExtractorInterface(
            self,
            initial_module="android",
            show_module_bar=False,
            auto_analyze_mode=True,
        )
        self.androidAutoForensicsInterface.setObjectName("androidAutoForensicsInterface")

        self.iosCategoryInterface = SystemCategoryWidget(
            "iOS 取证分析",
            "聚合 iOS 本地取证入口。",
            self,
        )
        self.iosCategoryInterface.setObjectName("iosCategoryInterface")
        self.iosLocalForensicsInterface = ExtractorInterface(self, initial_module="ios", show_module_bar=False)
        self.iosLocalForensicsInterface.setObjectName("iosLocalForensicsInterface")

        self.liveSshInterface = LiveSshInterface(self)
        self.liveSshInterface.setObjectName("liveSshInterface")
        self.pluginEditorInterface = PluginEditorInterface(self)
        self.pluginEditorInterface.setObjectName("pluginEditorInterface")
        self.pluginMarketInterface = PluginMarketInterface(self)
        self.pluginMarketInterface.setObjectName("pluginMarketInterface")
        self.searchInterface = SearchInterface(self)
        self.searchInterface.setObjectName("searchInterface")
        self.aiInterface = AiInterface(self)
        self.aiInterface.setObjectName("aiInterface")
        self.localTerminalInterface = LocalTerminalInterface(self)
        self.localTerminalInterface.setObjectName("localTerminalInterface")
        self.registryScanInterface = RegistryScanInterface(self)
        self.registryScanInterface.setObjectName("registryScanInterface")
        self.settingInterface = SettingInterface(self)
        self.settingInterface.setObjectName("settingInterface")

        # backward-compatible aliases used by search and SSH jump logic
        self.extractorInterface = self.linuxLocalForensicsInterface

        self.initNavigation()
        self.initWindow()

        try:
            self.liveSshInterface.try_auto_connect()
        except Exception:
            pass

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FluentIcon.HOME, "主页")
        self.navigationInterface.addSeparator()

        self.addSubInterface(self.windowsCategoryInterface, FluentIcon.APPLICATION, "Windows 取证分析")
        self.addSubInterface(
            self.windowsLocalForensicsInterface,
            FluentIcon.FOLDER,
            "本地取证",
            parent=self.windowsCategoryInterface,
        )
        self.addSubInterface(
            self.registryScanInterface,
            FluentIcon.SEARCH,
            "注册表取证",
            parent=self.windowsCategoryInterface,
        )
        self.addSubInterface(
            self.windowsMemoryForensicsInterface,
            FluentIcon.DOCUMENT,
            "内存取证",
            parent=self.windowsCategoryInterface,
        )
        self.addSubInterface(
            self.windowsLogAnalysisInterface,
            FluentIcon.FILTER,
            "日志分析",
            parent=self.windowsCategoryInterface,
        )

        self.addSubInterface(self.linuxCategoryInterface, FluentIcon.GLOBE, "Linux 取证分析")
        self.addSubInterface(
            self.linuxLocalForensicsInterface,
            FluentIcon.FOLDER,
            "本地取证",
            parent=self.linuxCategoryInterface,
        )
        self.addSubInterface(
            self.liveSshInterface,
            FluentIcon.IOT,
            "SSH 远程取证",
            parent=self.linuxCategoryInterface,
        )
        self.addSubInterface(
            self.linuxMemoryForensicsInterface,
            FluentIcon.DOCUMENT,
            "内存取证",
            parent=self.linuxCategoryInterface,
        )
        self.addSubInterface(
            self.linuxLogAnalysisInterface,
            FluentIcon.FILTER,
            "日志分析",
            parent=self.linuxCategoryInterface,
        )

        self.addSubInterface(self.androidCategoryInterface, FluentIcon.APPLICATION, "Android 取证分析")
        self.addSubInterface(
            self.androidLocalForensicsInterface,
            FluentIcon.FOLDER,
            "本地取证",
            parent=self.androidCategoryInterface,
        )
        self.addSubInterface(
            self.androidAutoForensicsInterface,
            FluentIcon.SEARCH,
            "自动取证",
            parent=self.androidCategoryInterface,
        )

        self.addSubInterface(self.iosCategoryInterface, FluentIcon.PHONE, "IOS 取证分析")
        self.addSubInterface(
            self.iosLocalForensicsInterface,
            FluentIcon.FOLDER,
            "本地取证",
            parent=self.iosCategoryInterface,
        )

        self.navigationInterface.addSeparator()
        self.addSubInterface(self.searchInterface, FluentIcon.SEARCH, "全局搜索")
        self.addSubInterface(self.aiInterface, FluentIcon.ROBOT, "AI 分析")
        self.addSubInterface(self.pluginMarketInterface, FluentIcon.MARKET, "插件市场")
        self.addSubInterface(self.pluginEditorInterface, FluentIcon.EDIT, "插件制作编辑")

        self.navigationInterface.addSeparator(NavigationItemPosition.BOTTOM)
        self.addSubInterface(
            self.settingInterface,
            FluentIcon.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM,
        )

    def initWindow(self):
        self.resize(980, 720)
        self.setWindowTitle("综合取证分析工具")
        desktop = QApplication.primaryScreen().availableGeometry()
        width, height = desktop.width(), desktop.height()
        self.move(width // 2 - self.width() // 2, height // 2 - self.height() // 2)
