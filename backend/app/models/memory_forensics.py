from typing import Any

from pydantic import BaseModel, Field


class MemoryTaskRequest(BaseModel):
    module: str = Field(default="windows")
    task: dict[str, Any] = Field(default_factory=dict)
    tool_root: str = ""
    memory_image: str = ""
    offline: bool = False
