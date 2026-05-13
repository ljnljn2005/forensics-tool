from pydantic import BaseModel, Field


class RegistryScanRequest(BaseModel):
    mapping_path: str = Field(..., min_length=1)
    scan_item: str = Field(..., min_length=1)
    registry_path: str = ""
