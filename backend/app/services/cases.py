import uuid

from src.constants import get_app_settings, save_app_settings


EVIDENCE_TYPES = ("windows", "linux", "android", "ios", "windows_memory", "linux_memory")


def _normalize_evidence_items(payload: dict) -> list[dict]:
    items = payload.get("evidence_items", [])
    normalized: list[dict] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "")).strip()
            if item_type not in EVIDENCE_TYPES:
                continue
            normalized.append(
                {
                    "id": str(item.get("id") or uuid.uuid4()),
                    "type": item_type,
                    "label": str(item.get("label", "")).strip() or f"{item_type} 检材",
                    "path": str(item.get("path", "")).strip(),
                }
            )

    if normalized:
        return normalized

    evidence_paths = payload.get("evidence_paths", {}) if isinstance(payload.get("evidence_paths", {}), dict) else {}
    for item_type in EVIDENCE_TYPES:
        path = str(evidence_paths.get(item_type, "")).strip()
        if path:
            normalized.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": item_type,
                    "label": f"{item_type} 检材",
                    "path": path,
                }
            )
    return normalized


def _derive_evidence_paths(items: list[dict]) -> dict:
    derived = {item_type: "" for item_type in EVIDENCE_TYPES}
    for item_type in EVIDENCE_TYPES:
        first = next((item.get("path", "") for item in items if item.get("type") == item_type and item.get("path")), "")
        derived[item_type] = first
    return derived


def _normalize_case(payload: dict) -> dict:
    evidence_items = _normalize_evidence_items(payload)
    ssh = payload.get("ssh", {}) if isinstance(payload.get("ssh", {}), dict) else {}
    return {
        "id": str(payload.get("id") or uuid.uuid4()),
        "name": str(payload.get("name", "")).strip(),
        "description": str(payload.get("description", "")).strip(),
        "evidence_items": evidence_items,
        "evidence_paths": _derive_evidence_paths(evidence_items),
        "ssh": {
            "host": str(ssh.get("host", "")).strip(),
            "port": int(ssh.get("port", 22) or 22),
            "user": str(ssh.get("user", "")).strip(),
            "password": str(ssh.get("password", "")).strip(),
        },
    }


def _read_case_state() -> tuple[list[dict], str]:
    settings = get_app_settings()
    raw_cases = settings.get("cases", [])
    cases = [_normalize_case(item) for item in raw_cases if isinstance(item, dict)]
    current_case_id = str(settings.get("current_case_id", "")).strip()
    return cases, current_case_id


def _write_case_state(cases: list[dict], current_case_id: str):
    save_app_settings({"cases": cases, "current_case_id": current_case_id})


def _current_case(cases: list[dict], current_case_id: str) -> dict | None:
    for case in cases:
        if case["id"] == current_case_id:
            return case
    return cases[0] if cases else None


def list_cases() -> dict:
    cases, current_case_id = _read_case_state()
    current_case = _current_case(cases, current_case_id)
    return {
        "cases": cases,
        "current_case_id": current_case["id"] if current_case else "",
        "current_case": current_case,
    }


def save_case(payload: dict) -> dict:
    normalized = _normalize_case(payload)
    if not normalized["name"]:
        raise ValueError("case name is required")

    cases, current_case_id = _read_case_state()
    replaced = False
    for index, existing in enumerate(cases):
        if existing["id"] == normalized["id"]:
            cases[index] = normalized
            replaced = True
            break
    if not replaced:
        cases.append(normalized)

    if not current_case_id:
        current_case_id = normalized["id"]

    _write_case_state(cases, current_case_id)
    return list_cases()


def select_case(case_id: str) -> dict:
    cases, _ = _read_case_state()
    current_case = _current_case(cases, case_id)
    if current_case is None:
        raise ValueError("case not found")
    _write_case_state(cases, current_case["id"])
    return list_cases()


def delete_case(case_id: str) -> dict:
    cases, current_case_id = _read_case_state()
    cases = [case for case in cases if case["id"] != case_id]
    if current_case_id == case_id:
        current_case_id = cases[0]["id"] if cases else ""
    _write_case_state(cases, current_case_id)
    return list_cases()
