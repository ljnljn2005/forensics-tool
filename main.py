import sys

from webui_launcher import launch_webui


def show_startup_error(message: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Forensics Tool 启动失败", 0x10)
    except Exception:
        return


if __name__ == "__main__":
    try:
        sys.exit(launch_webui())
    except Exception as exc:
        import traceback

        traceback.print_exc()
        print("WebUI 启动失败，请检查日志。")
        show_startup_error(f"{exc}\n\n如需激活码，请联系作者并提供上方机器码。")
        sys.exit(1)
