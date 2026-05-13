from typing import Any

from pydantic import BaseModel, Field


class ExtractorRunRequest(BaseModel):
    module: str = Field(default="windows")
    mapping_path: str = ""
    entry: dict[str, Any] = Field(default_factory=dict)
