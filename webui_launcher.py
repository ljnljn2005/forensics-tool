import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_URL = "http://127.0.0.1:8000/api/health"
APP_URL = "http://127.0.0.1:8000"
POPUP_WINDOW_SIZE = (1280, 900)


def python_supports_module(python_executable: str, module_name: str) -> bool:
    try:
        probe = subprocess.run(
            [python_executable, "-c", f"import {module_name}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return probe.returncode == 0


def choose_python_executable(project_root: str, fallback: str) -> str:
    venv_python = os.path.join(project_root, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python) and python_supports_module(venv_python, "uvicorn"):
        return venv_python
    return fallback


def frontend_npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def should_install_frontend_dependencies(frontend_dir: str) -> bool:
    return not os.path.isdir(os.path.join(frontend_dir, "node_modules"))


def frontend_dist_ready(frontend_dir: str) -> bool:
    return os.path.isfile(os.path.join(frontend_dir, "dist", "index.html"))


def ensure_frontend_build(frontend_dir: str):
    if frontend_dist_ready(frontend_dir):
        return

    npm_executable = frontend_npm_executable()
    if should_install_frontend_dependencies(frontend_dir):
        print("未检测到前端依赖，正在自动安装...")
        install = subprocess.run(
            [npm_executable, "install", "--cache", ".npm-cache"],
            cwd=frontend_dir,
            check=False,
        )
        if install.returncode != 0:
            raise RuntimeError("前端依赖安装失败，请手动检查 npm install 输出。")

    print("正在构建内置 WebUI 资源...")
    build = subprocess.run(
        [npm_executable, "run", "build"],
        cwd=frontend_dir,
        check=False,
    )
    if build.returncode != 0 or not frontend_dist_ready(frontend_dir):
        raise RuntimeError("前端资源构建失败，请手动检查 npm run build 输出。")


def wait_for_http(url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def preferred_webview_gui() -> str | None:
    if os.name == "nt":
        return "edgechromium"
    return None


def should_enable_debug_context_menu() -> bool:
    return os.name == "nt"


def import_webview_module():
    try:
        import webview  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("缺少 pywebview 依赖，请先运行 `pip install -r requirements.txt`。") from exc
    return webview


class WebViewBridge:
    def __init__(self, webview_module):
        self._webview = webview_module

    def open_popup_window(self, popup: str, mapping_path: str = "", database_path: str = "") -> dict:
        popup = str(popup or "").strip()
        if popup != "db-viewer":
            return {"ok": False, "message": "unsupported popup"}

        query = urllib.parse.urlencode(
            {
                "popup": popup,
                "mappingPath": mapping_path or "",
                "databasePath": database_path or "",
            }
        )
        target_url = f"{APP_URL}/?{query}"
        self._webview.create_window(
            "数据库查看器",
            target_url,
            width=POPUP_WINDOW_SIZE[0],
            height=POPUP_WINDOW_SIZE[1],
            min_size=(960, 640),
            text_select=True,
        )
        return {"ok": True, "url": target_url}


class BackendServer:
    def __init__(self):
        from backend.app.main import app

        self._owns_server = False
        self._config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(self._config)
        self._thread = threading.Thread(target=self._server.run, name="forensics-webui-backend", daemon=True)

    def start(self):
        if self._thread.is_alive():
            return
        if _port_is_open("127.0.0.1", 8000):
            if wait_for_http(BACKEND_URL, timeout_seconds=1):
                self._owns_server = False
                return
            raise RuntimeError("127.0.0.1:8000 已被其他程序占用，无法启动内置 WebUI 后端。")
        self._owns_server = True
        self._thread.start()

    def wait_until_ready(self, timeout_seconds: float = 20) -> bool:
        return wait_for_http(BACKEND_URL, timeout_seconds)

    def stop(self):
        if not self._owns_server:
            return
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=5)


def launch_webui() -> int:
    webview = import_webview_module()
    ensure_frontend_build(str(FRONTEND_DIR))

    server = BackendServer()
    server.start()
    if not server.wait_until_ready():
        server.stop()
        raise RuntimeError("后端服务启动超时。")

    gui_name = preferred_webview_gui()
    bridge = WebViewBridge(webview)
    webview.create_window(
        "综合取证分析工具 - WebUI",
        APP_URL,
        width=1440,
        height=960,
        min_size=(1100, 720),
        text_select=True,
        js_api=bridge,
    )

    try:
        webview.start(gui=gui_name, debug=should_enable_debug_context_menu())
    finally:
        server.stop()

    return 0


if __name__ == "__main__":
    sys.exit(launch_webui())
