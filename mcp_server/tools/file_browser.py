from backend.app.services.file_browser import inspect_mapped_path, open_mapped_path


def file_inspect(mapping_path: str, target_path: str) -> dict:
    payload = inspect_mapped_path(mapping_path, target_path)
    return {
        "summary": {
            "mapping_path": mapping_path,
            "target_path": target_path,
            "kind": payload.get("kind", ""),
            "child_count": len(payload.get("children", [])),
        },
        **payload,
    }


def file_open(mapping_path: str, target_path: str, action: str = "default") -> dict:
    payload = open_mapped_path(mapping_path, target_path, action)
    return {
        "summary": {
            "mapping_path": mapping_path,
            "target_path": target_path,
            "action": action,
            "kind": payload.get("kind", ""),
        },
        **payload,
    }
