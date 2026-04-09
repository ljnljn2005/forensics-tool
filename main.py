import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure high DPI policy before creating QApplication
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
app = QApplication(sys.argv)

from src.main_window import MainWindow

if __name__ == '__main__':
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
