from backend.app.services.extractor import list_extractor_entries, run_extractor_entry


def extractor_list_entries(module: str) -> dict:
    payload = list_extractor_entries(module)
    return {
        "summary": {
            "module": module,
            "entry_count": len(payload.get("entries", [])),
            "group_count": len(payload.get("groups", [])),
        },
        **payload,
    }


def extractor_run_entry(module: str, mapping_path: str, entry: dict) -> dict:
    payload = run_extractor_entry(module, mapping_path, entry)
    return {
        "summary": {
            "module": module,
            "mapping_path": mapping_path,
            "entry_name": entry.get("name", ""),
            "plugin": entry.get("plugin") or entry.get("group", ""),
        },
        **payload,
    }
