from backend.app.services.mcp_server import MCP_TOOL_GROUPS, read_mcp_settings
from mcp_server.tools import (
    android_match_auto_plugins,
    android_run_auto_forensics,
    android_scan_installed_packages,
    cases_get_evidence_by_type,
    cases_list,
    cases_save,
    cases_select,
    database_inspect_sqlite,
    extractor_list_entries,
    extractor_run_entry,
    file_inspect,
    file_open,
    log_detail,
    log_scan,
    memory_list_tasks,
    memory_preview_task,
    memory_run_task,
    registry_scan,
    ssh_run_plugin,
    ssh_test_connection,
)


TOOL_REGISTRY = {
    "cases_list": cases_list,
    "cases_save": cases_save,
    "cases_select": cases_select,
    "cases_get_evidence_by_type": cases_get_evidence_by_type,
    "android_scan_installed_packages": android_scan_installed_packages,
    "android_match_auto_plugins": android_match_auto_plugins,
    "android_run_auto_forensics": android_run_auto_forensics,
    "file_inspect": file_inspect,
    "file_open": file_open,
    "database_inspect_sqlite": database_inspect_sqlite,
    "extractor_list_entries": extractor_list_entries,
    "extractor_run_entry": extractor_run_entry,
    "registry_scan": registry_scan,
    "log_scan": log_scan,
    "log_detail": log_detail,
    "memory_list_tasks": memory_list_tasks,
    "memory_preview_task": memory_preview_task,
    "memory_run_task": memory_run_task,
    "ssh_test_connection": ssh_test_connection,
    "ssh_run_plugin": ssh_run_plugin,
}


def describe_server() -> dict:
    payload = read_mcp_settings()
    enabled_groups = set(payload["settings"].get("exposed_tool_groups", []))
    tools = []
    for group in MCP_TOOL_GROUPS:
        if group.get("key") not in enabled_groups:
            continue
        for tool_name in group.get("tools", []):
            tools.append(
                {
                    "name": tool_name,
                    "group": group.get("key", ""),
                    "implemented": tool_name in TOOL_REGISTRY,
                }
            )
    return {
        "name": "forensics-tool-mcp",
        "transport": payload["settings"]["transport"],
        "enabled": payload["settings"]["enabled"],
        "tool_groups": MCP_TOOL_GROUPS,
        "tools": tools,
    }


def call_tool(tool_name: str, arguments: dict | None = None) -> dict:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"unknown tool: {tool_name}")
    return TOOL_REGISTRY[tool_name](**dict(arguments or {}))


def list_tools() -> list[dict]:
    return describe_server().get("tools", [])


def health() -> dict:
    return {"ok": True, "name": "forensics-tool-mcp", "tool_count": len(TOOL_REGISTRY)}


if __name__ == "__main__":
    info = describe_server()
    print(f"{info['name']} scaffold ready")
