from fastapi import APIRouter, HTTPException

from backend.app.models.extractor import ExtractorRunRequest
from backend.app.services.extractor import list_extractor_entries, run_extractor_entry


router = APIRouter()


@router.get("/api/extractor/entries")
def extractor_entries(module: str = "windows"):
    if module not in {"windows", "linux", "android", "ios"}:
        raise HTTPException(status_code=400, detail="invalid module")
    return list_extractor_entries(module)


@router.post("/api/extractor/run")
def extractor_run(request: ExtractorRunRequest):
    if request.module not in {"windows", "linux", "android", "ios"}:
        raise HTTPException(status_code=400, detail="invalid module")
    return run_extractor_entry(request.module, request.mapping_path, request.entry)
