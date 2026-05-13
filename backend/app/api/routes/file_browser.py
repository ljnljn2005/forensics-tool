from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.file_browser import inspect_mapped_path, open_mapped_path


router = APIRouter()


class PathInspectRequest(BaseModel):
    mapping_path: str = Field(..., min_length=1)
    target_path: str = Field(..., min_length=1)


class PathOpenRequest(PathInspectRequest):
    action: str = Field(..., min_length=1)


@router.post("/api/file-browser/inspect")
def file_browser_inspect(request: PathInspectRequest):
    try:
        return inspect_mapped_path(request.mapping_path, request.target_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/file-browser/open")
def file_browser_open(request: PathOpenRequest):
    try:
        return open_mapped_path(request.mapping_path, request.target_path, request.action)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
