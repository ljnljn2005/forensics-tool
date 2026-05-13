from pydantic import BaseModel, Field


class LogScanRequest(BaseModel):
    mapping_path: str = Field(..., min_length=1)
    module: str = Field(default="windows")


class LogEntryModel(BaseModel):
    name: str = ""
    path: str = ""
    display_path: str = ""
    category: str = ""
    size: int = 0
    modified: int = 0


class LogDetailRequest(BaseModel):
    entry: LogEntryModel
