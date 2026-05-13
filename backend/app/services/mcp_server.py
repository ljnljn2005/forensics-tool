import json
import sys
from copy import deepcopy

from src.constants import BASE_DIR, get_app_settings, save_app_settings


DEFAULT_MCP_SETTINGS = {
    "enabled": False,
    "transport": "stdio",
    "host": "127.0.0.1",
    "port": 8765,
    "auto_start": False,
    "exposed_tool_groups": [
        "cases",
        "android_auto_forensics",
        "file_browser",
        "database",
    ],
}

MCP_TOOL_GROUPS = [
    {
        "key": "cases",
        "label": "案件与检材",
        "status": "planned",
        "tools": ["cases_list", "cases_save", "cases_select", "cases_get_evidence_by_type"],
    },
    {
        "key": "android_auto_forensics",
        "label": "Android 自动取证",
        "status": "planned",
        "tools": ["android_scan_installed_packages", "android_match_auto_plugins", "android_run_auto_forensics"],
    },
    {
        "key": "file_browser",
        "label": "文件与路径浏览",
        "status": "planned",
        "tools": ["file_inspect", "file_open"],
    },
    {
        "key": "database",
        "label": "数据库查看",
        "status": "planned",
        "tools": ["database_inspect_sqlite"],
    },
    {
        "key": "extractor",
        "label": "本地提取",
        "status": "queued",
        "tools": ["extractor_list_entries", "extractor_run_entry"],
    },
    {
        "key": "registry",
        "label": "注册表分析",
        "status": "queued",
        "tools": ["registry_scan"],
    },
    {
        "key": "logs",
        "label": "日志分析",
        "status": "queued",
        "tools": ["log_scan", "log_detail"],
    },
    {
        "key": "memory",
        "label": "内存取证",
        "status": "queued",
        "tools": ["memory_list_tasks", "memory_preview_task", "memory_run_task"],
    },
    {
        "key": "ssh",
        "label": "SSH 远程取证",
        "status": "queued",
        "tools": ["ssh_test_connection", "ssh_run_plugin"],
    },
]


def _normalize_mcp_settings(payload: dict | None) -> dict:
    raw = payload if isinstance(payload, dict) else {}
    normalized = deepcopy(DEFAULT_MCP_SETTINGS)
    normalized["enabled"] = bool(raw.get("enabled", normalized["enabled"]))
    transport = str(raw.get("transport", normalized["transport"])).strip().lower()
    normalized["transport"] = transport if transport in {"stdio", "http"} else normalized["transport"]
    normalized["host"] = str(raw.get("host", normalized["host"])).strip() or normalized["host"]
    try:
        normalized["port"] = int(raw.get("port", normalized["port"]) or normalized["port"])
    except (TypeError, ValueError):
        normalized["port"] = DEFAULT_MCP_SETTINGS["port"]
    normalized["auto_start"] = bool(raw.get("auto_start", normalized["auto_start"]))
    groups = raw.get("exposed_tool_groups", normalized["exposed_tool_groups"])
    if isinstance(groups, list):
        allowed = {group["key"] for group in MCP_TOOL_GROUPS}
        normalized["exposed_tool_groups"] = [str(item) for item in groups if str(item) in allowed]
    return normalized


def read_mcp_settings() -> dict:
    settings = get_app_settings()
    current = _normalize_mcp_settings(settings.get("mcp_server"))
    return {
        "settings": current,
        "tool_groups": deepcopy(MCP_TOOL_GROUPS),
        "status": {
            "implemented_groups": [
                "cases",
                "android_auto_forensics",
                "file_browser",
                "database",
                "extractor",
                "registry",
                "logs",
                "memory",
                "ssh",
            ],
            "server_module": "mcp_server.server",
            "running": False,
        },
    }


def update_mcp_settings(payload: dict) -> dict:
    current = _normalize_mcp_settings(payload)
    save_app_settings({"mcp_server": current})
    return read_mcp_settings()


def export_mcp_client_config() -> dict:
    payload = read_mcp_settings()
    settings = payload["settings"]
    server_name = "forensics-tool"
    stdio_config = {
        "mcpServers": {
            server_name: {
                "command": sys.executable,
                "args": ["-m", "mcp_server.server"],
                "cwd": BASE_DIR,
                "env": {
                    "PYTHONIOENCODING": "utf-8",
                },
            }
        }
    }
    http_url = f"http://{settings['host']}:{settings['port']}/mcp"
    http_config = {
        "mcpServers": {
            server_name: {
                "url": http_url,
            }
        }
    }
    active_config = stdio_config if settings["transport"] == "stdio" else http_config
    return {
        "server_name": server_name,
        "transport": settings["transport"],
        "python_executable": sys.executable,
        "project_root": BASE_DIR,
        "module": "mcp_server.server",
        "http_url": http_url,
        "active_json": json.dumps(active_config, ensure_ascii=False, indent=2),
        "stdio_json": json.dumps(stdio_config, ensure_ascii=False, indent=2),
        "http_json": json.dumps(http_config, ensure_ascii=False, indent=2),
        "notes": [
            "大多数支持 MCP 的 Agent 客户端都可以直接导入 mcpServers JSON。",
            "如果客户端支持 stdio，优先使用 stdio 配置；如果支持 URL 型 MCP，再使用 HTTP 配置。",
            "当前页面导出的是可复制配置，正式 HTTP 服务启动控制会在后续继续补齐。",
        ],
    }
