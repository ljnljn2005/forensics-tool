# WebUI Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first WebUI foundation that can gradually replace the desktop main interface, starting with Android auto forensics and Windows registry scanning.

**Architecture:** Keep Python forensics logic in shared services, expose those services through FastAPI, and build a React + Vite workbench UI that consumes structured JSON APIs. Do not reimplement analysis logic in the frontend and do not let the web layer depend on Qt widgets.

**Tech Stack:** Python, FastAPI, Pydantic, React, Vite, TypeScript, existing unittest test suite

---

### Task 1: Create the backend application skeleton

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Test: `tests/test_web_backend_health.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from backend.app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover tests -p "test_web_backend_health.py"`
Expected: FAIL because `backend.app.main` or the route does not exist.

**Step 3: Write minimal implementation**

Create a FastAPI app and register a `/api/health` route that returns `{"ok": True}`.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover tests -p "test_web_backend_health.py"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app tests/test_web_backend_health.py
git commit -m "feat: add web backend skeleton"
```

### Task 2: Extract Android auto-forensics logic into a Qt-free service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/android_auto_forensics.py`
- Modify: `src/extractor.py`
- Test: `tests/test_android_auto_forensics_service.py`

**Step 1: Write the failing test**

```python
import os
import shutil

from backend.app.services.android_auto_forensics import scan_android_apps


def test_scan_android_apps_returns_installed_and_matched_packages():
    root = os.path.join(os.getcwd(), "_android_service_test")
    os.makedirs(os.path.join(root, "data", "system"), exist_ok=True)
    os.makedirs(os.path.join(root, "data", "com.tencent.mm", "MicroMsg"), exist_ok=True)
    with open(os.path.join(root, "data", "system", "packages.list"), "w", encoding="utf-8") as handle:
        handle.write("com.tencent.mm 1000 0 /data/user/0/com.tencent.mm default none 0 0 1 @null\n")
    with open(os.path.join(root, "data", "com.tencent.mm", "MicroMsg", "note.txt"), "w", encoding="utf-8") as handle:
        handle.write("wechat evidence")

    entries = [
        {
            "group": "微信提取",
            "name": "MicroMsg",
            "cmd": "/data/com.tencent.mm/MicroMsg/note.txt",
            "type": "文件提取",
            "module": "android",
        }
    ]

    result = scan_android_apps(root, entries)

    assert "com.tencent.mm" in result["installed_packages"]
    assert result["matched_packages"][0]["package_name"] == "com.tencent.mm"
    shutil.rmtree(root, ignore_errors=True)
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover tests -p "test_android_auto_forensics_service.py"`
Expected: FAIL because the service module does not exist.

**Step 3: Write minimal implementation**

Move the pure analysis logic out of `src/extractor.py` into `backend/app/services/android_auto_forensics.py`, including:
- package name extraction
- installed package collection
- template match grouping
- per-entry file extraction calls through a pure helper

Leave `src/extractor.py` calling the shared service.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover tests -p "test_android_auto_forensics_service.py"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services src/extractor.py tests/test_android_auto_forensics_service.py
git commit -m "refactor: extract android auto forensics service"
```

### Task 3: Expose Android auto-forensics through an API route

**Files:**
- Create: `backend/app/models/android_auto_forensics.py`
- Create: `backend/app/api/routes/android_auto_forensics.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_web_android_auto_forensics_api.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from backend.app.main import app


def test_android_auto_forensics_api_returns_scan_result():
    client = TestClient(app)
    response = client.post(
        "/api/android/auto-forensics/scan",
        json={"mapping_path": "C:/evidence/android", "entries": []},
    )
    assert response.status_code in {200, 400}
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover tests -p "test_web_android_auto_forensics_api.py"`
Expected: FAIL because the route does not exist.

**Step 3: Write minimal implementation**

Add a Pydantic request model and response shape. Wire the route to the Android service and return structured JSON.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover tests -p "test_web_android_auto_forensics_api.py"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app tests/test_web_android_auto_forensics_api.py
git commit -m "feat: add android auto forensics api"
```

### Task 4: Extract registry scanning into a shared service

**Files:**
- Create: `backend/app/services/registry_scan.py`
- Modify: `src/registry_interface.py`
- Modify: `src/windows_registry.py`
- Test: `tests/test_registry_scan_service.py`

**Step 1: Write the failing test**

```python
from backend.app.services.registry_scan import build_registry_scan_response


def test_build_registry_scan_response_wraps_text_result():
    result = build_registry_scan_response("demo", "scan output")
    assert result["scan_item"] == "demo"
    assert result["text"] == "scan output"
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover tests -p "test_registry_scan_service.py"`
Expected: FAIL because the service module does not exist.

