import csv
import io
import locale
import os
import subprocess
import sys

import yaml

from .constants import BASE_DIR, get_app_settings, save_app_settings


BUNDLED_MEMORY_TOOL_ROOT = os.path.join(BASE_DIR, "tools", "memory")


def _first_existing_path(*candidates: str) -> str:
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return os.path.abspath(candidate)
    return ""


def _resolve_python_runtime(root: str) -> str:
    bundled_python = _first_existing_path(
        os.path.join(root, "python3", "python.exe"),
        os.path.join(root, "python", "python.exe"),
    )
    if bundled_python:
        return bundled_python
    return sys.executable


def _resolve_from_config(root: str) -> dict:
    config_path = os.path.join(root or "", "config", "base_config.yaml")
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    def resolve(rel_path: str) -> str:
        if not rel_path:
            return ""
        return os.path.abspath(os.path.join(root, rel_path))

    return {
        "python310": resolve(data.get("base_tools", {}).get("python310", {}).get("path", "")),
        "memprocfs": resolve(data.get("tools", {}).get("memprocfs", {}).get("path", "")),
        "volatility3": resolve(data.get("tools", {}).get("volatility3", {}).get("path", "")),
        "volatility3_symbols": resolve(data.get("tools", {}).get("volatility3_symbols", {}).get("path", "")),
    }


def bundled_memory_tool_root() -> str:
    return BUNDLED_MEMORY_TOOL_ROOT


def is_memory_tool_root(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    tool_paths = load_memory_tool_paths(path)
    return bool(tool_paths.get("memprocfs") or tool_paths.get("volatility3"))


def default_memory_tool_root() -> str:
    saved = ""
    try:
        settings = get_app_settings()
        saved = settings.get("memory_tools_root", "") or settings.get("lovelymem_root", "")
    except Exception:
        saved = ""

    bundled = bundled_memory_tool_root()
    if is_memory_tool_root(bundled):
        return bundled
    if is_memory_tool_root(saved):
        return saved
    return ""


def load_memory_tool_paths(root: str) -> dict:
    root = os.path.abspath(root) if root else ""

    bundled_paths = {
        "python310": _resolve_python_runtime(root),
        "memprocfs": _first_existing_path(
            os.path.join(root, "memprocfs", "MemProcFS.exe"),
            os.path.join(root, "MemProcFS.exe"),
        ),
        "volatility3": _first_existing_path(
            os.path.join(root, "volatility3", "vol.py"),
            os.path.join(root, "vol.py"),
        ),
        "volatility3_symbols": _first_existing_path(
            os.path.join(root, "volatility3", "volatility3", "symbols"),
            os.path.join(root, "volatility3", "symbols"),
            os.path.join(root, "symbols"),
        ),
    }

    config_paths = _resolve_from_config(root)
    merged = dict(bundled_paths)
    for key, value in config_paths.items():
        if value:
            merged[key] = value
    return merged


def build_memprocfs_command(paths: dict, memory_image: str) -> list[str]:
    return [
        paths.get("memprocfs", ""),
        "-device",
        memory_image,
        "-v",
        "-license-accept-elastic-license-2-0",
        "-forensic",
        "1",
    ]


def build_vol3_windows_command(paths: dict, memory_image: str, plugin: str, offline: bool = False) -> list[str]:
    command = [
        paths.get("python310", sys.executable),
        paths.get("volatility3", ""),
        "-f",
        memory_image,
    ]
    symbol_dir = paths.get("volatility3_symbols", "")
    if symbol_dir:
        command.extend(["--symbol-dirs", symbol_dir])
    if offline:
        command.append("--offline")
    renderer = "quick" if plugin in {"hashdump", "lsadump", "cachedump", "truecrypt"} else "csv"
    command.extend(["-r", renderer, f"windows.{plugin}"])
    return command


def build_vol3_linux_command(paths: dict, memory_image: str, plugin: str, offline: bool = False) -> list[str]:
    command = [
        paths.get("python310", sys.executable),
        paths.get("volatility3", ""),
        "-f",
        memory_image,
    ]
    symbol_dir = paths.get("volatility3_symbols", "")
    if symbol_dir:
        command.extend(["--symbol-dirs", symbol_dir])
    if offline:
        command.append("--offline")
    command.extend(["-r", "quick" if plugin == "linux.psaux" else "csv", plugin])
    return command


def windows_memory_tasks() -> list[dict]:
    return [
        {"name": "加载内存文件系统", "engine": "memprocfs_mount", "output": "text"},
        {"name": "进程列表", "engine": "memprocfs_csv", "result_path": r"M:\forensic\csv\process.csv", "output": "csv"},
        {"name": "网络连接", "engine": "memprocfs_csv", "result_path": r"M:\forensic\csv\net.csv", "output": "csv"},
        {"name": "句柄列表", "engine": "memprocfs_csv", "result_path": r"M:\forensic\csv\handles.csv", "output": "csv"},
        {"name": "系统信息", "engine": "memprocfs_text", "result_path": r"M:\sys\sysinfo\sysinfo.txt", "output": "text"},
        {"name": "进程列表（高级引擎）", "engine": "vol3_windows", "plugin": "pslist", "output": "csv"},
        {"name": "进程树（高级引擎）", "engine": "vol3_windows", "plugin": "pstree", "output": "csv"},
        {"name": "网络连接（高级引擎）", "engine": "vol3_windows", "plugin": "netscan", "output": "csv"},
        {"name": "句柄列表（高级引擎）", "engine": "vol3_windows", "plugin": "handles", "output": "csv"},
        {"name": "命令行（高级引擎）", "engine": "vol3_windows", "plugin": "cmdline", "output": "csv"},
        {"name": "恶意注入（高级引擎）", "engine": "vol3_windows", "plugin": "malfind", "output": "csv"},
        {"name": "HashDump（高级引擎）", "engine": "vol3_windows", "plugin": "hashdump", "output": "text"},
        {"name": "LsaDump（高级引擎）", "engine": "vol3_windows", "plugin": "lsadump", "output": "text"},
    ]


def linux_memory_tasks() -> list[dict]:
    return [
        {"name": "进程列表", "engine": "vol3_linux", "plugin": "linux.pslist", "output": "csv"},
        {"name": "进程扫描", "engine": "vol3_linux", "plugin": "linux.psscan", "output": "csv"},
        {"name": "进程树", "engine": "vol3_linux", "plugin": "linux.pstree", "output": "csv"},
        {"name": "命令行", "engine": "vol3_linux", "plugin": "linux.psaux", "output": "text"},
        {"name": "环境变量", "engine": "vol3_linux", "plugin": "linux.envars", "output": "csv"},
        {"name": "网络连接", "engine": "vol3_linux", "plugin": "linux.netstat", "output": "csv"},
        {"name": "文件句柄", "engine": "vol3_linux", "plugin": "linux.lsof", "output": "csv"},
        {"name": "已加载模块", "engine": "vol3_linux", "plugin": "linux.lsmod", "output": "csv"},
        {"name": "恶意注入", "engine": "vol3_linux", "plugin": "linux.malfind", "output": "csv"},
        {"name": "系统调用检查", "engine": "vol3_linux", "plugin": "linux.check_syscall", "output": "csv"},
    ]


def read_csv_rows(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def parse_csv_bytes(data: bytes) -> list[dict]:
    text = data.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def decode_command_output(data: bytes) -> str:
    encodings = [locale.getpreferredencoding(False), "utf-8", "gbk"]
    for encoding in encodings:
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# Backward-compatible aliases for earlier imports.
default_lovelymem_root = default_memory_tool_root
load_lovelymem_tool_paths = load_memory_tool_paths
