from __future__ import annotations

import math
import sys
import threading
import uuid
from pathlib import Path

import cv2 as cv
import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[3]
JIGSAW_ROOT = PROJECT_ROOT / "tools" / "toolbox" / "Jigsaw Puzzle"
GAPS_ROOT = JIGSAW_ROOT / "gaps-main"
OUTPUT_ROOT = JIGSAW_ROOT / "10086"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp", ".ico", ".tif"}
MIN_PIECE_SIZE = 32
MAX_PIECE_SIZE = 128

_TASKS: dict[str, dict[str, object]] = {}
_TASKS_LOCK = threading.Lock()
_SOLVE_LOCK = threading.Lock()


def _ensure_gaps_importable() -> None:
    gaps_path = str(GAPS_ROOT)
    if gaps_path not in sys.path:
        sys.path.insert(0, gaps_path)


def _read_image_cv(path: Path):
    return cv.imdecode(np.fromfile(str(path), dtype=np.uint8), cv.IMREAD_COLOR)


def _write_image_cv(path: Path, image: np.ndarray) -> None:
    suffix = path.suffix or ".png"
    ok, buffer = cv.imencode(suffix, image)
    if not ok:
        raise ValueError(f"Unable to encode image for output: {path}")
    buffer.tofile(str(path))


def _iter_image_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMG_EXTS],
        key=lambda item: item.name.lower(),
    )


def _sort_image_files(files: list[Path], sort_mode: str) -> list[Path]:
    if sort_mode == "name_desc":
        return sorted(files, key=lambda item: item.name.lower(), reverse=True)
    if sort_mode == "mtime_asc":
        return sorted(files, key=lambda item: item.stat().st_mtime)
    if sort_mode == "mtime_desc":
        return sorted(files, key=lambda item: item.stat().st_mtime, reverse=True)
    return sorted(files, key=lambda item: item.name.lower())


