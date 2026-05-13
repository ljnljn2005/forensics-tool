from backend.app.services.android_auto_forensics import scan_android_apps


def android_scan_installed_packages(mapping_path: str) -> dict:
    payload = scan_android_apps(mapping_path, [])
    installed_packages = payload.get("installed_packages", [])
    return {
        "summary": {
            "mapping_path": mapping_path,
            "installed_package_count": len(installed_packages),
            "matched_package_count": len(payload.get("matched_packages", [])),
        },
        "android_system_roots": payload.get("android_system_roots", []),
        "installed_packages": installed_packages,
    }


def android_match_auto_plugins(mapping_path: str) -> dict:
    payload = scan_android_apps(mapping_path, [])
    matches = [
        {
            "package_name": item.get("package_name", ""),
            "entry_count": len(item.get("entries", [])),
            "entries": [
                {
                    "group": entry.get("group", ""),
                    "name": entry.get("name", ""),
                    "type": entry.get("type", ""),
                    "resolved_path": entry.get("resolved_path", ""),
                }
                for entry in item.get("entries", [])
            ],
        }
        for item in payload.get("matched_packages", [])
    ]
    return {
        "summary": {
            "mapping_path": mapping_path,
            "matched_package_count": len(matches),
        },
        "matches": matches,
    }


def android_run_auto_forensics(mapping_path: str) -> dict:
    payload = scan_android_apps(mapping_path, [])
    return {
        "summary": {
            "mapping_path": mapping_path,
            "installed_package_count": len(payload.get("installed_packages", [])),
            "matched_package_count": len(payload.get("matched_packages", [])),
        },
        "installed_packages": payload.get("installed_packages", []),
        "matched_packages": payload.get("matched_packages", []),
    }
