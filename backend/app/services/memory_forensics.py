from __future__ import annotations

import os
import subprocess
from typing import Any

from src.memory_forensics import (
    build_memprocfs_command,
    build_vol3_linux_command,
    build_vol3_windows_command,
    decode_command_output,
    default_memory_tool_root,
    load_memory_tool_paths,
    parse_csv_bytes,
    linux_memory_tasks,
    windows_memory_tasks,
)


_MEMPROCFS_PROCESS: subprocess.Popen | None = None


def list_memory_tasks(module: str) -> dict[str, Any]:
    tasks = windows_memory_tasks() if module == "windows" else linux_memory_tasks()
    return {
        "module": module,
        "default_tool_root": default_memory_tool_root(),
        "tasks": tasks,
    }


def preview_memory_task(
    module: str,
    task: dict[str, Any],
    tool_root: str,
    memory_image: str,
    offline: bool,
) -> dict[str, Any]:
    tool_paths = load_memory_tool_paths(tool_root)
    engine = task.get("engine", "")
    image = memory_image or "<memory-image>"

    if engine == "vol3_windows":
        command = build_vol3_windows_command(tool_paths, image, task.get("plugin", ""), offline=offline)
        preview = "命令预览:\n" + " ".join(command)
    elif engine == "vol3_linux":
        command = build_vol3_linux_command(tool_paths, image, task.get("plugin", ""), offline=offline)
        preview = "命令预览:\n" + " ".join(command)
    elif engine == "memprocfs_mount":
        preview = "挂载命令预览:\n" + " ".join(build_memprocfs_command(tool_paths, image))
    else:
        preview = "结果路径:\n" + task.get("result_path", "")

    return {
        "module": module,
        "task": task,
        "tool_paths": tool_paths,
        "preview_text": preview,
    }


def run_memory_task(
    module: str,
    task: dict[str, Any],
    tool_root: str,
    memory_image: str,
    offline: bool,
) -> dict[str, Any]:
    global _MEMPROCFS_PROCESS

    tool_paths = load_memory_tool_paths(tool_root)
    engine = task.get("engine", "")

    if engine == "memprocfs_mount":
        memprocfs = tool_paths.get("memprocfs", "")
        if not memprocfs:
            return {"ok": False, "text": "未找到 MemProcFS 工具。", "rows": []}
        if not memory_image:
            return {"ok": False, "text": "请先选择内存镜像路径。", "rows": []}
        _MEMPROCFS_PROCESS = subprocess.Popen(build_memprocfs_command(tool_paths, memory_image))
        return {"ok": True, "text": "内存文件系统已启动，请等待挂载完成。", "rows": []}

    if engine.startswith("memprocfs_"):
        result_path = task.get("result_path", "")
        if not result_path or not os.path.exists(result_path):
            return {
                "ok": False,
                "text": f"结果文件不存在，请先挂载内存文件系统:\n{result_path}",
                "rows": [],
            }
        if engine == "memprocfs_text":
            with open(result_path, "r", encoding="utf-8", errors="replace") as handle:
                return {"ok": True, "text": handle.read(), "rows": []}
        with open(result_path, "rb") as handle:
            data = handle.read()
        rows = parse_csv_bytes(data)
        return {"ok": True, "text": f"已加载 CSV 结果，共 {len(rows)} 行。", "rows": rows}

    if not memory_image:
        return {"ok": False, "text": "请先选择内存镜像路径。", "rows": []}

    if engine == "vol3_windows":
        command = build_vol3_windows_command(tool_paths, memory_image, task.get("plugin", ""), offline=offline)
    elif engine == "vol3_linux":
        command = build_vol3_linux_command(tool_paths, memory_image, task.get("plugin", ""), offline=offline)
    else:
        return {"ok": False, "text": f"未知任务引擎: {engine}", "rows": []}

    process = subprocess.run(command, capture_output=True, text=False, timeout=180)
    output = process.stdout + process.stderr
    text = f"退出码: {process.returncode}\n\n{decode_command_output(output)}"
    rows = parse_csv_bytes(process.stdout) if process.returncode == 0 else []
    return {
        "ok": process.returncode == 0,
        "text": text,
        "rows": rows,
    }


def stop_memprocfs() -> dict[str, Any]:
    global _MEMPROCFS_PROCESS
    if _MEMPROCFS_PROCESS and _MEMPROCFS_PROCESS.poll() is None:
        _MEMPROCFS_PROCESS.terminate()
        _MEMPROCFS_PROCESS = None
        return {"ok": True, "text": "内存文件系统已请求停止。"}
    return {"ok": True, "text": "当前没有正在运行的内存文件系统进程。"}
