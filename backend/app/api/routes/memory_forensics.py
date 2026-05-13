from fastapi import APIRouter, HTTPException

from backend.app.models.memory_forensics import MemoryTaskRequest
from backend.app.services.memory_forensics import list_memory_tasks, preview_memory_task, run_memory_task, stop_memprocfs


router = APIRouter()


@router.get("/api/memory/tasks")
def memory_tasks(module: str = "windows"):
    if module not in {"windows", "linux"}:
        raise HTTPException(status_code=400, detail="module must be windows or linux")
    return list_memory_tasks(module)


@router.post("/api/memory/preview")
def memory_preview(request: MemoryTaskRequest):
    if request.module not in {"windows", "linux"}:
        raise HTTPException(status_code=400, detail="module must be windows or linux")
    return preview_memory_task(
        request.module,
        request.task,
        request.tool_root,
        request.memory_image,
        request.offline,
    )


@router.post("/api/memory/run")
def memory_run(request: MemoryTaskRequest):
    if request.module not in {"windows", "linux"}:
        raise HTTPException(status_code=400, detail="module must be windows or linux")
    return run_memory_task(
        request.module,
        request.task,
        request.tool_root,
        request.memory_image,
        request.offline,
    )


@router.post("/api/memory/stop-mount")
def memory_stop_mount():
    return stop_memprocfs()
