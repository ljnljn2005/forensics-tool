import os
import subprocess
import tarfile
import zipfile
from typing import Any

from backend.app.services.file_signatures import detect_file_signature
from src.extractor import materialize_mapped_file, resolve_mapped_path_candidates


def _archive_member_from_target(base_path: str, target_path: str) -> str:
    base_norm = os.path.normpath(base_path)
    target_norm = os.path.normpath(target_path)
    if target_norm.startswith(base_norm):
        member = target_norm[len(base_norm):].lstrip("/\\")
    else:
        member = str(target_path).lstrip("/\\")
    return member.replace("\\", "/")


def _read_local_file_header(path: str, size: int = 64) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(size)
    except OSError:
        return b""


def _read_archive_member_header(mapping_path: str, member: str, size: int = 64) -> bytes:
    member = member.strip("/")
    if not member:
        return b""

    try:
        if tarfile.is_tarfile(mapping_path):
            with tarfile.open(mapping_path, "r") as archive:
                file_obj = archive.extractfile(member)
                return file_obj.read(size) if file_obj else b""
    except Exception:
        pass

    try:
        if zipfile.is_zipfile(mapping_path):
            with zipfile.ZipFile(mapping_path, "r") as archive:
                with archive.open(member, "r") as file_obj:
                    return file_obj.read(size)
    except Exception:
        pass
    return b""


def _detect_local_file(path: str) -> dict[str, Any]:
    detected = detect_file_signature(_read_local_file_header(path))
    return {
        "detected_kind": detected["kind"],
        "detected_format": detected["format"],
        "detected_mime": detected["mime"],
        "preferred_extension": detected["preferred_extension"],
    }


def _detect_archive_file(mapping_path: str, member: str) -> dict[str, Any]:
    detected = detect_file_signature(_read_archive_member_header(mapping_path, member))
    return {
        "detected_kind": detected["kind"],
        "detected_format": detected["format"],
        "detected_mime": detected["mime"],
        "preferred_extension": detected["preferred_extension"],
    }


