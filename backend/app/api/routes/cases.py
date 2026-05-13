from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.cases import delete_case, list_cases, save_case, select_case


router = APIRouter()


class CasePayloadRequest(BaseModel):
    payload: dict = Field(default_factory=dict)


class CaseSelectRequest(BaseModel):
    case_id: str = Field(..., min_length=1)


@router.get("/api/cases")
def cases_list():
    return list_cases()


@router.post("/api/cases")
def cases_save(request: CasePayloadRequest):
    try:
        return save_case(request.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/cases/select")
def cases_select(request: CaseSelectRequest):
    try:
        return select_case(request.case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/cases/{case_id}")
def cases_delete(case_id: str):
    return delete_case(case_id)
