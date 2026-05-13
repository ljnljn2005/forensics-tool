from fastapi import APIRouter

from backend.app.models.ai_analysis import AiAnalysisRequest
from backend.app.services.ai_analysis import run_ai_analysis


router = APIRouter()


@router.post("/api/ai/analyze")
def ai_analyze(request: AiAnalysisRequest):
    return run_ai_analysis(request.text)
