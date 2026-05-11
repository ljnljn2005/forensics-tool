import os
import locale
import struct
import subprocess
import uuid
from dataclasses import dataclass
from typing import Iterable, Protocol


DEFAULT_APP_EXTENSIONS = (
    ".html",
    ".htm",
    ".pdf",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".mp4",
    ".mp3",
    ".zip",
    ".docx",
    ".xlsx",
    ".pptx",
)


@dataclass(frozen=True)
class UserHive:
    username: str
    path: str


@dataclass(frozen=True)
class RegistryHives:
    software_hive: str | None
    user_hives: list[UserHive]


@dataclass(frozen=True)
class DefaultAppAssociation:
    username: str
    extension: str
    prog_id: str
    hash_value: str
    command: str
    hive_path: str


@dataclass(frozen=True)
class RegistrySearchItem:
    plugin: str
    name: str
    registry_path: str
    description: str = ""


class HiveLoader(Protocol):
    def query_values(self, hive_path: str, subkey: str) -> dict[str, str]:
        ...


class AutoHiveLoader:
    """Prefer direct offline hive parsing; fall back to reg.exe if parsing is unsupported."""

    def __init__(self):
        self.file_loader = FileHiveLoader()
        self.reg_loader = RegExeHiveLoader()

    def query_values(self, hive_path: str, subkey: str) -> dict[str, str]:
        try:
            return self.file_loader.query_values(hive_path, subkey)
        except Exception as file_error:
            try:
                return self.reg_loader.query_values(hive_path, subkey)
            except Exception as reg_error:
                raise RuntimeError(f"直接解析失败: {file_error}; reg.exe 读取失败: {reg_error}") from reg_error


class FileHiveLoader:
    """Minimal read-only parser for offline Windows registry hive files."""

    def query_values(self, hive_path: str, subkey: str) -> dict[str, str]:
        hive = _RegistryHiveFile(hive_path)
        try:
            try:
                key = hive.open_key(subkey)
            except KeyError:
                return {}
            return hive.values(key)
        finally:
            hive.close()


class RegExeHiveLoader:
    """Read offline registry hives through Windows reg.exe temporary mounts."""

    def query_values(self, hive_path: str, subkey: str) -> dict[str, str]:
        if os.name != "nt":
            raise RuntimeError("离线注册表查询需要在 Windows 上运行")
        if not os.path.exists(hive_path):
            raise FileNotFoundError(hive_path)

        mount_name = f"ForensicsTool_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        mount_root = f"HKU\\{mount_name}"
        load = subprocess.run(
            ["reg", "load", mount_root, hive_path],
            capture_output=True,
        )
        if load.returncode != 0:
            raise RuntimeError((_decode_reg_output(load.stderr or load.stdout) or "reg load failed").strip())

        try:
            query = subprocess.run(
                ["reg", "query", f"{mount_root}\\{subkey}"],
                capture_output=True,
            )
            if query.returncode != 0:
                return {}
            return parse_reg_query_values(_decode_reg_output(query.stdout))
        finally:
            subprocess.run(
                ["reg", "unload", mount_root],
                capture_output=True,
            )


def find_windows_hives(mapping_path: str) -> RegistryHives:
    root = os.path.abspath(os.path.expanduser(os.path.expandvars(mapping_path or "")))
    software_hive = os.path.join(root, "Windows", "System32", "config", "SOFTWARE")
    if not os.path.exists(software_hive):
        software_hive = None

    users_dir = os.path.join(root, "Users")
    user_hives: list[UserHive] = []
    if os.path.isdir(users_dir):
        for username in sorted(os.listdir(users_dir)):
            if username.lower() in {"default", "public", "all users", "default user"}:
                continue
            hive_path = os.path.join(users_dir, username, "NTUSER.DAT")
            if os.path.exists(hive_path):
                user_hives.append(UserHive(username=username, path=hive_path))

    return RegistryHives(software_hive=software_hive, user_hives=user_hives)


