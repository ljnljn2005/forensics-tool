from pydantic import BaseModel, Field


class AndroidAutoForensicsEntry(BaseModel):
    group: str = ""
    name: str = ""
    cmd: str = ""
    type: str = ""
    module: str = "android"
    package_name: str = ""


class AndroidAutoForensicsRequest(BaseModel):
    mapping_path: str = Field(..., min_length=1)
    entries: list[AndroidAutoForensicsEntry] = Field(default_factory=list)
