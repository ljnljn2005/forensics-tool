import sys

from webui_launcher import launch_webui


if __name__ == "__main__":
    try:
        sys.exit(launch_webui())
    except Exception:
        import traceback

        traceback.print_exc()
        print("WebUI 启动失败，请检查日志。")
        sys.exit(1)
