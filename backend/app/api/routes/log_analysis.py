from fastapi import APIRouter, HTTPException

from backend.app.models.log_analysis import LogDetailRequest, LogScanRequest
from backend.app.services.log_analysis import get_log_detail, list_logs


router = APIRouter()


@router.post("/api/logs/scan")
def scan_logs(request: LogScanRequest):
    if request.module not in {"windows", "linux"}:
        raise HTTPException(status_code=400, detail="module must be windows or linux")
    return list_logs(request.mapping_path, request.module)


@router.post("/api/logs/detail")
def log_detail(request: LogDetailRequest):
    return get_log_detail(request.entry.model_dump())
