import unittest
from unittest.mock import patch

from mcp_server.server import call_tool, describe_server, health, list_tools


class McpServerRuntimeTests(unittest.TestCase):
    @patch("mcp_server.server.read_mcp_settings")
    def test_describe_server_lists_enabled_tools(self, read_mock):
        read_mock.return_value = {
            "settings": {
                "enabled": True,
                "transport": "stdio",
                "exposed_tool_groups": ["cases", "database"],
            },
            "tool_groups": [],
            "status": {},
        }

        payload = describe_server()

        tool_names = {tool["name"] for tool in payload["tools"]}
        self.assertIn("cases_list", tool_names)
        self.assertIn("database_inspect_sqlite", tool_names)
        self.assertNotIn("file_inspect", tool_names)

    @patch("mcp_server.server.read_mcp_settings")
    def test_describe_server_includes_extractor_and_registry_tools_when_enabled(self, read_mock):
        read_mock.return_value = {
            "settings": {
                "enabled": True,
                "transport": "stdio",
                "exposed_tool_groups": ["extractor", "registry"],
            },
            "tool_groups": [],
            "status": {},
        }

        payload = describe_server()

        tools = {tool["name"]: tool for tool in payload["tools"]}
        self.assertTrue(tools["extractor_list_entries"]["implemented"])
        self.assertTrue(tools["extractor_run_entry"]["implemented"])
        self.assertTrue(tools["registry_scan"]["implemented"])

    @patch("mcp_server.server.read_mcp_settings")
    def test_describe_server_includes_logs_memory_and_ssh_tools_when_enabled(self, read_mock):
        read_mock.return_value = {
            "settings": {
                "enabled": True,
                "transport": "stdio",
                "exposed_tool_groups": ["logs", "memory", "ssh"],
            },
            "tool_groups": [],
            "status": {},
        }

        payload = describe_server()

        tools = {tool["name"]: tool for tool in payload["tools"]}
        self.assertTrue(tools["log_scan"]["implemented"])
        self.assertTrue(tools["log_detail"]["implemented"])
        self.assertTrue(tools["memory_list_tasks"]["implemented"])
        self.assertTrue(tools["memory_preview_task"]["implemented"])
        self.assertTrue(tools["memory_run_task"]["implemented"])
        self.assertTrue(tools["ssh_test_connection"]["implemented"])
        self.assertTrue(tools["ssh_run_plugin"]["implemented"])

    @patch("mcp_server.server.TOOL_REGISTRY", {"demo_tool": lambda value: {"value": value}})
    def test_call_tool_dispatches_arguments(self):
        payload = call_tool("demo_tool", {"value": 7})

        self.assertEqual(payload, {"value": 7})

    @patch("mcp_server.server.describe_server")
    def test_list_tools_returns_described_tools(self, describe_mock):
        describe_mock.return_value = {"tools": [{"name": "cases_list"}]}

        self.assertEqual(list_tools(), [{"name": "cases_list"}])

    def test_health_payload(self):
        payload = health()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["name"], "forensics-tool-mcp")


if __name__ == "__main__":
    unittest.main()
