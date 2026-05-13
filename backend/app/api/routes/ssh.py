from fastapi import APIRouter

from backend.app.models.ssh import SshConnectionRequest, SshPluginRunRequest
from backend.app.services.ssh import run_ssh_plugin, test_ssh_connection


router = APIRouter()


@router.post("/api/ssh/test")
def ssh_test(request: SshConnectionRequest):
    return test_ssh_connection(request.host, request.port, request.user, request.password)


@router.post("/api/ssh/run-plugin")
def ssh_run_plugin(request: SshPluginRunRequest):
    return run_ssh_plugin(request.host, request.port, request.user, request.password, request.plugin_name)
