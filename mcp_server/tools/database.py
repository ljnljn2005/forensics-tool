from backend.app.services.db_viewer import inspect_sqlite_database


def database_inspect_sqlite(mapping_path: str, database_path: str) -> dict:
    payload = inspect_sqlite_database(mapping_path, database_path)
    return {
        "summary": {
            "mapping_path": mapping_path,
            "database_path": database_path,
            "table_count": len(payload.get("tables", [])),
            "ok": bool(payload.get("ok")),
        },
        **payload,
    }
