from src.constants import get_app_proxy, get_app_settings, save_app_proxy, save_app_settings
from backend.app.services.cases import list_cases


def read_settings() -> dict:
    data = get_app_settings()
    data["proxy"] = get_app_proxy()
    case_state = list_cases()
    data["current_case_id"] = case_state.get("current_case_id", "")
    data["current_case"] = case_state.get("current_case")
    return data


def update_settings(payload: dict) -> dict:
    proxy = payload.pop("proxy", None)
    if proxy is not None:
        save_app_proxy(proxy)
    save_app_settings(payload)
    return read_settings()
