from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.services.jigsaw_toolbox import (
    analyze_montage,
    auto_adapt_puzzle_source,
    create_puzzle,
    get_solve_task,
    inspect_puzzle_image,
    jigsaw_catalog,
    preview_square,
    run_montage,
    run_square,
    start_solve_puzzle_task,
)
from backend.app.services.toolbox import launch_tool, list_toolbox_tools


router = APIRouter()


@router.get("/api/toolbox/tools")
def toolbox_tools():
    return list_toolbox_tools()


@router.post("/api/toolbox/launch")
def toolbox_launch(payload: dict[str, Any]):
    tool_key = str(payload.get("tool_key", "")).strip()
    if not tool_key:
        raise HTTPException(status_code=400, detail="tool_key is required")
    try:
        return launch_tool(tool_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/toolbox/jigsaw")
def toolbox_jigsaw_catalog():
    return jigsaw_catalog()


@router.post("/api/toolbox/jigsaw/montage/analyze")
def toolbox_jigsaw_montage_analyze(payload: dict[str, Any]):
    try:
        return analyze_montage(
            folder_path=str(payload.get("folder_path", "")),
            sort_mode=str(payload.get("sort_mode", "name_asc")),
            cols=int(payload.get("cols", 0) or 0),
            cell_width=int(payload.get("cell_width", 200) or 200),
            cell_height=int(payload.get("cell_height", 200) or 200),
            gap=int(payload.get("gap", 0) or 0),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/toolbox/jigsaw/montage/run")
def toolbox_jigsaw_montage_run(payload: dict[str, Any]):
    try:
        return run_montage(
            folder_path=str(payload.get("folder_path", "")),
            sort_mode=str(payload.get("sort_mode", "name_asc")),
            cols=int(payload.get("cols", 0) or 0),
            cell_width=int(payload.get("cell_width", 200) or 200),
            cell_height=int(payload.get("cell_height", 200) or 200),
            gap=int(payload.get("gap", 0) or 0),
            background=str(payload.get("background", "white")),
            output_path=str(payload.get("output_path", "")),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/toolbox/jigsaw/square/preview")
def toolbox_jigsaw_square_preview(payload: dict[str, Any]):
    try:
        return preview_square(
            image_path=str(payload.get("image_path", "")),
            cols=int(payload.get("cols", 0) or 0),
            rows=int(payload.get("rows", 0) or 0),
            mode=str(payload.get("mode", "area")),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/toolbox/jigsaw/square/run")
def toolbox_jigsaw_square_run(payload: dict[str, Any]):
    try:
        return run_square(
            image_path=str(payload.get("image_path", "")),
            cols=int(payload.get("cols", 0) or 0),
            rows=int(payload.get("rows", 0) or 0),
            mode=str(payload.get("mode", "area")),
            output_path=str(payload.get("output_path", "")).strip() or None,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/toolbox/jigsaw/puzzle/inspect")
def toolbox_jigsaw_puzzle_inspect(payload: dict[str, Any]):
    try:
        return inspect_puzzle_image(str(payload.get("image_path", "")))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/toolbox/jigsaw/puzzle/adapt")
def toolbox_jigsaw_puzzle_adapt(payload: dict[str, Any]):
    try:
        return auto_adapt_puzzle_source(
            image_path=str(payload.get("image_path", "")),
            piece_size=int(payload.get("piece_size", 64) or 64),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/toolbox/jigsaw/puzzle/create")
def toolbox_jigsaw_puzzle_create(payload: dict[str, Any]):
    try:
        return create_puzzle(
            image_path=str(payload.get("image_path", "")),
            output_path=str(payload.get("output_path", "")),
            piece_size=int(payload.get("piece_size", 64) or 64),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/toolbox/jigsaw/puzzle/solve")
def toolbox_jigsaw_puzzle_solve(payload: dict[str, Any]):
    try:
        piece_size_raw = payload.get("piece_size", None)
        piece_size = int(piece_size_raw) if piece_size_raw not in (None, "", 0, "0") else None
        return start_solve_puzzle_task(
            puzzle_path=str(payload.get("puzzle_path", "")),
            output_path=str(payload.get("output_path", "")),
            piece_size=piece_size,
            generations=int(payload.get("generations", 20) or 20),
            population=int(payload.get("population", 200) or 200),
            selection=str(payload.get("selection", "tournament")),
            mutation=float(payload.get("mutation", 0.02) or 0.02),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/toolbox/jigsaw/puzzle/tasks/{task_id}")
def toolbox_jigsaw_puzzle_task(task_id: str):
    try:
        return get_solve_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
