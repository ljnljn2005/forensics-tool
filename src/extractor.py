import glob
import json
import os
import re
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from .constants import PLUGINS_DIR, get_app_settings


_LAST_TRIED_PATHS: list | None = None
MODULE_LABELS = {
    "windows": "Windows",
    "linux": "Linux",
    "android": "Android",
    "ios": "iOS",
}


PACKAGE_NAME_RE = re.compile(r"(?:^|[\\/])((?:[A-Za-z][A-Za-z0-9_]*\.)+[A-Za-z0-9_]+)(?=[\\/]|$)")
PACKAGE_TOKEN_RE = re.compile(r"\b((?:[A-Za-z][A-Za-z0-9_]*\.)+[A-Za-z0-9_]+)\b")
ANDROID_SYSTEM_ROOT_DEFAULTS = [
    "/data/user/0",
    "/data/data",
    "/data/user_de/0",
    "/data_mirror/data_ce/null/0",
]


def extract_android_package_name(text: str) -> str:
    if not text:
        return ""
    match = PACKAGE_NAME_RE.search(text)
    return match.group(1) if match else ""


def collect_android_template_packages(entries: list[dict]) -> dict[str, list[dict]]:
    packages: dict[str, list[dict]] = {}
    for entry in entries:
        if (entry.get("module") or "").lower() != "android":
            continue
        package_name = str(entry.get("package_name", "")).strip() or extract_android_package_name(entry.get("cmd", ""))
        if not package_name:
            continue
        packages.setdefault(package_name, []).append(entry)
    return packages


def collect_android_installed_packages(base_path: str) -> list[str]:
    if not base_path or not os.path.exists(base_path):
        return []

    packages: set[str] = set()

    def _read_package_lines(path: str):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    yield line.strip()
        except OSError:
            return

    def _read_packages_xml(path: str):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except (OSError, ET.ParseError):
            return set()

        discovered: set[str] = set()
        for package_node in root.iter("package"):
            package_name = str(package_node.attrib.get("name", "")).strip()
            if package_name and PACKAGE_TOKEN_RE.fullmatch(package_name):
                discovered.add(package_name)
        return discovered

    for rel_path in (
        os.path.join("data", "system", "packages.list"),
        os.path.join("system", "packages.list"),
    ):
        full_path = os.path.join(base_path, rel_path)
        if not os.path.isfile(full_path):
            continue
        for line in _read_package_lines(full_path):
            packages.update(PACKAGE_TOKEN_RE.findall(line))

    for rel_path in (
        os.path.join("data", "system", "packages.xml"),
        os.path.join("system", "packages.xml"),
    ):
        full_path = os.path.join(base_path, rel_path)
        if os.path.isfile(full_path):
            packages.update(_read_packages_xml(full_path))

    for rel_dir in (
        os.path.join("data", "data"),
        os.path.join("data", "user", "0"),
        os.path.join("data", "user_de", "0"),
        os.path.join("data_mirror", "data_ce", "null", "0"),
        "data",
    ):
        full_dir = os.path.join(base_path, rel_dir)
        if not os.path.isdir(full_dir):
            continue
        try:
            for name in os.listdir(full_dir):
                package_name = extract_android_package_name(name)
                if package_name:
                    packages.add(package_name)
        except OSError:
            continue

    return sorted(packages)


def get_android_system_roots() -> list[str]:
    settings = get_app_settings()
    configured = settings.get("android_system_roots", [])
    roots: list[str] = []
    if isinstance(configured, str):
        configured = [line.strip() for line in configured.splitlines() if line.strip()]
    if isinstance(configured, list):
        roots.extend(str(item).strip() for item in configured if str(item).strip())

    merged: list[str] = []
    for root in roots + ANDROID_SYSTEM_ROOT_DEFAULTS:
        normalized = "/" + root.strip().replace("\\", "/").strip("/")
        if normalized not in merged:
            merged.append(normalized)
    return merged


