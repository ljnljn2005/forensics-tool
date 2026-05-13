import os
import sqlite3
from typing import Any

from backend.app.services.file_signatures import detect_file_signature
from src.extractor import materialize_mapped_file


def inspect_sqlite_database(mapping_path: str, database_path: str) -> dict[str, Any]:
    temp_path = ""
    try:
        temp_path, source_path, tried_paths = materialize_mapped_file(database_path, base_path=mapping_path, suffix=".db")
        with open(temp_path, "rb") as handle:
            header = handle.read(16)
        detected = detect_file_signature(header)
        if detected["kind"] != "database" or detected["format"] != "sqlite":
            return {
                "ok": False,
                "database_path": database_path,
                "source_path": source_path,
                "tried_paths": tried_paths,
                "message": "当前仅支持常见 SQLite 数据库，这个文件不是标准 SQLite 格式。",
                "tables": [],
            }

        connection = sqlite3.connect(temp_path)
        connection.row_factory = sqlite3.Row
        try:
            table_rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()

            tables = []
            for row in table_rows:
                table_name = str(row["name"])
                columns = [item["name"] for item in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()]
                row_count = connection.execute(f'SELECT COUNT(*) AS c FROM "{table_name}"').fetchone()["c"]
                preview_rows = [
                    dict(item)
                    for item in connection.execute(f'SELECT * FROM "{table_name}" LIMIT 100').fetchall()
                ]
                tables.append(
                    {
                        "name": table_name,
                        "columns": columns,
                        "row_count": row_count,
                        "preview_rows": preview_rows,
                    }
                )
        finally:
            connection.close()

        return {
            "ok": True,
            "database_path": database_path,
            "source_path": source_path,
            "tried_paths": tried_paths,
            "message": "",
            "tables": tables,
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
