from typing import Any

from fastapi import APIRouter

from backend.app.services.mcp_server import export_mcp_client_config, read_mcp_settings, update_mcp_settings


router = APIRouter()


@router.get("/api/mcp/settings")
def mcp_settings_get():
    return read_mcp_settings()


@router.post("/api/mcp/settings")
def mcp_settings_save(payload: dict[str, Any]):
    return update_mcp_settings(dict(payload))


@router.get("/api/mcp/export")
def mcp_export():
    return export_mcp_client_config()
