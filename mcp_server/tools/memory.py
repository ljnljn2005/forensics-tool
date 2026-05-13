from backend.app.services.memory_forensics import list_memory_tasks, preview_memory_task, run_memory_task


def memory_list_tasks(module: str) -> dict:
    payload = list_memory_tasks(module)
    return {
        "summary": {
            "module": module,
            "task_count": len(payload.get("tasks", [])),
            "default_tool_root": payload.get("default_tool_root", ""),
        },
        **payload,
    }


def memory_preview_task(module: str, task: dict, tool_root: str, memory_image: str, offline: bool = False) -> dict:
    payload = preview_memory_task(module, task, tool_root, memory_image, offline)
    return {
        "summary": {
            "module": module,
            "task_name": task.get("name", ""),
            "engine": task.get("engine", ""),
        },
        **payload,
    }


def memory_run_task(module: str, task: dict, tool_root: str, memory_image: str, offline: bool = False) -> dict:
    payload = run_memory_task(module, task, tool_root, memory_image, offline)
    return {
        "summary": {
            "module": module,
            "task_name": task.get("name", ""),
            "engine": task.get("engine", ""),
            "ok": bool(payload.get("ok")),
        },
        **payload,
    }
