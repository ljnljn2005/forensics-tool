import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app


class McpServerApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("backend.app.api.routes.mcp_server.read_mcp_settings")
    def test_get_settings(self, read_mock):
        read_mock.return_value = {
            "settings": {"enabled": False, "transport": "stdio"},
            "tool_groups": [],
            "status": {"implemented_groups": [], "server_module": "mcp_server.server", "running": False},
        }

        response = self.client.get("/api/mcp/settings")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["settings"]["transport"], "stdio")

    @patch("backend.app.api.routes.mcp_server.update_mcp_settings")
    def test_post_settings(self, update_mock):
        update_mock.return_value = {
            "settings": {"enabled": True, "transport": "http", "port": 8800},
            "tool_groups": [],
            "status": {"implemented_groups": ["cases"], "server_module": "mcp_server.server", "running": False},
        }

        response = self.client.post(
            "/api/mcp/settings",
            json={"enabled": True, "transport": "http", "port": 8800},
        )

        self.assertEqual(response.status_code, 200)
        update_mock.assert_called_once()
        self.assertEqual(response.json()["settings"]["port"], 8800)

    @patch("backend.app.api.routes.mcp_server.export_mcp_client_config")
    def test_get_export(self, export_mock):
        export_mock.return_value = {
            "server_name": "forensics-tool",
            "transport": "stdio",
            "python_executable": "python",
            "project_root": "D:/Coding/forensicstool",
            "module": "mcp_server.server",
            "http_url": "http://127.0.0.1:8765/mcp",
            "active_json": "{}",
            "stdio_json": "{}",
            "http_json": "{}",
            "notes": [],
        }

        response = self.client.get("/api/mcp/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["server_name"], "forensics-tool")


if __name__ == "__main__":
    unittest.main()
