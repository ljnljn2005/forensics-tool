from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.services.plugins import delete_plugin, fetch_plugin_market, list_plugins, save_plugin


router = APIRouter()


@router.get("/api/plugins")
def plugins_list():
    return list_plugins()


@router.post("/api/plugins")
def plugins_save(payload: dict[str, Any]):
    try:
        return save_plugin(dict(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/plugins/{name}")
def plugins_delete(name: str):
    return delete_plugin(name)


@router.get("/api/plugin-market")
def plugin_market(url: str):
    if not url.strip():
        raise HTTPException(status_code=400, detail="url is required")
    return fetch_plugin_market(url)
