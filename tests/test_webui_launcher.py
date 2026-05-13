import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from webui_launcher import (
    APP_URL,
    WebViewBridge,
    choose_python_executable,
    ensure_frontend_build,
    frontend_dist_ready,
    frontend_npm_executable,
    preferred_webview_gui,
    python_supports_module,
    should_enable_debug_context_menu,
    should_install_frontend_dependencies,
)


class WebUiLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.mkdtemp(prefix="webui_launcher_")

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_choose_python_executable_prefers_project_venv(self):
        venv_scripts = os.path.join(self.temp_root, "venv", "Scripts")
        os.makedirs(venv_scripts, exist_ok=True)
        python_path = os.path.join(venv_scripts, "python.exe")
        with open(python_path, "w", encoding="utf-8") as handle:
            handle.write("")

        with patch("webui_launcher.python_supports_module", return_value=True):
            result = choose_python_executable(self.temp_root, "fallback-python")

        self.assertEqual(result, python_path)

    def test_choose_python_executable_falls_back_when_no_venv(self):
        result = choose_python_executable(self.temp_root, "fallback-python")

        self.assertEqual(result, "fallback-python")

    def test_python_supports_module_false_for_missing_module(self):
        self.assertFalse(python_supports_module("python", "__this_module_should_not_exist__"))

    def test_should_install_frontend_dependencies_checks_node_modules(self):
        frontend_dir = os.path.join(self.temp_root, "frontend")
        os.makedirs(frontend_dir, exist_ok=True)

        self.assertTrue(should_install_frontend_dependencies(frontend_dir))

        os.makedirs(os.path.join(frontend_dir, "node_modules"), exist_ok=True)
        self.assertFalse(should_install_frontend_dependencies(frontend_dir))

    def test_frontend_dist_ready_checks_index_file(self):
        frontend_dir = os.path.join(self.temp_root, "frontend")
        dist_dir = os.path.join(frontend_dir, "dist")
        os.makedirs(dist_dir, exist_ok=True)
        self.assertFalse(frontend_dist_ready(frontend_dir))

        with open(os.path.join(dist_dir, "index.html"), "w", encoding="utf-8") as handle:
            handle.write("<html></html>")

        self.assertTrue(frontend_dist_ready(frontend_dir))

    def test_ensure_frontend_build_skips_when_dist_exists(self):
        frontend_dir = os.path.join(self.temp_root, "frontend")
        dist_dir = os.path.join(frontend_dir, "dist")
        os.makedirs(dist_dir, exist_ok=True)
        with open(os.path.join(dist_dir, "index.html"), "w", encoding="utf-8") as handle:
            handle.write("<html></html>")

        with patch("webui_launcher.subprocess.run") as run_mock:
            ensure_frontend_build(frontend_dir)

        run_mock.assert_not_called()

    def test_frontend_npm_executable_matches_platform(self):
        expected = "npm.cmd" if os.name == "nt" else "npm"
        self.assertEqual(frontend_npm_executable(), expected)

    def test_preferred_webview_gui_matches_platform(self):
        expected = "edgechromium" if os.name == "nt" else None
        self.assertEqual(preferred_webview_gui(), expected)

    def test_should_enable_debug_context_menu_matches_platform(self):
        expected = os.name == "nt"
        self.assertEqual(should_enable_debug_context_menu(), expected)

    def test_webview_bridge_opens_db_viewer_popup_in_webview(self):
        class FakeWebview:
            def __init__(self):
                self.calls = []

            def create_window(self, *args, **kwargs):
                self.calls.append((args, kwargs))

        fake = FakeWebview()
        bridge = WebViewBridge(fake)

        result = bridge.open_popup_window("db-viewer", "C:/case/android.tar", "/data/user/0/app/demo.db")

        self.assertTrue(result["ok"])
        self.assertIn(f"{APP_URL}/?popup=db-viewer", result["url"])
        self.assertEqual(len(fake.calls), 1)


if __name__ == "__main__":
    unittest.main()