def extract_android_plugin_relative_path(cmd: str, package_name: str) -> str:
    normalized = str(cmd or "").strip().replace("\\", "/")
    if not normalized:
        return ""

    if package_name:
        package_marker = f"/{package_name}"
        marker_index = normalized.find(package_marker)
        if marker_index >= 0:
            suffix = normalized[marker_index + len(package_marker):]
            return "/" + suffix.strip("/") if suffix.strip("/") else ""

    for root in get_android_system_roots():
        if normalized == root:
            return ""
        if normalized.startswith(root + "/"):
            remainder = normalized[len(root):]
            package_marker = f"/{package_name}" if package_name else ""
            if package_marker and remainder.startswith(package_marker):
                suffix = remainder[len(package_marker):]
                return "/" + suffix.strip("/") if suffix.strip("/") else ""
            return "/" + remainder.strip("/") if remainder.strip("/") else ""

    return "/" + normalized.strip("/") if normalized.strip("/") else ""


def resolve_android_entry_candidates(mapping_path: str, package_name: str, cmd: str) -> list[str]:
    if not mapping_path or not package_name:
        return []

    mapping_root = os.path.normpath(mapping_path)
    package_segment = package_name.replace(".", os.sep)
    relative_suffix = extract_android_plugin_relative_path(cmd, package_name)
    suffix_segments = [segment for segment in relative_suffix.strip("/").split("/") if segment]

    candidates: list[str] = []
    for system_root in get_android_system_roots():
        system_segments = [segment for segment in system_root.strip("/").split("/") if segment]
        candidate = os.path.join(mapping_root, *system_segments, package_name, *suffix_segments)
        alt_candidate = os.path.join(mapping_root, *system_segments, package_segment, *suffix_segments)
        for path in (candidate, alt_candidate):
            normalized = os.path.normpath(path)
            if normalized not in candidates:
                candidates.append(normalized)
    return candidates


def resolve_mapped_path_candidates(base_path: str | None, target_path: str) -> list[str]:
    if not target_path:
        return []

    normalized = target_path.replace("/", os.sep).replace("\\", os.sep)
    candidates: list[str] = []

    if base_path and not os.path.isabs(target_path):
        candidates.extend(
            [
                os.path.join(base_path, target_path),
                os.path.join(base_path, normalized),
                os.path.join(base_path, target_path.lstrip("/\\")),
                normalized,
                target_path,
            ]
        )
    else:
        candidates.extend([target_path, normalized])
        if base_path and target_path.startswith(("/", "\\")):
            candidates.append(os.path.join(base_path, target_path.lstrip("/\\")))

    deduped: list[str] = []
    for candidate in candidates:
        normalized_candidate = os.path.normpath(candidate)
        if normalized_candidate not in deduped:
            deduped.append(normalized_candidate)
    return deduped


def _archive_member_from_target(base_path: str, target_path: str) -> str:
    base_norm = os.path.normpath(base_path)
    target_norm = os.path.normpath(target_path)
    if target_norm.startswith(base_norm):
        member = target_norm[len(base_norm):].lstrip("/\\")
    else:
        member = str(target_path).lstrip("/\\")
    return member.replace("\\", "/")


def load_mapped_file_bytes(target_path: str, base_path: str | None = None) -> tuple[bytes, str, list[str]]:
    tried_paths = resolve_mapped_path_candidates(base_path, target_path)

    for try_path in tried_paths:
        if os.path.isfile(try_path):
            with open(try_path, "rb") as handle:
                return handle.read(), try_path, tried_paths

    if base_path and os.path.isfile(base_path):
        member_candidates = [_archive_member_from_target(base_path, target_path)]
        member_candidates.extend(_archive_member_from_target(base_path, item) for item in tried_paths)
        deduped_members: list[str] = []
        for member in member_candidates:
            member = member.strip("/")
            if member and member not in deduped_members:
                deduped_members.append(member)

        try:
            if tarfile.is_tarfile(base_path):
                with tarfile.open(base_path, "r") as archive:
                    for member in deduped_members:
                        try:
                            file_obj = archive.extractfile(member)
                        except KeyError:
                            file_obj = None
                        if file_obj:
                            return file_obj.read(), f"{base_path}:{member}", tried_paths
        except Exception:
            pass

        try:
            if zipfile.is_zipfile(base_path):
                with zipfile.ZipFile(base_path, "r") as archive:
                    names = set(archive.namelist())
                    for member in deduped_members:
                        if member in names:
                            return archive.read(member), f"{base_path}:{member}", tried_paths
        except Exception:
            pass

    raise FileNotFoundError(f"target file not found: {target_path}")