**Step 3: Write minimal implementation**

Create a lightweight service wrapper that standardizes registry scan results for both Qt and Web callers.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover tests -p "test_registry_scan_service.py"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services src/registry_interface.py src/windows_registry.py tests/test_registry_scan_service.py
git commit -m "refactor: add registry scan service"
```

### Task 5: Expose registry scanning through an API route

**Files:**
- Create: `backend/app/models/registry_scan.py`
- Create: `backend/app/api/routes/registry_scan.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_web_registry_scan_api.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from backend.app.main import app


def test_registry_scan_api_exists():
    client = TestClient(app)
    response = client.post("/api/windows/registry/scan", json={"mapping_path": "C:/evidence", "scan_item": "default_apps"})
    assert response.status_code in {200, 400}
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover tests -p "test_web_registry_scan_api.py"`
Expected: FAIL because the route does not exist.

**Step 3: Write minimal implementation**

Add the route, request model, and JSON response schema, backed by the registry scan service.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover tests -p "test_web_registry_scan_api.py"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app tests/test_web_registry_scan_api.py
git commit -m "feat: add registry scan api"
```

### Task 6: Create the frontend scaffold and base layout

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/layout/AppShell.tsx`
- Create: `frontend/src/styles.css`

**Step 1: Write the failing test**

If using a frontend test stack in this phase, add a minimal render test. If not, treat the missing build command as the failing signal.

Expected first command:

```bash
npm install
npm run build
```

Expected: FAIL because the frontend project does not exist yet.

**Step 2: Run command to verify it fails**

Run: `npm run build`
Expected: FAIL with missing `package.json`

**Step 3: Write minimal implementation**

Create a Vite + React + TypeScript app shell with:
- left navigation
- top title area
- center content outlet

**Step 4: Run build to verify it passes**

Run: `npm install`
Run: `npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend
git commit -m "feat: scaffold web frontend shell"
```

### Task 7: Build the Android auto-forensics page in the frontend

**Files:**
- Create: `frontend/src/pages/AndroidAutoForensicsPage.tsx`
- Create: `frontend/src/services/api.ts`
- Modify: `frontend/src/App.tsx`

**Step 1: Write the failing test**

If frontend tests are present, write a render test that checks:
- mapping path input exists
- scan button exists
- results section renders

Otherwise use `npm run build` after wiring imports as the failure checkpoint.

**Step 2: Run test or build to verify it fails**

Run: `npm run build`
Expected: FAIL until the page and imports exist.

**Step 3: Write minimal implementation**

Create a page with:
- mapping path input
- scan button
- installed package list
- matched app results list
- detail text panel

Call `/api/android/auto-forensics/scan`.

**Step 4: Run build to verify it passes**

Run: `npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend
git commit -m "feat: add android auto forensics page"
```

### Task 8: Build the registry scan page in the frontend

**Files:**
- Create: `frontend/src/pages/RegistryScanPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/services/api.ts`

**Step 1: Write the failing test**

Add a frontend test or use the missing route wiring as the failing checkpoint.

**Step 2: Run test or build to verify it fails**

Run: `npm run build`
Expected: FAIL until the registry page is wired in.

**Step 3: Write minimal implementation**

Create a page with:
- mapping path input
- scan item selection
- run button
- result table or text preview

Call `/api/windows/registry/scan`.

**Step 4: Run build to verify it passes**

Run: `npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend
git commit -m "feat: add registry scan page"
```

### Task 9: Add local launch documentation for the WebUI

**Files:**
- Modify: `README.md`

**Step 1: Write the failing check**

Decide the expected local startup commands and verify the README does not yet document them.

**Step 2: Run verification**

Check: `rg -n "FastAPI|Vite|frontend|backend" README.md`
Expected: Missing or incomplete instructions.

**Step 3: Write minimal implementation**

Document:
- backend startup
- frontend startup
- development URLs
- scope of the first WebUI phase

**Step 4: Verify documentation exists**

Run: `rg -n "FastAPI|Vite|frontend|backend" README.md`
Expected: Matches present

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add webui development instructions"
```

### Task 10: Run full regression verification

**Files:**
- No code changes required unless regressions appear

**Step 1: Run backend tests**

Run: `python -m unittest discover tests`
Expected: PASS

**Step 2: Run frontend build**

Run: `npm run build`
Expected: PASS

**Step 3: Run manual smoke test**

Run backend locally and frontend locally, then verify:
- `/api/health`
- Android auto-forensics page loads
- Registry scan page loads

**Step 4: Commit final fixes if needed**

```bash
git add -A
git commit -m "test: verify first webui migration phase"
```
