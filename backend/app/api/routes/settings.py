from typing import Any

from fastapi import APIRouter

from backend.app.services.settings import read_settings, update_settings


router = APIRouter()


@router.get("/api/settings")
def settings_get():
    return read_settings()


@router.post("/api/settings")
def settings_save(payload: dict[str, Any]):
    return update_settings(dict(payload))
