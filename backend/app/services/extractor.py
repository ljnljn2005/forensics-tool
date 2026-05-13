import json
import os
from collections import defaultdict

from backend.app.services.plugins import is_android_auto_plugin
from src.constants import PLUGINS_DIR, get_app_settings
from src.extractor import MODULE_LABELS, execute_command_for_ai


PLUGINS_FILE = os.path.join(PLUGINS_DIR, "ssh_plugins.json")


def _load_plugin_payload() -> dict:
    try:
        with open(PLUGINS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def list_extractor_entries(module: str) -> dict:
    payload = _load_plugin_payload()
    entries = []
    grouped = defaultdict(list)

    for group_name, group_data in payload.items():
        plugin_payload = group_data if isinstance(group_data, dict) else {"blocks": group_data}
        if module == "android" and is_android_auto_plugin(plugin_payload):
            continue
        blocks = group_data.get("blocks", []) if isinstance(group_data, dict) else group_data
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            block_module = (block.get("module") or "").lower()
            block_type = block.get("type", "")
            if block_module and block_module != module:
                continue
            if "文件" not in block_type and "提取" not in block_type:
                continue
            entry = {
                "group": group_name,
                "plugin": group_name,
                "name": block.get("name", ""),
                "cmd": block.get("cmd", ""),
                "type": block_type,
                "module": block_module or module,
            }
            entries.append(entry)
            grouped[group_name].append(entry)

    return {
        "module": module,
        "module_label": MODULE_LABELS.get(module, module.capitalize()),
        "entries": entries,
        "groups": [{"name": group_name, "count": len(group_entries)} for group_name, group_entries in grouped.items()],
    }


def run_extractor_entry(module: str, mapping_path: str, entry: dict) -> dict:
    result = execute_command_for_ai(
        entry.get("cmd", ""),
        base_path=mapping_path or get_app_settings().get("mapping_path"),
        btype=entry.get("type", ""),
    )
    return {
        "module": module,
        "mapping_path": mapping_path,
        "entry": entry,
        "text": result,
    }
