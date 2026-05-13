from pydantic import BaseModel, Field


class AiAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=1)