def parse_reg_query_values(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("HKEY_"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[1].startswith("REG_"):
            continue
        name, _kind, value = parts
        if name in {"(默认)", "(Default)"}:
            name = "(Default)"
        values[name] = value.strip()
    return values


def _decode_reg_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    encodings = [
        locale.getpreferredencoding(False),
        "mbcs",
        "gbk",
        "cp936",
        "utf-8",
    ]
    for encoding in encodings:
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


class _RegistryHiveFile:
    BASE_BLOCK_SIZE = 4096

    def __init__(self, path: str):
        self.path = path
        self._fh = open(path, "rb")
        header = self._read_at(0, self.BASE_BLOCK_SIZE)
        if header[:4] != b"regf":
            raise ValueError("不是有效的 Windows registry hive 文件")
        self.root_offset = struct.unpack_from("<I", header, 0x24)[0]

    def close(self):
        self._fh.close()

    def open_key(self, path: str):
        current = self._read_nk(self.root_offset)
        parts = [part for part in path.replace("/", "\\").split("\\") if part]
        for part in parts:
            child_offset = self._find_subkey(current, part)
            if child_offset is None:
                raise KeyError(path)
            current = self._read_nk(child_offset)
        return current

    def values(self, key: dict) -> dict[str, str]:
        count = key["value_count"]
        if count <= 0 or key["value_list_offset"] in (0xFFFFFFFF, 0xFFFFFFFE):
            return {}
        offsets = self._read_value_list(key["value_list_offset"], count)
        values: dict[str, str] = {}
        for offset in offsets:
            value = self._read_vk(offset)
            values[value["name"]] = value["value"]
        return values

    def _find_subkey(self, key: dict, name: str):
        for child_offset in self._subkey_offsets(key):
            child = self._read_nk(child_offset)
            if child["name"].lower() == name.lower():
                return child_offset
        return None

    def _subkey_offsets(self, key: dict) -> list[int]:
        if key["subkey_count"] <= 0 or key["subkey_list_offset"] in (0xFFFFFFFF, 0xFFFFFFFE):
            return []
        return self._read_subkey_list(key["subkey_list_offset"])

    def _read_subkey_list(self, offset: int) -> list[int]:
        data = self._read_cell_data(offset)
        signature = data[:2]
        if signature in (b"lf", b"lh"):
            count = struct.unpack_from("<H", data, 2)[0]
            return [struct.unpack_from("<I", data, 4 + i * 8)[0] for i in range(count)]
        if signature == b"li":
            count = struct.unpack_from("<H", data, 2)[0]
            return [struct.unpack_from("<I", data, 4 + i * 4)[0] for i in range(count)]
        if signature == b"ri":
            count = struct.unpack_from("<H", data, 2)[0]
            offsets: list[int] = []
            for i in range(count):
                nested = struct.unpack_from("<I", data, 4 + i * 4)[0]
                offsets.extend(self._read_subkey_list(nested))
            return offsets
        raise ValueError(f"不支持的子键列表类型: {signature!r}")

    def _read_value_list(self, offset: int, count: int) -> list[int]:
        data = self._read_cell_data(offset)
        return [struct.unpack_from("<I", data, i * 4)[0] for i in range(count)]

    def _read_nk(self, offset: int) -> dict:
        data = self._read_cell_data(offset)
        if data[:2] != b"nk":
            raise ValueError(f"不是 nk 单元: {offset:#x}")
        flags = struct.unpack_from("<H", data, 2)[0]
        name_len = struct.unpack_from("<H", data, 72)[0]
        raw_name = data[76:76 + name_len]
        name = raw_name.decode("ascii" if flags & 0x20 else "utf-16le", errors="replace")
        return {
            "name": name,
            "subkey_count": struct.unpack_from("<I", data, 20)[0],
            "subkey_list_offset": struct.unpack_from("<I", data, 28)[0],
            "value_count": struct.unpack_from("<I", data, 36)[0],
            "value_list_offset": struct.unpack_from("<I", data, 40)[0],
        }

    def _read_vk(self, offset: int) -> dict:
        data = self._read_cell_data(offset)
        if data[:2] != b"vk":
            raise ValueError(f"不是 vk 单元: {offset:#x}")
        name_len = struct.unpack_from("<H", data, 2)[0]
        raw_data_size = struct.unpack_from("<I", data, 4)[0]
        data_offset = struct.unpack_from("<I", data, 8)[0]
        value_type = struct.unpack_from("<I", data, 12)[0]
        flags = struct.unpack_from("<H", data, 16)[0]
        raw_name = data[20:20 + name_len]
        name = raw_name.decode("ascii" if flags & 0x01 else "utf-16le", errors="replace") if raw_name else "(Default)"
        raw_value = self._read_value_data(raw_data_size, data_offset)
        return {"name": name, "value": self._format_value(raw_value, value_type)}

    def _read_value_data(self, raw_size: int, data_offset: int) -> bytes:
        inline = bool(raw_size & 0x80000000)
        size = raw_size & 0x7FFFFFFF
        if size == 0:
            return b""
        if inline:
            return struct.pack("<I", data_offset)[:size]
        return self._read_cell_data(data_offset)[:size]

    def _format_value(self, data: bytes, value_type: int) -> str:
        if value_type in (1, 2):
            return data.decode("utf-16le", errors="replace").rstrip("\x00")
        if value_type == 4 and len(data) >= 4:
            return str(struct.unpack_from("<I", data, 0)[0])
        if value_type == 11 and len(data) >= 8:
            return str(struct.unpack_from("<Q", data, 0)[0])
        if value_type == 7:
            return "; ".join(part for part in data.decode("utf-16le", errors="replace").split("\x00") if part)
        return data.hex(" ")

    def _read_cell_data(self, relative_offset: int) -> bytes:
        absolute = self.BASE_BLOCK_SIZE + relative_offset
        header = self._read_at(absolute, 4)
        if len(header) != 4:
            raise ValueError(f"单元偏移越界: {relative_offset:#x}")
        size = struct.unpack("<i", header)[0]
        cell_size = abs(size)
        if cell_size < 4:
            raise ValueError(f"非法单元大小: {cell_size}")
        return self._read_at(absolute + 4, cell_size - 4)

    def _read_at(self, offset: int, size: int) -> bytes:
        self._fh.seek(offset)
        return self._fh.read(size)



def extract_registry_search_items(plugins_data: dict) -> list[RegistrySearchItem]:
    items: list[RegistrySearchItem] = []
    for plugin_name, plugin_data in (plugins_data.items() if isinstance(plugins_data, dict) else []):
        description = ""
        blocks = plugin_data
        if isinstance(plugin_data, dict):
            blocks = plugin_data.get("blocks", [])
            description = plugin_data.get("description", "") or ""

        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            cmd = (block.get("cmd") or "").strip()
            btype = block.get("type") or ""
            module = (block.get("module") or "").lower()
            if not cmd:
                continue
            is_registry_type = "注册表" in btype or "registry" in btype.lower()
            is_registry_path = _looks_like_registry_path(cmd)
            if module == "windows" and (is_registry_type or is_registry_path):
                items.append(
                    RegistrySearchItem(
                        plugin=plugin_name,
                        name=block.get("name", "") or cmd,
                        registry_path=cmd,
                        description=block.get("description", "") or description,
                    )
                )
    return items


def query_registry_path_report(
    mapping_path: str,
    registry_path: str,
    hive_loader: HiveLoader | None = None,
    hives: RegistryHives | None = None,
) -> str:
    if not registry_path.strip():
        return "错误: 注册表路径为空。"
    if hives is None and (not mapping_path or not os.path.exists(mapping_path)):
        return "错误: 映射路径不存在，请先在主页保存有效的 Windows 映射路径。"

    loader = hive_loader or AutoHiveLoader()
    discovered = hives or find_windows_hives(mapping_path)
    targets = _resolve_registry_targets(discovered, registry_path)
    lines = ["注册表路径查找", f"映射路径: {mapping_path}", f"目标路径: {registry_path}", ""]

    if not targets:
        lines.append("暂不支持该根键，当前支持 HKCU/HKEY_CURRENT_USER、HKLM\\SOFTWARE、HKCR。")
        return "\n".join(lines)

    found = False
    for label, hive_path, subkey in targets:
        if not hive_path:
            lines.append(f"[{label}] hive 未找到")
            continue
        try:
            values = loader.query_values(hive_path, subkey)
        except Exception as exc:
            lines.append(f"[{label}] 查询失败: {exc}")
            continue
        if not values:
            lines.append(f"[{label}] 未找到值")
            continue
        found = True
        lines.append(f"[{label}]")
        lines.append(f"Hive: {hive_path}")
        lines.append(f"Subkey: {subkey}")
        for name, value in values.items():
            lines.append(f"- {name}: {value}")
        lines.append("")

    if not found:
        lines.append("未找到匹配的注册表值。")
    return "\n".join(lines).rstrip()


def get_default_app_associations(
    mapping_path: str,
    extensions: Iterable[str] = DEFAULT_APP_EXTENSIONS,
    hive_loader: HiveLoader | None = None,
    hives: RegistryHives | None = None,
) -> list[DefaultAppAssociation]:
    rows, _errors = _collect_default_app_associations(
        mapping_path,
        extensions=extensions,
        hive_loader=hive_loader,
        hives=hives,
    )
    return rows


def _collect_default_app_associations(
    mapping_path: str,
    extensions: Iterable[str] = DEFAULT_APP_EXTENSIONS,
    hive_loader: HiveLoader | None = None,
    hives: RegistryHives | None = None,
) -> tuple[list[DefaultAppAssociation], list[str]]:
    loader = hive_loader or AutoHiveLoader()
    discovered = hives or find_windows_hives(mapping_path)
    rows: list[DefaultAppAssociation] = []
    errors: list[str] = []

    for user_hive in discovered.user_hives:
        for extension in extensions:
            ext = extension if extension.startswith(".") else f".{extension}"
            subkey = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\UserChoice"
            try:
                values = loader.query_values(user_hive.path, subkey)
            except Exception as exc:
                errors.append(f"{user_hive.username} ({user_hive.path}) 读取失败: {exc}")
                break
            prog_id = values.get("ProgId", "")
            if not prog_id:
                continue

            command = _resolve_open_command(loader, discovered, user_hive, prog_id)
            rows.append(
                DefaultAppAssociation(
                    username=user_hive.username,
                    extension=ext,
                    prog_id=prog_id,
                    hash_value=values.get("Hash", ""),
                    command=command,
                    hive_path=user_hive.path,
                )
            )

    return rows, errors


def lookup_default_apps_report(mapping_path: str) -> str:
    if not mapping_path or not os.path.exists(mapping_path):
        return "错误: 映射路径不存在，请先在主页保存有效的 Windows 映射路径。"

    hives = find_windows_hives(mapping_path)
    return build_default_apps_report(mapping_path, hives=hives)


def build_default_apps_report(
    mapping_path: str,
    hives: RegistryHives,
    hive_loader: HiveLoader | None = None,
) -> str:
    lines = [
        "Windows 注册表默认应用查找",
        f"映射路径: {mapping_path}",
        f"用户 hive 数量: {len(hives.user_hives)}",
        f"SOFTWARE hive: {hives.software_hive or '未找到'}",
        "",
    ]
    if not hives.user_hives:
        lines.append("未找到 Users/*/NTUSER.DAT，无法读取用户默认应用关联。")
        return "\n".join(lines)

    rows, errors = _collect_default_app_associations(
        mapping_path,
        hives=hives,
        hive_loader=hive_loader,
    )
    if errors:
        lines.append("注册表读取失败，当前没有得到可靠结果。")
        lines.append("读取方式: reg.exe load/query/unload 离线 hive。")
        lines.append("常见原因: 当前进程缺少 SeRestorePrivilege/管理员权限，或映像挂载为只读/受限。")
        lines.append("")
        lines.extend(f"- {error}" for error in errors)
        return "\n".join(lines)

    lines.append(format_default_app_associations(rows))
    return "\n".join(lines)


def _looks_like_registry_path(value: str) -> bool:
    upper = value.strip().upper()
    return upper.startswith(
        (
            "HKCU\\",
            "HKEY_CURRENT_USER\\",
            "HKLM\\",
            "HKEY_LOCAL_MACHINE\\",
            "HKCR\\",
            "HKEY_CLASSES_ROOT\\",
        )
    )


def _resolve_registry_targets(hives: RegistryHives, registry_path: str) -> list[tuple[str, str | None, str]]:
    normalized = registry_path.strip().replace("/", "\\")
    upper = normalized.upper()

    for prefix in ("HKEY_CURRENT_USER\\", "HKCU\\"):
        if upper.startswith(prefix):
            subkey = normalized[len(prefix):]
            return [(user.username, user.path, subkey) for user in hives.user_hives]

    for prefix in ("HKEY_LOCAL_MACHINE\\SOFTWARE\\", "HKLM\\SOFTWARE\\"):
        if upper.startswith(prefix):
            subkey = "Software\\" + normalized[len(prefix):]
            return [("HKLM\\SOFTWARE", hives.software_hive, subkey)]

    for prefix in ("HKEY_CLASSES_ROOT\\", "HKCR\\"):
        if upper.startswith(prefix):
            subkey = "Classes\\" + normalized[len(prefix):]
            return [("HKCR", hives.software_hive, subkey)]

    return []


def format_default_app_associations(rows: list[DefaultAppAssociation]) -> str:
    if not rows:
        return (
            "未找到默认应用关联。\n"
            "提示: Windows 10/11 的默认应用通常保存在用户 NTUSER.DAT 的 "
            "Explorer\\FileExts\\.<扩展名>\\UserChoice 下；如果当前进程没有加载 hive 的权限，也可能没有结果。"
        )

    lines = ["默认应用关联:"]
    for row in rows:
        lines.append(f"- 用户: {row.username}")
        lines.append(f"  扩展名: {row.extension}")
        lines.append(f"  ProgID: {row.prog_id}")
        if row.command:
            lines.append(f"  打开命令: {row.command}")
        if row.hash_value:
            lines.append(f"  Hash: {row.hash_value}")
        lines.append(f"  Hive: {row.hive_path}")
    return "\n".join(lines)


def _resolve_open_command(
    loader: HiveLoader,
    hives: RegistryHives,
    user_hive: UserHive,
    prog_id: str,
) -> str:
    user_subkey = rf"Software\Classes\{prog_id}\shell\open\command"
    software_subkey = rf"Classes\{prog_id}\shell\open\command"

    for hive_path, subkey in (
        (user_hive.path, user_subkey),
        (hives.software_hive, software_subkey),
    ):
        if not hive_path:
            continue
        try:
            values = loader.query_values(hive_path, subkey)
        except Exception:
            values = {}
        command = values.get("(Default)", "")
        if command:
            return command
    return ""
