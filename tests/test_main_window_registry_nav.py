import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.memory_forensics import MemoryForensicsInterface
from src.log_analysis import LogAnalysisInterface
from src.main_window import MainWindow
from src.registry_interface import RegistryScanInterface


class MainWindowRegistryNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_has_registry_scan_interface(self):
        window = MainWindow()

        self.assertIsInstance(window.registryScanInterface, RegistryScanInterface)
        self.assertEqual(window.registryScanInterface.objectName(), "registryScanInterface")
        self.assertEqual(window.homeInterface.objectName(), "homeInterface")

    def test_main_window_organizes_system_categories_and_settings_aliases(self):
        window = MainWindow()

        self.assertEqual(window.windowsCategoryInterface.objectName(), "windowsCategoryInterface")
        self.assertEqual(window.linuxCategoryInterface.objectName(), "linuxCategoryInterface")
        self.assertEqual(window.androidCategoryInterface.objectName(), "androidCategoryInterface")
        self.assertEqual(window.iosCategoryInterface.objectName(), "iosCategoryInterface")
        self.assertEqual(window.windowsLocalForensicsInterface.current_module, "windows")
        self.assertEqual(window.linuxLocalForensicsInterface.current_module, "linux")
        self.assertEqual(window.androidLocalForensicsInterface.current_module, "android")
        self.assertEqual(window.androidAutoForensicsInterface.current_module, "android")
        self.assertTrue(window.androidAutoForensicsInterface.auto_analyze_mode)
        self.assertEqual(window.iosLocalForensicsInterface.current_module, "ios")
        self.assertIs(window.extractorInterface, window.linuxLocalForensicsInterface)
        self.assertEqual(window.settingInterface.objectName(), "settingInterface")

    def test_main_window_has_windows_and_linux_log_analysis_interfaces(self):
        window = MainWindow()

        self.assertIsInstance(window.windowsLogAnalysisInterface, LogAnalysisInterface)
        self.assertIsInstance(window.linuxLogAnalysisInterface, LogAnalysisInterface)
        self.assertEqual(window.windowsLogAnalysisInterface.module, "windows")
        self.assertEqual(window.linuxLogAnalysisInterface.module, "linux")

    def test_main_window_has_windows_and_linux_memory_forensics_interfaces(self):
        window = MainWindow()

        self.assertIsInstance(window.windowsMemoryForensicsInterface, MemoryForensicsInterface)
        self.assertIsInstance(window.linuxMemoryForensicsInterface, MemoryForensicsInterface)
        self.assertEqual(window.windowsMemoryForensicsInterface.module, "windows")
        self.assertEqual(window.linuxMemoryForensicsInterface.module, "linux")


if __name__ == "__main__":
    unittest.main()
