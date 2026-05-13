from backend.app.services.log_analysis import get_log_detail, list_logs


def log_scan(mapping_path: str, module: str) -> dict:
    payload = list_logs(mapping_path, module)
    return {
        "summary": {
            "mapping_path": mapping_path,
            "module": module,
            "entry_count": len(payload.get("entries", [])),
        },
        **payload,
    }


def log_detail(entry: dict) -> dict:
    payload = get_log_detail(entry)
    return {
        "summary": {
            "path": entry.get("path", ""),
            "event_count": len(payload.get("events", [])),
            "text_length": len(payload.get("text", "")),
        },
        **payload,
    }