def materialize_mapped_file(target_path: str, base_path: str | None = None, suffix: str = "") -> tuple[str, str, list[str]]:
    file_bytes, source_path, tried_paths = load_mapped_file_bytes(target_path, base_path=base_path)
    temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_handle.write(file_bytes)
        temp_handle.flush()
    finally:
        temp_handle.close()
    return temp_handle.name, source_path, tried_paths


def execute_command_for_ai(cmd: str, base_path: str | None = None, btype: str = "") -> str:
    """Read mapped files for extractor/search use, or fall back to running a local command."""
    try:
        if not base_path:
            try:
                base_path = get_app_settings().get("mapping_path")
            except Exception:
                base_path = base_path

        if btype and "文件" in btype and cmd:
            match = re.search(r'([A-Za-z]:[\\/][^\s;\'" ]+)|([\\/][^\s;\'" ]+)|([^\s;\'" ]+[\\/][^\s;\'" ]+)|([^\s;\'"]+\.[A-Za-z0-9_]+)', cmd)
            if match:
                fpath = match.group(0)
                normalized = fpath.replace("/", os.sep).replace("\\", os.sep)
                candidates: list[str] = []

                if base_path and not os.path.isabs(fpath):
                    candidates.extend(
                        [
                            os.path.join(base_path, fpath),
                            os.path.join(base_path, normalized),
                            os.path.join(base_path, fpath.lstrip("/\\")),
                            normalized,
                            fpath,
                        ]
                    )
                else:
                    candidates.extend([fpath, normalized])
                    if base_path and fpath.startswith(("/", "\\")):
                        candidates.append(os.path.join(base_path, fpath.lstrip("/\\")))

                tried = []
                for candidate in candidates:
                    try_path = os.path.normpath(candidate)
                    tried.append(try_path)

                    archive_output = _try_read_from_archive(base_path, try_path)
                    if archive_output is not None:
                        return archive_output

                    if os.path.isfile(try_path):
                        with open(try_path, "r", encoding="utf-8", errors="replace") as handle:
                            globals()["_LAST_TRIED_PATHS"] = [try_path]
                            return handle.read()
                    if os.path.isdir(try_path):
                        globals()["_LAST_TRIED_PATHS"] = [try_path]
                        return "目录列出: " + try_path + "\n" + "\n".join(sorted(os.listdir(try_path)))

                globals()["_LAST_TRIED_PATHS"] = tried
                return f"目标文件未找到（尝试过的路径）: {tried}"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (result.stdout or "") + (result.stderr or "")
    except Exception as exc:
        return f"执行失败: {exc}"


def _try_read_from_archive(base_path: str | None, try_path: str) -> str | None:
    if not base_path or not os.path.isfile(base_path):
        return None

    member = try_path[len(os.path.normpath(base_path)):].lstrip("/\\")
    if not member:
        return None

    try:
        if tarfile.is_tarfile(base_path):
            with tarfile.open(base_path, "r") as archive:
                try:
                    file_obj = archive.extractfile(member)
                    if file_obj:
                        globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member}"]
                        return file_obj.read().decode("utf-8", errors="replace")
                except KeyError:
                    pass
                prefix = member.rstrip("/") + "/"
                members = [name for name in archive.getnames() if name.startswith(prefix)]
                if members:
                    children = sorted({name[len(prefix):].split("/", 1)[0] for name in members})
                    globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member} (dir)"]
                    return "目录列出: " + member + "\n" + "\n".join(children)
    except Exception:
        pass

    try:
        if zipfile.is_zipfile(base_path):
            with zipfile.ZipFile(base_path, "r") as archive:
                names = archive.namelist()
                if member in names:
                    globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member}"]
                    return archive.read(member).decode("utf-8", errors="replace")
                prefix = member.rstrip("/") + "/"
                members = [name for name in names if name.startswith(prefix)]
                if members:
                    children = sorted({name[len(prefix):].split("/", 1)[0] for name in members})
                    globals()["_LAST_TRIED_PATHS"] = [f"{base_path}:{member} (dir)"]
                    return "目录列出: " + member + "\n" + "\n".join(children)
    except Exception:
        pass

    return None
