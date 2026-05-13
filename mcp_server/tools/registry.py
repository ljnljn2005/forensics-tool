from backend.app.services.registry_scan import run_registry_scan


def registry_scan(mapping_path: str, scan_item: str = "default_apps", registry_path: str = "") -> dict:
    payload = run_registry_scan(mapping_path, scan_item, registry_path)
    return {
        "summary": {
            "mapping_path": mapping_path,
            "scan_item": scan_item,
            "registry_path": registry_path,
        },
        **payload,
    }
