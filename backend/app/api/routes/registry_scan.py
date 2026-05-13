from fastapi import APIRouter, HTTPException

from backend.app.models.registry_scan import RegistryScanRequest
from backend.app.services.registry_scan import run_registry_scan


router = APIRouter()


@router.post("/api/windows/registry/scan")
def registry_scan(request: RegistryScanRequest):
    if not request.mapping_path:
        raise HTTPException(status_code=400, detail="mapping_path is required")
    return run_registry_scan(
        mapping_path=request.mapping_path,
        scan_item=request.scan_item,
        registry_path=request.registry_path,
    )
