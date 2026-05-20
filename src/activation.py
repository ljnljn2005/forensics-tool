from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


# Public key for v1.2 license verification. The matching private key is kept
# only in the local private activation generator and must not be committed.
PUBLIC_KEY_B64 = "Pgi0HdxazVsKcLmZgjopjNWm/6E0Maz4OszRCDgpNLE="


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve() if path.exists() else path.absolute()).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def runtime_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_root = Path(sys.executable).resolve().parent
        roots.extend([exe_root, Path(getattr(sys, "_MEIPASS", exe_root)).resolve()])
    roots.append(Path(__file__).resolve().parents[1])
    return _dedupe_paths(roots)


def default_license_paths() -> list[Path]:
    paths: list[Path] = []
    for root in runtime_roots():
        paths.extend([root / "activation.lic", root / "settings" / "activation.lic"])
    return _dedupe_paths(paths)


def machine_id() -> str:
    raw = "|".join(
        [
            platform.node(),
            platform.system(),
            platform.machine(),
            str(uuid.getnode()),
            os.environ.get("PROCESSOR_IDENTIFIER", ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:32]


def license_paths() -> list[Path]:
    custom = os.environ.get("FORENSICS_TOOL_LICENSE", "").strip()
    if custom:
        return [Path(custom).expanduser(), *default_license_paths()]
    return default_license_paths()


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_license() -> dict[str, Any]:
    for path in license_paths():
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    expected = " 或 ".join(str(path) for path in license_paths())
    raise RuntimeError(f"未找到激活文件，请联系作者获取激活码。当前机器码：{machine_id()}。收到后请放置到 {expected}")


def _verify_signature(payload: dict[str, Any], signature: str) -> None:
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64))
    try:
        public_key.verify(base64.b64decode(signature), _canonical_payload(payload))
    except (InvalidSignature, ValueError) as exc:
        raise RuntimeError("激活码签名无效，请联系作者重新获取。") from exc


def require_activation() -> dict[str, Any]:
    license_data = _load_license()
    payload = license_data.get("payload")
    signature = str(license_data.get("signature", ""))
    if not isinstance(payload, dict) or not signature:
        raise RuntimeError("激活文件格式无效，请联系作者重新获取。")

    _verify_signature(payload, signature)

    expected_machine = str(payload.get("machine_id", ""))
    current_machine = machine_id()
    if expected_machine != current_machine:
        raise RuntimeError(f"激活码不适用于当前机器。当前机器码：{current_machine}")

    expires_at = str(payload.get("expires_at", "")).strip()
    if expires_at:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise RuntimeError("激活码已过期，请联系作者续期。")

    return payload
