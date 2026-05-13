from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes.ai_analysis import router as ai_analysis_router
from backend.app.api.routes.android_auto_forensics import router as android_auto_forensics_router
from backend.app.api.routes.auto_forensics import router as auto_forensics_router
from backend.app.api.routes.cases import router as cases_router
from backend.app.api.routes.db_viewer import router as db_viewer_router
from backend.app.api.routes.extractor import router as extractor_router
from backend.app.api.routes.file_browser import router as file_browser_router
from backend.app.api.routes.global_search import router as global_search_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.log_analysis import router as log_analysis_router
from backend.app.api.routes.mcp_server import router as mcp_server_router
from backend.app.api.routes.memory_forensics import router as memory_forensics_router
from backend.app.api.routes.plugins import router as plugins_router
from backend.app.api.routes.registry_scan import router as registry_scan_router
from backend.app.api.routes.settings import router as settings_router
from backend.app.api.routes.ssh import router as ssh_router
from backend.app.api.routes.toolbox import router as toolbox_router


app = FastAPI(title="Forensics Tool Web API")
app.include_router(health_router)
app.include_router(cases_router)
app.include_router(ai_analysis_router)
app.include_router(android_auto_forensics_router)
app.include_router(auto_forensics_router)
app.include_router(db_viewer_router)
app.include_router(file_browser_router)
app.include_router(registry_scan_router)
app.include_router(log_analysis_router)
app.include_router(mcp_server_router)
app.include_router(memory_forensics_router)
app.include_router(global_search_router)
app.include_router(extractor_router)
app.include_router(settings_router)
app.include_router(plugins_router)
app.include_router(ssh_router)
app.include_router(toolbox_router)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

if FRONTEND_ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS_DIR)), name="frontend-assets")


def _frontend_available() -> bool:
    return FRONTEND_INDEX_FILE.is_file()


@app.get("/", include_in_schema=False)
def frontend_index():
    if not _frontend_available():
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": "WebUI front-end build is missing. Run `npm run build` in the frontend directory.",
            },
        )
    return FileResponse(FRONTEND_INDEX_FILE)


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"ok": False, "message": f"Unknown API route: /{full_path}"})
    if not _frontend_available():
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": "WebUI front-end build is missing. Run `npm run build` in the frontend directory.",
            },
        )
    candidate = FRONTEND_DIST_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(FRONTEND_INDEX_FILE)
