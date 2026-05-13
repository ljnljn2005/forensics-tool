import locale
import os
import re
import subprocess


def discover_logs(mapping_path: str, module: str) -> list[dict]:
    root = os.path.abspath(os.path.expanduser(os.path.expandvars(mapping_path or "")))
    if not root or not os.path.exists(root):
        return []

    if module == "windows":
        return _discover_windows_logs(root)
    return _discover_linux_logs(root)


def _discover_windows_logs(root: str) -> list[dict]:
    entries = []
    targets = [
        ("Windows/System32/winevt/Logs", ".evtx", "事件日志"),
        ("Windows/Logs", ".log", "文本日志"),
        ("Windows/Panther", ".log", "安装日志"),
    ]
    for relative_dir, suffix, category in targets:
        full_dir = os.path.join(root, *relative_dir.split("/"))
        if not os.path.isdir(full_dir):
            continue
        for name in sorted(os.listdir(full_dir)):
            full_path = os.path.join(full_dir, name)
            if os.path.isfile(full_path) and name.lower().endswith(suffix):
                entries.append(_build_log_entry(full_path, "/" + relative_dir.replace("\\", "/") + "/" + name, category))
    return entries


def _discover_linux_logs(root: str) -> list[dict]:
    entries = []
    full_dir = os.path.join(root, "var", "log")
    if not os.path.isdir(full_dir):
        return entries

    for name in sorted(os.listdir(full_dir)):
        full_path = os.path.join(full_dir, name)
        if not os.path.isfile(full_path):
            continue
        if name.endswith((".log", ".txt")) or "." not in name:
            entries.append(_build_log_entry(full_path, f"/var/log/{name}", "系统日志"))
    return entries


def _build_log_entry(full_path: str, display_path: str, category: str) -> dict:
    stat = os.stat(full_path)
    return {
        "name": os.path.basename(full_path),
        "path": full_path,
        "display_path": display_path,
        "category": category,
        "size": stat.st_size,
        "modified": int(stat.st_mtime),
    }


def read_log_detail(entry: dict) -> str:
    path = entry.get("path", "")
    lines = [
        f"名称: {entry.get('name', '')}",
        f"分类: {entry.get('category', '')}",
        f"路径: {entry.get('display_path', path)}",
        f"大小: {entry.get('size', 0)} bytes",
        "",
    ]

    if path.lower().endswith(".evtx"):
        lines.append("事件级解析预览:")
        lines.append(_read_evtx_events(path))
        return "\n".join(lines)

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read(8000)
        lines.append("内容预览:")
        lines.append(content or "[空文件]")
    except Exception as exc:
        lines.append(f"读取失败: {exc}")
    return "\n".join(lines)


def _read_evtx_events(path: str, max_events: int = 30) -> str:
    try:
        result = subprocess.run(
            ["wevtutil", "qe", path, f"/c:{max_events}", "/f:text", "/lf:true"],
            capture_output=True,
            text=True,
            encoding=locale.getpreferredencoding(False) or "utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        return f"事件日志解析失败: {exc}"

    if result.returncode == 0:
        output = (result.stdout or "").strip()
        return output or "未读取到事件内容。"

    error_text = (result.stderr or result.stdout or "").strip()
    if error_text:
        return f"事件日志解析失败:\n{error_text}"
    return "事件日志解析失败。"


def parse_evtx_text(text: str) -> list[dict]:
    source = text.strip()
    matches = list(re.finditer(r"(?m)^Event\[\d+\]:", source))
    if matches:
        chunks = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
            chunks.append(source[start:end].strip())
    else:
        chunks = [source] if source else []
    events = []
    for chunk in chunks:
        block = chunk.strip()
        if not block:
            continue
        event = {
            "event_id": _match_field(block, ["Event ID"]),
            "provider": _match_field(block, ["Provider Name", "Source"]),
            "time_created": _match_field(block, ["Date", "Time Created"]),
            "level": _match_field(block, ["Level"]),
            "raw": block,
        }
        if any(event[key] for key in ("event_id", "provider", "time_created", "level")):
            events.append(event)
    return events


def _match_field(text: str, keys: list[str]) -> str:
    for key in keys:
        match = re.search(rf"^\s*{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""
