from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.db_viewer import inspect_sqlite_database


router = APIRouter()


class DatabaseInspectRequest(BaseModel):
    mapping_path: str = Field(..., min_length=1)
    database_path: str = Field(..., min_length=1)


@router.post("/api/database/inspect")
def database_inspect(request: DatabaseInspectRequest):
    try:
        return inspect_sqlite_database(request.mapping_path, request.database_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
