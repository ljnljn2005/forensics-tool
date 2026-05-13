from fastapi import APIRouter, HTTPException

from backend.app.services.global_search import search_plugins


router = APIRouter()


@router.get("/api/search")
def global_search(keyword: str = ""):
    if not keyword.strip():
        raise HTTPException(status_code=400, detail="keyword is required")
    return search_plugins(keyword)
