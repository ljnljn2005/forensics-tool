import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure high DPI policy before creating QApplication
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
app = QApplication(sys.argv)

try:
    from src.main_window import MainWindow
except Exception:
    import traceback
    traceback.print_exc()
    print("导入 MainWindow 失败，请检查依赖和模块路径。")
    sys.exit(1)

if __name__ == '__main__':
    try:
        w = MainWindow()
        w.show()
        sys.exit(app.exec())
    except Exception:
        import traceback
        traceback.print_exc()
        print("启动窗口失败，请检查日志。")
        sys.exit(1)
