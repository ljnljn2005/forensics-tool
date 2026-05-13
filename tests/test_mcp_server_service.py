import unittest
from unittest.mock import patch

from backend.app.services.mcp_server import (
    DEFAULT_MCP_SETTINGS,
    MCP_TOOL_GROUPS,
    _normalize_mcp_settings,
    export_mcp_client_config,
    read_mcp_settings,
    update_mcp_settings,
)


class McpServerServiceTests(unittest.TestCase):
    def test_normalize_settings_filters_unknown_groups_and_invalid_port(self):
        payload = {
            "enabled": True,
            "transport": "HTTP",
            "host": "0.0.0.0",
            "port": "not-a-number",
            "auto_start": True,
            "exposed_tool_groups": ["cases", "bad-group", "database"],
        }

        normalized = _normalize_mcp_settings(payload)

        self.assertTrue(normalized["enabled"])
        self.assertEqual(normalized["transport"], "http")
        self.assertEqual(normalized["host"], "0.0.0.0")
        self.assertEqual(normalized["port"], DEFAULT_MCP_SETTINGS["port"])
        self.assertTrue(normalized["auto_start"])
        self.assertEqual(normalized["exposed_tool_groups"], ["cases", "database"])

    @patch("backend.app.services.mcp_server.get_app_settings", return_value={})
    def test_read_mcp_settings_returns_defaults_and_status(self, _settings_mock):
        payload = read_mcp_settings()

        self.assertEqual(payload["settings"]["transport"], "stdio")
        self.assertIn("cases", payload["status"]["implemented_groups"])
        self.assertIn("extractor", payload["status"]["implemented_groups"])
        self.assertIn("registry", payload["status"]["implemented_groups"])
        self.assertIn("logs", payload["status"]["implemented_groups"])
        self.assertIn("memory", payload["status"]["implemented_groups"])
        self.assertIn("ssh", payload["status"]["implemented_groups"])
        self.assertEqual(payload["status"]["server_module"], "mcp_server.server")
        self.assertEqual(
            [group["key"] for group in payload["tool_groups"]],
            [group["key"] for group in MCP_TOOL_GROUPS],
        )

    @patch("backend.app.services.mcp_server.read_mcp_settings")
    @patch("backend.app.services.mcp_server.save_app_settings")
    def test_update_mcp_settings_persists_normalized_payload(self, save_mock, read_mock):
        payload = {
            "enabled": True,
            "transport": "http",
            "host": "127.0.0.1",
            "port": 9001,
            "auto_start": True,
            "exposed_tool_groups": ["cases", "database", "unknown"],
        }
        read_mock.return_value = {
            "settings": {
                "enabled": True,
                "transport": "http",
                "host": "127.0.0.1",
                "port": 9001,
                "auto_start": True,
                "exposed_tool_groups": ["cases", "database"],
            },
            "tool_groups": [],
            "status": {"implemented_groups": ["cases", "database"], "server_module": "mcp_server.server", "running": False},
        }

        result = update_mcp_settings(payload)

        save_mock.assert_called_once_with(
            {
                "mcp_server": {
                    "enabled": True,
                    "transport": "http",
                    "host": "127.0.0.1",
                    "port": 9001,
                    "auto_start": True,
                    "exposed_tool_groups": ["cases", "database"],
                }
            }
        )
        self.assertEqual(result["settings"]["exposed_tool_groups"], ["cases", "database"])

    @patch("backend.app.services.mcp_server.read_mcp_settings")
    def test_export_mcp_client_config_includes_both_stdio_and_http(self, read_mock):
        read_mock.return_value = {
            "settings": {
                "enabled": True,
                "transport": "stdio",
                "host": "127.0.0.1",
                "port": 8765,
                "auto_start": False,
                "exposed_tool_groups": ["cases"],
            },
            "tool_groups": [],
            "status": {"implemented_groups": ["cases"], "server_module": "mcp_server.server", "running": False},
        }

        payload = export_mcp_client_config()

        self.assertEqual(payload["transport"], "stdio")
        self.assertIn('"mcpServers"', payload["stdio_json"])
        self.assertIn('"command"', payload["stdio_json"])
        self.assertIn('"url"', payload["http_json"])
        self.assertIn("http://127.0.0.1:8765/mcp", payload["http_url"])


if __name__ == "__main__":
    unittest.main()
