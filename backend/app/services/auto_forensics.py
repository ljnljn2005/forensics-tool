from __future__ import annotations

import datetime
import os
import struct
from collections import defaultdict

from backend.app.services.extractor import _load_plugin_payload, list_extractor_entries
from backend.app.services.log_analysis import get_log_detail, list_logs
from backend.app.services.plugins import is_android_auto_plugin
from src.extractor import execute_command_for_ai
from src.windows_registry import (
    AutoHiveLoader,
    lookup_default_apps_report,
    query_registry_path_report,
)


def _looks_like_registry_path(value: str) -> bool:
    upper = value.strip().upper()
    return upper.startswith(
        ("HKCU\\", "HKEY_CURRENT_USER\\", "HKLM\\", "HKEY_LOCAL_MACHINE\\", "HKCR\\", "HKEY_CLASSES_ROOT\\")
    )


def _collect_registry_plugin_entries(module: str) -> list[dict]:
    payload = _load_plugin_payload()
    entries: list[dict] = []
    for group_name, group_data in payload.items():
        blocks = group_data.get("blocks", []) if isinstance(group_data, dict) else group_data
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            block_module = (block.get("module") or "").lower()
            cmd = str(block.get("cmd", "")).strip()
            if block_module and block_module != module:
                continue
            if not _looks_like_registry_path(cmd):
                continue
            entries.append({
                "group": group_name,
                "plugin": group_name,
                "name": block.get("name", "") or cmd,
                "cmd": cmd,
                "type": "注册表",
                "module": block_module or module,
            })
    return entries


def _collect_file_entries(module: str) -> list[dict]:
    catalog = list_extractor_entries(module)
    return catalog.get("entries", [])


# ─── Phase 1: file extraction ───────────────────────────────────────

def run_file_extraction(mapping_path: str, module: str) -> dict:
    """Run plugin-based file extraction. Returns matched_groups + metadata."""
    file_entries = _collect_file_entries(module)
    grouped = defaultdict(list)
    for entry in file_entries:
        cmd = entry.get("cmd", "")
        btype = entry.get("type", "")
        try:
            result = execute_command_for_ai(cmd, base_path=mapping_path, btype=btype)
        except Exception as exc:
            result = f"执行失败: {exc}"
        grouped[entry["group"]].append({
            **entry,
            "resolved_path": cmd,
            "result": result,
        })

    matched_groups = [
        {"group_name": group_name, "entries": group_entries}
        for group_name, group_entries in grouped.items()
    ]
    total = sum(len(g["entries"]) for g in matched_groups)
    return {
        "phase": "files",
        "mapping_path": mapping_path,
        "module": module,
        "matched_groups": matched_groups,
        "total_entries": total,
    }


# ─── Phase 2: registry scan (Windows only) ──────────────────────────

def run_registry_analysis(mapping_path: str) -> dict:
    """Run comprehensive registry scans. Returns matched_groups + metadata."""
    entries: list[dict] = []

    # 1. Default apps
    try:
        text = lookup_default_apps_report(mapping_path)
        entries.append({
            "group": "注册表分析", "plugin": "注册表分析",
            "name": "默认应用关联", "cmd": "default_apps",
            "type": "注册表", "module": "windows", "result": text,
        })
    except Exception as exc:
        entries.append({
            "group": "注册表分析", "plugin": "注册表分析",
            "name": "默认应用关联", "cmd": "default_apps",
            "type": "注册表", "module": "windows", "result": f"扫描失败: {exc}",
        })

    # 2. Common system paths
    common_paths = [
        ("HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run", "开机启动 (HKLM)"),
        ("HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce", "开机启动一次 (HKLM)"),
        ("HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon", "Winlogon"),
        ("HKLM\\SOFTWARE\\Microsoft\\Active Setup\\Installed Components", "Active Setup 组件"),
        ("HKLM\\SYSTEM\\CurrentControlSet\\Services", "服务列表 (首50项)"),
        ("HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall", "已安装程序列表"),
    ]
    for reg_path, label in common_paths:
        try:
            text = query_registry_path_report(mapping_path, reg_path)
            entries.append({
                "group": "注册表分析", "plugin": "注册表分析",
                "name": label, "cmd": reg_path,
                "type": "注册表", "module": "windows", "result": text,
            })
        except Exception as exc:
            entries.append({
                "group": "注册表分析", "plugin": "注册表分析",
                "name": label, "cmd": reg_path,
                "type": "注册表", "module": "windows", "result": f"查询失败: {exc}",
            })

    # 3. Plugin-defined registry paths
    for entry in _collect_registry_plugin_entries("windows"):
        try:
            entry["result"] = query_registry_path_report(mapping_path, entry["cmd"])
        except Exception as exc:
            entry["result"] = f"查询失败: {exc}"
        entries.append(entry)

    return {
        "phase": "registry",
        "mapping_path": mapping_path,
        "module": "windows",
        "matched_groups": [
            {"group_name": "注册表分析", "entries": entries},
        ],
        "total_entries": len(entries),
    }