def _piece_size_candidates(width: int, height: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    total_pixels = width * height
    for piece_size in range(MIN_PIECE_SIZE, min(width, height, MAX_PIECE_SIZE) + 1):
        cols = width // piece_size
        rows = height // piece_size
        if cols < 1 or rows < 1:
            continue
        adapted_width = cols * piece_size
        adapted_height = rows * piece_size
        used_pixels = adapted_width * adapted_height
        loss_pixels = total_pixels - used_pixels
        used_ratio = used_pixels / total_pixels if total_pixels else 0
        total_pieces = cols * rows
        candidates.append(
            {
                "piece_size": piece_size,
                "cols": cols,
                "rows": rows,
                "total_pieces": total_pieces,
                "adapted_width": adapted_width,
                "adapted_height": adapted_height,
                "loss_pixels": loss_pixels,
                "loss_ratio": round(loss_pixels / total_pixels, 6) if total_pixels else 0,
                "used_ratio": round(used_ratio, 6),
                "exact_fit": adapted_width == width and adapted_height == height,
            }
        )
    candidates.sort(
        key=lambda item: (
            0 if bool(item["exact_fit"]) else 1,
            abs(int(item["total_pieces"]) - 200),
            float(item["loss_ratio"]),
            -float(item["used_ratio"]),
        )
    )
    return candidates


def _center_crop_to_grid(image: Image.Image, piece_size: int) -> tuple[Image.Image, dict[str, int]]:
    width, height = image.size
    adapted_width = (width // piece_size) * piece_size
    adapted_height = (height // piece_size) * piece_size
    if adapted_width < piece_size or adapted_height < piece_size:
        raise ValueError(f"Image is too small for piece size {piece_size}px.")
    left = max((width - adapted_width) // 2, 0)
    top = max((height - adapted_height) // 2, 0)
    right = left + adapted_width
    bottom = top + adapted_height
    cropped = image.crop((left, top, right, bottom))
    return cropped, {
        "original_width": width,
        "original_height": height,
        "adapted_width": adapted_width,
        "adapted_height": adapted_height,
        "crop_left": left,
        "crop_top": top,
        "crop_right": right,
        "crop_bottom": bottom,
    }


def _new_task(message: str) -> dict[str, object]:
    task_id = uuid.uuid4().hex
    task = {
        "task_id": task_id,
        "status": "running",
        "progress": 0.0,
        "message": message,
        "output_path": "",
    }
    with _TASKS_LOCK:
        _TASKS[task_id] = task
    return task


def _update_task(task_id: str, **updates: object) -> None:
    with _TASKS_LOCK:
        if task_id in _TASKS:
            _TASKS[task_id].update(updates)


def get_solve_task(task_id: str) -> dict[str, object]:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            raise ValueError(f"Unknown task id: {task_id}")
        return dict(task)


def jigsaw_catalog() -> dict[str, object]:
    return {
        "key": "jigsaw-puzzle",
        "name": "Jigsaw Puzzle",
        "description": "集成超级拼接、正方形转换、拼图生成与拼图还原。",
        "tool_dir": str(JIGSAW_ROOT),
        "features": [
            {"key": "montage", "name": "超级拼接"},
            {"key": "square", "name": "正方形转换"},
            {"key": "puzzle", "name": "拼图生成 / 还原"},
        ],
    }


def analyze_montage(folder_path: str, sort_mode: str, cols: int, cell_width: int, cell_height: int, gap: int) -> dict[str, object]:
    folder = Path(folder_path)
    files = _sort_image_files(_iter_image_files(folder), sort_mode)
    if not files:
        return {"folder_path": str(folder), "count": 0, "files": [], "layout": None}

    total = len(files)
    resolved_cols = cols if cols and cols > 0 else max(int(math.sqrt(total)), 1)
    rows = math.ceil(total / resolved_cols)
    canvas_width = resolved_cols * cell_width + (resolved_cols + 1) * gap
    canvas_height = rows * cell_height + (rows + 1) * gap
    memory_mb = round((canvas_width * canvas_height * 4) / (1024 * 1024), 2)
    return {
        "folder_path": str(folder),
        "count": total,
        "files": [str(path) for path in files[:500]],
        "layout": {
            "cols": resolved_cols,
            "rows": rows,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "memory_mb": memory_mb,
        },
    }


def run_montage(
    folder_path: str,
    sort_mode: str,
    cols: int,
    cell_width: int,
    cell_height: int,
    gap: int,
    background: str,
    output_path: str,
) -> dict[str, object]:
    analysis = analyze_montage(folder_path, sort_mode, cols, cell_width, cell_height, gap)
    files = [Path(path) for path in analysis["files"]]
    layout = analysis["layout"]
    if not files or not layout:
        raise ValueError("No input images were found in the selected folder.")

    canvas = Image.new("RGB", (layout["canvas_width"], layout["canvas_height"]), background)
    for index, file_path in enumerate(files):
        row = index // layout["cols"]
        col = index % layout["cols"]
        x = gap + col * (cell_width + gap)
        y = gap + row * (cell_height + gap)
        with Image.open(file_path) as image:
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            if image.mode == "RGBA":
                base = Image.new("RGBA", image.size, background)
                image = Image.alpha_composite(base, image)
            image = image.convert("RGB").resize((cell_width, cell_height), Image.LANCZOS)
            canvas.paste(image, (x, y))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return {
        "ok": True,
        "output_path": str(output),
        "count": len(files),
        "layout": layout,
        "message": f"已完成超级拼接，共处理 {len(files)} 张图片。",
    }


def preview_square(image_path: str, cols: int, rows: int, mode: str) -> dict[str, object]:
    if cols < 1 or rows < 1:
        raise ValueError("Rows and columns must be positive integers.")
    path = Path(image_path)
    with Image.open(path) as image:
        width, height = image.size

    cell_width = width / cols
    cell_height = height / rows
    if mode == "keep_width":
        new_width, new_height = width, round(width * rows / cols)
    elif mode == "keep_height":
        new_width, new_height = round(height * cols / rows), height
    else:
        side = math.sqrt(cell_width * cell_height)
        new_width = round(side * cols)
        new_height = round(new_width * rows / cols)

    return {
        "input_path": str(path),
        "original_width": width,
        "original_height": height,
        "cols": cols,
        "rows": rows,
        "cell_width": round(cell_width, 2),
        "cell_height": round(cell_height, 2),
        "new_width": new_width,
        "new_height": new_height,
        "new_cell_width": round(new_width / cols, 2),
        "new_cell_height": round(new_height / rows, 2),
        "mode": mode,
    }


def run_square(image_path: str, cols: int, rows: int, mode: str, output_path: str | None = None) -> dict[str, object]:
    preview = preview_square(image_path, cols, rows, mode)
    source = Path(image_path)
    output = Path(output_path) if output_path else source.with_name(f"{source.stem}_square{source.suffix}")
    with Image.open(source) as image:
        converted = image.resize((preview["new_width"], preview["new_height"]), Image.LANCZOS)
        output.parent.mkdir(parents=True, exist_ok=True)
        converted.save(output)
    return {"ok": True, "output_path": str(output), "preview": preview, "message": "已完成正方形转换。"}


def inspect_puzzle_image(image_path: str) -> dict[str, object]:
    path = Path(image_path)
    with Image.open(path) as image:
        width, height = image.size

    suggestions = _piece_size_candidates(width, height)
    exact_sizes = [int(item["piece_size"]) for item in suggestions if bool(item["exact_fit"])]
    suggested = suggestions[0] if suggestions else None
    return {
        "image_path": str(path),
        "width": width,
        "height": height,
        "valid_piece_sizes": exact_sizes,
        "suggested": suggested,
        "suggestions": suggestions[:12],
    }


def auto_adapt_puzzle_source(image_path: str, piece_size: int) -> dict[str, object]:
    source = Path(image_path)
    with Image.open(source) as image:
        cropped, meta = _center_crop_to_grid(image, piece_size)
        output = source.with_name(f"{source.stem}_adapted{source.suffix}")
        cropped.save(output)
    return {
        "ok": True,
        "output_path": str(output),
        "adapted": meta["adapted_width"] != meta["original_width"] or meta["adapted_height"] != meta["original_height"],
        "mode": "crop",
        "crop": meta,
    }


def create_puzzle(image_path: str, output_path: str, piece_size: int) -> dict[str, object]:
    _ensure_gaps_importable()
    from gaps import utils

    source = Path(image_path)
    output = Path(output_path)
    input_image = _read_image_cv(source)
    if input_image is None:
        raise ValueError(f"Unable to read image: {source}")
    pieces, rows, columns = utils.flatten_image(input_image, piece_size)
    np.random.shuffle(pieces)
    puzzle = utils.assemble_image(pieces, rows, columns)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_image_cv(output, puzzle)
    return {
        "ok": True,
        "output_path": str(output),
        "piece_size": piece_size,
        "rows": rows,
        "columns": columns,
        "pieces": len(pieces),
        "message": f"已生成拼图，共 {len(pieces)} 个碎片。",
    }


def start_solve_puzzle_task(
    puzzle_path: str,
    output_path: str,
    piece_size: int | None,
    generations: int,
    population: int,
    selection: str,
    mutation: float,
) -> dict[str, object]:
    task = _new_task("正在准备拼图还原任务...")

    def worker() -> None:
        try:
            _solve_puzzle_sync(
                task_id=str(task["task_id"]),
                puzzle_path=puzzle_path,
                output_path=output_path,
                piece_size=piece_size,
                generations=generations,
                population=population,
                selection=selection,
                mutation=mutation,
            )
        except Exception as exc:  # pragma: no cover
            _update_task(str(task["task_id"]), status="failed", message=str(exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return dict(task)


def _solve_puzzle_sync(
    task_id: str,
    puzzle_path: str,
    output_path: str,
    piece_size: int | None,
    generations: int,
    population: int,
    selection: str,
    mutation: float,
) -> None:
    _ensure_gaps_importable()
    import gaps.genetic_algorithm as ga_module
    from gaps.genetic_algorithm import GeneticAlgorithm
    from gaps.size_detector import SizeDetector

    source = Path(puzzle_path)
    output = Path(output_path)
    image = _read_image_cv(source)
    if image is None:
        raise ValueError(f"Unable to read puzzle image: {source}")

    _update_task(task_id, progress=2.0, message="正在分析拼图片段尺寸...")
    resolved_piece_size = piece_size or SizeDetector(image).detect()
    _update_task(task_id, progress=5.0, message=f"已确定碎片尺寸：{resolved_piece_size}px")

    with _SOLVE_LOCK:
        original_print_progress = ga_module.print_progress

        def patched_progress(iteration: int, total: int, prefix: str = "", suffix: str = "", decimals: int = 1, bar_length: int = 50) -> None:
            if total <= 0:
                percent = 100.0
            else:
                percent = max(0.0, min(100.0, (iteration / float(total)) * 100.0))
            progress = 5.0 + percent * 0.9
            _update_task(task_id, progress=round(progress, 1), message=f"正在还原拼图：{percent:.1f}%")
            original_print_progress(iteration, total, prefix=prefix, suffix=suffix, decimals=decimals, bar_length=bar_length)

        ga_module.print_progress = patched_progress
        try:
            ga = GeneticAlgorithm(
                image=image,
                piece_size=resolved_piece_size,
                population_size=population,
                generations=generations,
                selection_method=selection,
                mutation_rate=mutation,
            )
            result = ga.start_evolution(False)
        finally:
            ga_module.print_progress = original_print_progress

    _update_task(task_id, progress=98.0, message="正在写出还原结果...")
    solved_image = result.to_image()
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_image_cv(output, solved_image)
    _update_task(
        task_id,
        status="completed",
        progress=100.0,
        output_path=str(output),
        message="拼图还原完成。",
        piece_size=resolved_piece_size,
        generations=generations,
        population=population,
        selection=selection,
        mutation=mutation,
    )
