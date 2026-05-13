from pydantic import BaseModel, Field


class SshConnectionRequest(BaseModel):
    host: str = Field(..., min_length=1)
    port: int = 22
    user: str = Field(..., min_length=1)
    password: str = ""


class SshPluginRunRequest(SshConnectionRequest):
    plugin_name: str = Field(..., min_length=1)