def inspect_mapped_path(mapping_path: str, target_path: str) -> dict[str, Any]:
    candidates = resolve_mapped_path_candidates(mapping_path, target_path)

    for candidate in candidates:
        if os.path.isdir(candidate):
            children = []
            for name in sorted(os.listdir(candidate)):
                child_path = os.path.join(candidate, name)
                file_meta = _detect_local_file(child_path) if os.path.isfile(child_path) else {
                    "detected_kind": "directory" if os.path.isdir(child_path) else "unknown",
                    "detected_format": "",
                    "detected_mime": "",
                    "preferred_extension": "",
                }
                children.append(
                    {
                        "name": name,
                        "path": child_path,
                        "is_dir": os.path.isdir(child_path),
                        "is_file": os.path.isfile(child_path),
                        **file_meta,
                    }
                )
            return {
                "ok": True,
                "kind": "directory",
                "path": candidate,
                "source_path": candidate,
                "children": children,
                "tried_paths": candidates,
                "detected_kind": "directory",
                "detected_format": "",
                "detected_mime": "",
                "preferred_extension": "",
            }
        if os.path.isfile(candidate):
            return {
                "ok": True,
                "kind": "file",
                "path": candidate,
                "source_path": candidate,
                "children": [],
                "tried_paths": candidates,
                **_detect_local_file(candidate),
            }

    if mapping_path and os.path.isfile(mapping_path):
        member_candidates = [_archive_member_from_target(mapping_path, target_path)]
        member_candidates.extend(_archive_member_from_target(mapping_path, item) for item in candidates)
        deduped_members: list[str] = []
        for member in member_candidates:
            member = member.strip("/")
            if member and member not in deduped_members:
                deduped_members.append(member)

        try:
            if tarfile.is_tarfile(mapping_path):
                with tarfile.open(mapping_path, "r") as archive:
                    archive_names = archive.getnames()
                    archive_name_set = set(archive_names)
                    for member in deduped_members:
                        if member in archive_name_set:
                            return {
                                "ok": True,
                                "kind": "file",
                                "path": target_path,
                                "source_path": f"{mapping_path}:{member}",
                                "children": [],
                                "tried_paths": candidates,
                                **_detect_archive_file(mapping_path, member),
                            }
                        prefix = member.rstrip("/") + "/"
                        matches = [name for name in archive_names if name.startswith(prefix)]
                        if matches:
                            children = sorted({name[len(prefix):].split("/", 1)[0] for name in matches if name != prefix})
                            return {
                                "ok": True,
                                "kind": "directory",
                                "path": target_path,
                                "source_path": f"{mapping_path}:{member}",
                                "children": [
                                    {
                                        "name": child,
                                        "path": os.path.join(target_path, child).replace("\\", "/"),
                                        "is_dir": any(name.startswith(prefix + child + "/") for name in matches),
                                        "is_file": child in [name[len(prefix):] for name in matches],
                                        **(
                                            _detect_archive_file(mapping_path, prefix + child)
                                            if child in [name[len(prefix):] for name in matches]
                                            else {
                                                "detected_kind": "directory",
                                                "detected_format": "",
                                                "detected_mime": "",
                                                "preferred_extension": "",
                                            }
                                        ),
                                    }
                                    for child in children
                                ],
                                "tried_paths": candidates,
                                "detected_kind": "directory",
                                "detected_format": "",
                                "detected_mime": "",
                                "preferred_extension": "",
                            }
        except Exception:
            pass

        try:
            if zipfile.is_zipfile(mapping_path):
                with zipfile.ZipFile(mapping_path, "r") as archive:
                    names = archive.namelist()
                    name_set = set(names)
                    for member in deduped_members:
                        if member in name_set:
                            return {
                                "ok": True,
                                "kind": "file",
                                "path": target_path,
                                "source_path": f"{mapping_path}:{member}",
                                "children": [],
                                "tried_paths": candidates,
                                **_detect_archive_file(mapping_path, member),
                            }
                        prefix = member.rstrip("/") + "/"
                        matches = [name for name in names if name.startswith(prefix)]
                        if matches:
                            children = sorted({name[len(prefix):].split("/", 1)[0] for name in matches if name != prefix})
                            return {
                                "ok": True,
                                "kind": "directory",
                                "path": target_path,
                                "source_path": f"{mapping_path}:{member}",
                                "children": [
                                    {
                                        "name": child,
                                        "path": os.path.join(target_path, child).replace("\\", "/"),
                                        "is_dir": any(name.startswith(prefix + child + "/") for name in matches),
                                        "is_file": child in [name[len(prefix):] for name in matches],
                                        **(
                                            _detect_archive_file(mapping_path, prefix + child)
                                            if child in [name[len(prefix):] for name in matches]
                                            else {
                                                "detected_kind": "directory",
                                                "detected_format": "",
                                                "detected_mime": "",
                                                "preferred_extension": "",
                                            }
                                        ),
                                    }
                                    for child in children
                                ],
                                "tried_paths": candidates,
                                "detected_kind": "directory",
                                "detected_format": "",
                                "detected_mime": "",
                                "preferred_extension": "",
                            }
        except Exception:
            pass

    raise FileNotFoundError(f"target path not found: {target_path}")


def open_mapped_path(mapping_path: str, target_path: str, action: str) -> dict[str, Any]:
    if action not in {"default", "explorer"}:
        raise ValueError("invalid action")

    info = inspect_mapped_path(mapping_path, target_path)
    source_path = info["path"]
    materialize_suffix = info.get("preferred_extension", "") or os.path.splitext(target_path)[1]
    if info["kind"] == "file" and not os.path.isfile(source_path):
        source_path, _, _ = materialize_mapped_file(target_path, base_path=mapping_path, suffix=materialize_suffix)
    elif info["kind"] == "file" and action == "default":
        existing_extension = os.path.splitext(source_path)[1].lower()
        preferred_extension = str(info.get("preferred_extension", "")).lower()
        if preferred_extension and existing_extension != preferred_extension:
            source_path, _, _ = materialize_mapped_file(target_path, base_path=mapping_path, suffix=preferred_extension)

    if info["kind"] == "directory" and not os.path.isdir(source_path):
        raise FileNotFoundError("directory open for archived paths is not supported yet")

    if os.name == "nt":
        if action == "default":
            os.startfile(source_path)  # type: ignore[attr-defined]
        elif info["kind"] == "file":
            subprocess.run(["explorer", "/select,", os.path.normpath(source_path)], check=False)
        else:
            subprocess.run(["explorer", os.path.normpath(source_path)], check=False)
    else:
        subprocess.run(["xdg-open", source_path], check=False)

    return {
        "ok": True,
        "kind": info["kind"],
        "opened_path": source_path,
        "source_path": info["source_path"],
        "detected_kind": info.get("detected_kind", "unknown"),
    }