# ─── Phase 3: log scan (Windows only) ───────────────────────────────

def run_log_analysis(mapping_path: str, module: str = "windows") -> dict:
    """Discover log files and read content. Returns matched_groups + metadata."""
    scan_result = list_logs(mapping_path, module)
    entries: list[dict] = []
    for log_entry in scan_result.get("entries", []):
        detail = get_log_detail(log_entry)
        text = detail.get("text", "")
        events = detail.get("events", [])
        event_summary = ""
        if events:
            event_summary = "\n".join(
                f"  [{e.get('event_id','')}] {e.get('provider','')} @ {e.get('time_created','')} [{e.get('level','')}]"
                for e in events[:20]
            )
            if len(events) > 20:
                event_summary += f"\n  ... 还有 {len(events) - 20} 条事件"

        entries.append({
            "group": "日志分析", "plugin": "日志分析",
            "name": log_entry.get("name", ""),
            "cmd": log_entry.get("display_path", log_entry.get("path", "")),
            "type": "日志", "module": "windows",
            "result": text[:5000] if not event_summary else event_summary,
            "log_meta": {
                "category": log_entry.get("category", ""),
                "size": log_entry.get("size", 0),
                "event_count": len(events),
            },
        })

    return {
        "phase": "logs",
        "mapping_path": mapping_path,
        "module": "windows",
        "matched_groups": [
            {"group_name": "日志分析", "entries": entries},
        ],
        "total_entries": len(entries),
    }


def _query_hive_value(loader, hive_path: str, subkey: str, value_name: str) -> str:
    """Query a single value from a registry hive, returning empty string on failure."""
    try:
        values = loader.query_values(hive_path, subkey)
        return values.get(value_name, "")
    except Exception:
        return ""


def _parse_install_timestamp(raw: str) -> str:
    """Convert Unix timestamp (DWORD) to readable datetime."""
    try:
        ts = int(raw)
        dt = datetime.datetime.utcfromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OverflowError):
        return raw


