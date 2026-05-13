import os

from src.extractor import (
    collect_android_installed_packages,
    collect_android_template_packages,
    execute_command_for_ai,
    get_android_system_roots,
    resolve_android_entry_candidates,
)
from backend.app.services.plugins import list_android_auto_plugins


def scan_android_apps(mapping_path: str, entries: list[dict]) -> dict:
    if not entries:
        entries = []
        for plugin in list_android_auto_plugins():
            for block in plugin.get("blocks", []):
                package_names = [str(block.get("package_name", "")).strip()] if str(block.get("package_name", "")).strip() else [
                    str(item).strip() for item in plugin.get("package_names", []) if str(item).strip()
                ]
                if not package_names:
                    package_names = [""]
                for package_name in package_names:
                    entries.append(
                        {
                            "group": plugin.get("name", ""),
                            "name": block.get("name", ""),
                            "cmd": block.get("cmd", ""),
                            "type": block.get("type", ""),
                            "module": block.get("module", "android"),
                            "package_name": package_name,
                        }
                    )

    installed_packages = collect_android_installed_packages(mapping_path)
    template_map = collect_android_template_packages(entries)
    matched_packages = []

    for package_name in installed_packages:
        package_entries = template_map.get(package_name, [])
        if not package_entries:
            continue
        rendered_entries = []
        for entry in package_entries:
            resolved_candidates = resolve_android_entry_candidates(
                mapping_path,
                package_name,
                entry.get("cmd", ""),
            )
            resolved_path = next((candidate for candidate in resolved_candidates if os.path.exists(candidate)), "")
            if not resolved_path and resolved_candidates:
                resolved_path = resolved_candidates[0]
            rendered_entries.append(
                {
                    **entry,
                    "resolved_candidates": resolved_candidates,
                    "resolved_path": resolved_path,
                    "result": execute_command_for_ai(
                        resolved_path or entry.get("cmd", ""),
                        base_path=mapping_path,
                        btype=entry.get("type", ""),
                    ),
                }
            )
        matched_packages.append({"package_name": package_name, "entries": rendered_entries})

    return {
        "mapping_path": mapping_path,
        "android_system_roots": get_android_system_roots(),
        "installed_packages": installed_packages,
        "matched_packages": matched_packages,
    }
