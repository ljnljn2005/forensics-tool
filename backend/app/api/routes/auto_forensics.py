from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.auto_forensics import (
    run_file_extraction,
    run_log_analysis,
    run_registry_analysis,
    run_system_info_scan,
)

router = APIRouter()


class AutoForensicsRequest(BaseModel):
    mapping_path: str = Field(..., min_length=1)
    module: str = "windows"


class MappingPathRequest(BaseModel):
    mapping_path: str = Field(..., min_length=1)


@router.post("/api/auto-forensics/scan")
def auto_forensics_scan(request: AutoForensicsRequest):
    """Phase 1: file extraction from plugins."""
    module = request.module.lower()
    if module not in {"windows", "linux", "android", "ios"}:
        raise HTTPException(status_code=400, detail="invalid module")
    return run_file_extraction(mapping_path=request.mapping_path, module=module)


@router.post("/api/auto-forensics/scan-system-info")
def auto_forensics_scan_system_info(request: MappingPathRequest):
    """Phase 0: Windows system information from registry."""
    return run_system_info_scan(mapping_path=request.mapping_path)


@router.post("/api/auto-forensics/scan-registry")
def auto_forensics_scan_registry(request: MappingPathRequest):
    """Phase 2: Windows registry scan."""
    return run_registry_analysis(mapping_path=request.mapping_path)


@router.post("/api/auto-forensics/scan-logs")
def auto_forensics_scan_logs(request: MappingPathRequest):
    """Phase 3: Windows log scan."""
    return run_log_analysis(mapping_path=request.mapping_path, module="windows")