def run_system_info_scan(mapping_path: str) -> dict:
    """Phase 0: Extract Windows system information from registry hives."""
    root = os.path.abspath(mapping_path)
    if not root or not os.path.exists(root):
        return {
            "phase": "system-info", "mapping_path": mapping_path, "module": "windows",
            "matched_groups": [], "total_entries": 0,
        }

    software_hive = os.path.join(root, "Windows", "System32", "config", "SOFTWARE")
    system_hive = os.path.join(root, "Windows", "System32", "config", "SYSTEM")
    loader = AutoHiveLoader()

    # ─── Hive status ───
    has_software = os.path.isfile(software_hive)
    has_system = os.path.isfile(system_hive)

    # ─── SOFTWARE: Windows NT CurrentVersion ───
    nt_values: dict[str, str] = {}
    if has_software:
        try:
            nt_values = loader.query_values(software_hive, r"Microsoft\Windows NT\CurrentVersion")
        except Exception:
            nt_values = {}

    # ─── SYSTEM: control set ───
    control_set = "ControlSet001"
    if has_system:
        try:
            sel = loader.query_values(system_hive, "Select")
            cur = sel.get("Current", "1")
            control_set = f"ControlSet00{cur}"
        except Exception:
            control_set = "ControlSet001"

    # ─── SYSTEM hive queries ───
    sys_timezone: dict[str, str] = {}
    sys_computer: dict[str, str] = {}
    sys_ntp: dict[str, str] = {}
    sys_tcpip: dict[str, str] = {}
    sys_filesys: dict[str, str] = {}
    if has_system:
        try:
            sys_timezone = loader.query_values(system_hive, rf"{control_set}\Control\TimeZoneInformation")
        except Exception:
            pass
        try:
            sys_computer = loader.query_values(system_hive, rf"{control_set}\Control\ComputerName\ComputerName")
        except Exception:
            pass
        try:
            sys_ntp = loader.query_values(system_hive, rf"{control_set}\Services\W32Time\Parameters")
        except Exception:
            pass
        try:
            sys_tcpip = loader.query_values(system_hive, rf"{control_set}\Services\Tcpip\Parameters")
        except Exception:
            pass
        try:
            sys_filesys = loader.query_values(system_hive, rf"{control_set}\Control\FileSystem")
        except Exception:
            pass

    # ─── Map registry values to fields ───
    product_name = nt_values.get("ProductName", "")
    edition_id = nt_values.get("EditionID", "")
    current_build = nt_values.get("CurrentBuild", nt_values.get("CurrentBuildNumber", ""))
    ubr = nt_values.get("UBR", "")
    display_version = nt_values.get("DisplayVersion", "")
    install_date_raw = nt_values.get("InstallDate", "")
    install_date = _parse_install_timestamp(install_date_raw)

    # C_VERSION: prefer CurrentMajorVersionNumber (DWORD, exists on Win10+), else map "6.3"→"10"
    c_ver_raw = nt_values.get("CurrentMajorVersionNumber", "")
    if c_ver_raw and c_ver_raw.isdigit():
        c_version = c_ver_raw
    else:
        nt_ver = nt_values.get("CurrentVersion", "")
        # Map NT version → Windows version
        nt_map = {"6.3": "10", "6.2": "8", "6.1": "7", "6.0": "Vista", "5.2": "Server 2003/XP x64", "5.1": "XP"}
        c_version = nt_map.get(nt_ver, nt_ver)

    # VERSION: append UBR if available
    full_version = current_build
    if ubr and ubr.isdigit():
        full_version = f"{current_build}.{ubr}"
    elif ubr:
        full_version = f"{current_build} (UBR: {ubr})"

    # Determine OS_TYPE
    os_type = "Windows Client"
    if "Server" in product_name:
        os_type = "Windows Server"

    # Determine OS_NAME (marketing name)
    os_name = product_name
    if display_version:
        os_name = f"{product_name} ({display_version})"
    build_num = current_build
    if build_num.isdigit():
        b = int(build_num)
        if b >= 22000:
            os_name = f"Windows 11 {display_version}" if display_version else f"Windows 11 (build {build_num})"
        elif b >= 10240:
            os_name = f"Windows 10 {display_version}" if display_version else f"Windows 10 (build {build_num})"

    # ─── Bitness: check multiple indicators ───
    bitness = ""
    if has_software:
        prog_x86 = _query_hive_value(loader, software_hive, r"Microsoft\Windows NT\CurrentVersion", "ProgramFilesDir (x86)")
        prog_w64 = _query_hive_value(loader, software_hive, r"Microsoft\Windows NT\CurrentVersion", "ProgramW6432Dir")
        if prog_w64 or prog_x86:
            bitness = "64 位"
        else:
            bitness = "32 位"
    if has_system and bitness != "64 位":
        # also check PROCESSOR_ARCHITECTURE in system environment
        try:
            env_vals = loader.query_values(system_hive, rf"{control_set}\Control\Session Manager\Environment")
            proc_arch = env_vals.get("PROCESSOR_ARCHITECTURE", "")
            if proc_arch.upper() in ("AMD64", "IA64", "ARM64"):
                bitness = "64 位"
            elif proc_arch.upper() == "X86":
                bitness = "32 位"
        except Exception:
            pass

    # CPU from SOFTWARE hive HKLM\HARDWARE is volatile offline.
    # But we can try SAM\SAM\Domains\Account or setup log later.
    cpu_val = "(离线 hive 无法获取)"
    memory_val = "(离线 hive 无法获取)"
    firmware_val = "(离线 hive 无法获取)"
    firmware_ver_val = "(离线 hive 无法获取)"

    # Last shutdown from SYSTEM\Control\Windows\ShutdownTime (REG_BINARY FILETIME)
    last_shutdown = ""
    if has_system:
        try:
            shutdown_val = _query_hive_value(loader, system_hive, rf"{control_set}\Control\Windows", "ShutdownTime")
            if shutdown_val:
                # _format_value returns REG_BINARY as hex with spaces: "de 94 0a 6c 5b c3 db 01"
                # FILETIME = two LE 32-bit ints: dwLowDateTime, dwHighDateTime
                clean_hex = shutdown_val.replace(" ", "").replace("\x00", "")
                raw_bytes = bytes.fromhex(clean_hex)
                if len(raw_bytes) >= 8:
                    dw_low, dw_high = struct.unpack("<II", raw_bytes[:8])
                    ft = (dw_high << 32) | dw_low
                    if ft > 0:
                        us = ft // 10
                        dt = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=us)
                        last_shutdown = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    else:
                        last_shutdown = shutdown_val[:50]
                else:
                    last_shutdown = shutdown_val[:50]
        except Exception:
            pass
    if not last_shutdown:
        last_shutdown = "(需从事件日志 Event ID 6006 获取)"

    # NtfsDisableLastAccessUpdate: DWORD, 0/1 or 0x8000000x flags
    ntfs_raw = sys_filesys.get("NtfsDisableLastAccessUpdate", "")
    ntfs_last_access = "(未找到)"
    if ntfs_raw:
        try:
            ntfs_int = int(ntfs_raw)
            if ntfs_int & 0x80000000:
                # top bit = global policy flag
                if ntfs_int & 1:
                    ntfs_last_access = "已禁用 (Disabled)"
                else:
                    ntfs_last_access = "已启用 (Enabled)"
            elif ntfs_int == 1:
                ntfs_last_access = "已禁用 (Disabled)"
            elif ntfs_int == 0:
                ntfs_last_access = "已启用 (Enabled)"
            else:
                ntfs_last_access = f"已启用 (Raw: {ntfs_raw})"
        except ValueError:
            ntfs_last_access = f"值: {ntfs_raw}"

    # Build field list
    fields = [
        ("MATERIALS_NAME", "操作系统名称", product_name),
        ("OS_TYPE", "操作系统类型", os_type),
        ("OS_NAME", "操作系统版本", os_name),
        ("OS_BITNESS", "操作系统位数", bitness or "(未找到)"),
        ("OS_TIME ZONE", "系统时区", sys_timezone.get("TimeZoneKeyName", "(未找到)")),
        ("INSTALL TIME", "安装时间", install_date),
        ("PRODUCT_KEY", "产品密钥", (nt_values.get("DigitalProductId", "")[:60].replace(" ", "") + "...") if len(nt_values.get("DigitalProductId", "")) > 60 else nt_values.get("DigitalProductId", "(未找到)" if "DigitalProductId" not in nt_values else nt_values.get("DigitalProductId", "")).replace(" ", "")),
        ("RELEASE_ID", "发行ID", edition_id or display_version or "(未找到)"),
        ("OS_PRODUCT_ID", "产品ID", nt_values.get("ProductId", "(未找到)")),
        ("C_VERSION", "当前版本号", c_version),
        ("VERSION", "当前Build版本号", full_version),
        ("CPU", "处理器", cpu_val),
        ("MEMORY", "内存", memory_val),
        ("COMPUTER_NAME", "设备名称", sys_computer.get("ComputerName", "(未找到)")),
        ("FIRMWARE", "固件", firmware_val),
        ("FIRMWARE_VERSION", "固件版本", firmware_ver_val),
        ("NTP SERVER", "自动校准系统时间的服务器地址", sys_ntp.get("NtpServer", "(未设置)")),
        ("SYSTEM_PATH", "系统根路径", nt_values.get("SystemRoot", "(未找到)")),
        ("PATH_NAME", "路径名", nt_values.get("ProgramFilesDir", nt_values.get("ProgramW6432Dir", "(未找到)"))),
        ("LAST_LOGOUT_TIME", "最后一次正常关机时间", last_shutdown),
        ("NTFS_LAST_ACCESS_UPDATE_ENABLE", "最后访问时间已启用", ntfs_last_access),
        ("REGISTER_OWNER", "注册所有者", nt_values.get("RegisteredOwner", "(未设置)")),
        ("PC_GROUP", "工作组", sys_tcpip.get("Domain", sys_tcpip.get("NV Domain", "(未找到)"))),
    ]

    lines = []
    for eng, chn, val in fields:
        lines.append(f"{chn}({eng}): {val}")

    result_text = "\n".join(lines)

    return {
        "phase": "system-info",
        "mapping_path": mapping_path,
        "module": "windows",
        "matched_groups": [
            {
                "group_name": "系统信息",
                "entries": [
                    {
                        "group": "系统信息",
                        "plugin": "系统信息",
                        "name": "操作系统信息",
                        "cmd": "system_info",
                        "type": "系统信息",
                        "module": "windows",
                        "result": result_text,
                    }
                ],
            }
        ],
        "total_entries": 1,
    }
