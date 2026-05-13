import json
import os

from src.constants import PLUGINS_DIR


def search_plugins(keyword: str) -> dict:
    query = (keyword or "").strip().lower()
    if not query:
        return {"keyword": keyword, "results": []}

    matches = []
    central_file = os.path.join(PLUGINS_DIR, "ssh_plugins.json")
    central = {}
    if os.path.exists(central_file):
        try:
            with open(central_file, "r", encoding="utf-8") as handle:
                central = json.load(handle)
        except Exception:
            central = {}

    for pname, pdata in central.items():
        if isinstance(pdata, dict):
            blocks = pdata.get("blocks", [])
            author = pdata.get("author", "")
            description = pdata.get("description", "")
        else:
            blocks = pdata
            author = ""
            description = ""
        _append_matches(matches, pname, author, description, blocks, query)

    for file_name in os.listdir(PLUGINS_DIR):
        if not file_name.endswith(".json"):
            continue
        file_path = os.path.join(PLUGINS_DIR, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                plugin_data = json.load(handle)
        except Exception:
            continue

        if isinstance(plugin_data, dict):
            plugin_name = plugin_data.get("name", os.path.splitext(file_name)[0])
            author = plugin_data.get("author", "")
            description = plugin_data.get("description", "")
            blocks = plugin_data.get("blocks", [])
        else:
            plugin_name = os.path.splitext(file_name)[0]
            author = ""
            description = ""
            blocks = plugin_data

        _append_matches(matches, plugin_name, author, description, blocks, query)

    return {"keyword": keyword, "results": matches}


def _append_matches(matches: list, plugin_name: str, author: str, description: str, blocks, query: str):
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        haystack = " ".join(
            [
                plugin_name,
                author,
                description,
                block.get("name", ""),
                block.get("cmd", ""),
                block.get("type", ""),
                block.get("module", ""),
            ]
        ).lower()
        if query not in haystack:
            continue
        matches.append(
            {
                "plugin": plugin_name,
                "author": author,
                "description": description,
                "block_name": block.get("name", ""),
                "cmd": block.get("cmd", ""),
                "type": block.get("type", ""),
                "module": block.get("module", ""),
            }
        )
