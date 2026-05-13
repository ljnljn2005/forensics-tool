from fastapi import APIRouter, HTTPException

from backend.app.models.android_auto_forensics import AndroidAutoForensicsRequest
from backend.app.services.android_auto_forensics import scan_android_apps


router = APIRouter()


@router.post("/api/android/auto-forensics/scan")
def android_auto_forensics_scan(request: AndroidAutoForensicsRequest):
    if not request.mapping_path:
        raise HTTPException(status_code=400, detail="mapping_path is required")
    return scan_android_apps(
        request.mapping_path,
        [entry.model_dump() for entry in request.entries],
    )
