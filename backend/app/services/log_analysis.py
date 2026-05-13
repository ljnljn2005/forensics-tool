from src.log_analysis import discover_logs, parse_evtx_text, read_log_detail


def list_logs(mapping_path: str, module: str) -> dict:
    entries = discover_logs(mapping_path, module)
    return {
        "module": module,
        "mapping_path": mapping_path,
        "entries": entries,
    }


def get_log_detail(entry: dict) -> dict:
    text = read_log_detail(entry)
    events = parse_evtx_text(text) if str(entry.get("path", "")).lower().endswith(".evtx") else []
    return {
        "entry": entry,
        "text": text,
        "events": events,
    }
