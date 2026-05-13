from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOOLBOX_ROOT = PROJECT_ROOT / "tools" / "toolbox"


def _tool_catalog() -> list[dict[str, str]]:
    tool_dir = TOOLBOX_ROOT / "Jigsaw Puzzle"
    executable = tool_dir / "启动.exe"
    launcher_bat = tool_dir / "启动.bat"
    launcher_py = tool_dir / "一键使用.py"
    readme = tool_dir / "麻瓜图片拼接使用指北.md"

    return [
        {
            "key": "jigsaw-puzzle",
            "name": "Jigsaw Puzzle",
            "description": "图片拼接与碎片拼图辅助工具。",
            "tool_dir": str(tool_dir),
            "entry_path": str(executable if executable.is_file() else launcher_bat if launcher_bat.is_file() else launcher_py),
            "readme_path": str(readme),
        }
    ]


def list_toolbox_tools() -> dict[str, list[dict[str, str]]]:
    return {"tools": _tool_catalog()}


def launch_tool(tool_key: str) -> dict[str, object]:
    tool = next((item for item in _tool_catalog() if item["key"] == tool_key), None)
    if tool is None:
        raise ValueError(f"Unknown toolbox tool: {tool_key}")

    tool_dir = Path(tool["tool_dir"])
    if not tool_dir.is_dir():
        raise ValueError(f"Tool directory does not exist: {tool_dir}")

    executable = tool_dir / "启动.exe"
    launcher_bat = tool_dir / "启动.bat"
    launcher_py = tool_dir / "一键使用.py"

    creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

    if executable.is_file():
        process = subprocess.Popen([str(executable)], cwd=str(tool_dir), creationflags=creation_flags)
        target = executable
    elif launcher_bat.is_file():
        process = subprocess.Popen(["cmd.exe", "/c", str(launcher_bat)], cwd=str(tool_dir), creationflags=creation_flags)
        target = launcher_bat
    elif launcher_py.is_file():
        process = subprocess.Popen([sys.executable, str(launcher_py)], cwd=str(tool_dir), creationflags=creation_flags)
        target = launcher_py
    else:
        raise ValueError(f"No launch entry found under: {tool_dir}")

    return {
        "ok": True,
        "tool_key": tool_key,
        "pid": process.pid,
        "entry_path": str(target),
        "message": f"已启动 {tool['name']}",
    }
