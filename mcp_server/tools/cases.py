from backend.app.services.cases import list_cases, save_case, select_case


def cases_list() -> dict:
    payload = list_cases()
    return {
        "summary": {
            "case_count": len(payload.get("cases", [])),
            "current_case_id": payload.get("current_case_id", ""),
        },
        "cases": payload.get("cases", []),
        "current_case": payload.get("current_case"),
    }


def cases_save(case_payload: dict) -> dict:
    payload = save_case(case_payload)
    return {
        "summary": {
            "case_count": len(payload.get("cases", [])),
            "current_case_id": payload.get("current_case_id", ""),
        },
        "cases": payload.get("cases", []),
        "current_case": payload.get("current_case"),
    }


def cases_select(case_id: str) -> dict:
    payload = select_case(case_id)
    return {
        "summary": {
            "case_count": len(payload.get("cases", [])),
            "current_case_id": payload.get("current_case_id", ""),
        },
        "cases": payload.get("cases", []),
        "current_case": payload.get("current_case"),
    }


def cases_get_evidence_by_type(evidence_type: str, case_id: str = "") -> dict:
    payload = list_cases()
    cases = payload.get("cases", [])
    selected_case = payload.get("current_case") or {}
    if case_id:
        selected_case = next((item for item in cases if item.get("id") == case_id), None)
        if selected_case is None:
            raise ValueError("case not found")

    evidence_items = [item for item in selected_case.get("evidence_items", []) if item.get("type") == evidence_type]
    return {
        "summary": {
            "case_id": selected_case.get("id", ""),
            "case_name": selected_case.get("name", ""),
            "evidence_type": evidence_type,
            "count": len(evidence_items),
        },
        "items": evidence_items,
    }
