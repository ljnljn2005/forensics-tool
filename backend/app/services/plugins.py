import json
import os
import urllib.request
from urllib import parse as urllib_parse

from src.constants import PLUGINS_DIR, get_app_proxy
from src.extractor import extract_android_package_name


PLUGINS_FILE = os.path.join(PLUGINS_DIR, "ssh_plugins.json")


def _normalize_blocks(plugin: dict) -> list[dict]:
    blocks = plugin.get("blocks", [])
    if not isinstance(blocks, list):
        return []
    normalized = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        normalized.append(
            {
                "name": block.get("name", ""),
                "cmd": block.get("cmd", ""),
                "type": block.get("type", ""),
                "module": block.get("module", plugin.get("module", "")),
                "category": block.get("category", ""),
                "package_name": block.get("package_name", ""),
            }
        )
    return normalized


def _derive_android_package_names(blocks: list[dict]) -> list[str]:
    packages: set[str] = set()
    for block in blocks:
        if (block.get("module") or "").lower() != "android":
            continue
        explicit = str(block.get("package_name", "")).strip()
        if explicit:
            packages.add(explicit)
            continue
        inferred = extract_android_package_name(str(block.get("cmd", "")))
        if inferred:
            packages.add(inferred)
    return sorted(packages)


def is_android_auto_plugin(plugin: dict) -> bool:
    package_names = plugin.get("package_names", [])
    if isinstance(package_names, list) and any(str(item).strip() for item in package_names):
        return True
    for block in plugin.get("blocks", []):
        if not isinstance(block, dict):
            continue
        if (block.get("module") or "").lower() != "android":
            continue
        if str(block.get("package_name", "")).strip():
            return True
    return False


def normalize_plugin(plugin: dict, fallback_name: str = "") -> dict:
    name = str(plugin.get("name", "")).strip() or fallback_name
    blocks = _normalize_blocks(plugin)
    package_names = plugin.get("package_names", [])
    if not isinstance(package_names, list):
        package_names = []
    derived_packages = _derive_android_package_names(blocks)
    merged_packages = sorted({str(item).strip() for item in package_names if str(item).strip()} | set(derived_packages))
    modules = sorted({str(block.get("module", "")).lower() for block in blocks if str(block.get("module", "")).strip()})
    return {
        "name": name,
        "author": plugin.get("author", ""),
        "description": plugin.get("description", ""),
        "module": plugin.get("module", ""),
        "blocks": blocks,
        "package_names": merged_packages,
        "detected_modules": modules,
    }


def _load_plugins() -> dict:
    if not os.path.exists(PLUGINS_FILE):
        return {}
    try:
        with open(PLUGINS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_plugins(data: dict):
    with open(PLUGINS_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)


def _load_local_plugin_files() -> dict[str, dict]:
    plugins: dict[str, dict] = {}
    for filename in os.listdir(PLUGINS_DIR):
        if not filename.endswith(".json") or filename == "ssh_plugins.json":
            continue
        path = os.path.join(PLUGINS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                plugin = normalize_plugin(payload, fallback_name=os.path.splitext(filename)[0])
                if plugin["name"]:
                    plugins[plugin["name"]] = plugin
        except Exception:
            continue
    return plugins


def list_plugins() -> dict:
    plugins: dict[str, dict] = {}
    plugins.update(_load_local_plugin_files())
    for name, payload in _load_plugins().items():
        if isinstance(payload, dict) and "blocks" in payload:
            plugin = normalize_plugin(payload, fallback_name=name)
            if plugin["name"]:
                plugins[plugin["name"]] = plugin
    return {"plugins": sorted(plugins.values(), key=lambda item: item["name"].lower())}


def list_android_auto_plugins() -> list[dict]:
    result = []
    for plugin in list_plugins()["plugins"]:
        if not is_android_auto_plugin(plugin):
            continue
        android_blocks = [block for block in plugin["blocks"] if (block.get("module") or "").lower() == "android"]
        if not android_blocks:
            continue
        result.append(
            {
                "name": plugin["name"],
                "author": plugin.get("author", ""),
                "description": plugin.get("description", ""),
                "package_names": plugin.get("package_names", []),
                "blocks": android_blocks,
            }
        )
    return result


def save_plugin(plugin: dict) -> dict:
    normalized = normalize_plugin(plugin)
    name = normalized.get("name", "").strip()
    if not name:
        raise ValueError("plugin name is required")
    current = _load_plugins()
    current[name] = normalized
    _save_plugins(current)
    plugin_file_path = os.path.join(PLUGINS_DIR, f"{name}.json")
    with open(plugin_file_path, "w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=4, ensure_ascii=False)
    return {"ok": True, "plugin": normalized}


def delete_plugin(name: str) -> dict:
    current = _load_plugins()
    current.pop(name, None)
    _save_plugins(current)
    plugin_file_path = os.path.join(PLUGINS_DIR, f"{name}.json")
    if os.path.exists(plugin_file_path):
        os.remove(plugin_file_path)
    return {"ok": True}


def fetch_plugin_market(url: str) -> dict:
    proxy_str = get_app_proxy()
    opener = None
    if proxy_str:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy_str, "https": proxy_str})
        opener = urllib.request.build_opener(proxy_handler)

    market_data = []
    if url.startswith("http"):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ForensicTool"})
        response = opener.open(req, timeout=10) if opener else urllib.request.urlopen(req, timeout=10)
        files = json.loads(response.read().decode("utf-8"))
        for file_info in files:
            if isinstance(file_info, dict) and file_info.get("name", "").endswith(".json") and file_info.get("name") != "market.json":
                download_url = file_info.get("download_url")
                if not download_url:
                    continue
                parsed = urllib_parse.urlsplit(download_url)
                encoded_path = urllib_parse.quote(urllib_parse.unquote(parsed.path))
                safe_url = urllib_parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment))
                child_req = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0 ForensicTool"})
                child_res = opener.open(child_req, timeout=10) if opener else urllib.request.urlopen(child_req, timeout=10)
                payload = json.loads(child_res.read().decode("utf-8"))
                if isinstance(payload, dict):
                    market_data.append(normalize_plugin(payload, fallback_name=file_info.get("name", "").replace(".json", "")))
    else:
        local_path = url
        if url.startswith("file:///"):
            local_path = url[8:]
        elif url.startswith("file://"):
            local_path = url[7:]
        if os.path.isdir(local_path):
            for filename in os.listdir(local_path):
                if filename.endswith(".json") and filename != "market.json":
                    with open(os.path.join(local_path, filename), "r", encoding="utf-8") as handle:
                        payload = json.load(handle)
                    if isinstance(payload, dict):
                        market_data.append(normalize_plugin(payload, fallback_name=filename.replace(".json", "")))
        else:
            with open(local_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                market_data = [normalize_plugin(item) for item in data if isinstance(item, dict)]
            elif isinstance(data, dict):
                market_data = [normalize_plugin(data)]
    return {"plugins": market_data}
