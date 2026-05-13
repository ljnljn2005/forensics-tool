from src.windows_registry import lookup_default_apps_report, query_registry_path_report


def build_registry_scan_response(scan_item: str, text: str, mapping_path: str = "") -> dict:
    return {
        "scan_item": scan_item,
        "mapping_path": mapping_path,
        "text": text,
    }


def run_registry_scan(mapping_path: str, scan_item: str, registry_path: str = "") -> dict:
    if scan_item == "default_apps":
        text = lookup_default_apps_report(mapping_path)
    else:
        text = query_registry_path_report(mapping_path, registry_path)
    return build_registry_scan_response(scan_item, text, mapping_path=mapping_path)
