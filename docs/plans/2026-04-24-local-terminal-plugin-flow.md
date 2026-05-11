# Local Terminal Plugin Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the local terminal plugin workflow clearer by scoping plugin blocks to the selected plugin, surfacing empty states, and focusing results automatically.

**Architecture:** Keep the current `LocalTerminalInterface` layout, but tighten the data flow around plugin selection. The left plugin list becomes the source of truth for the current plugin, the right-side block selector is repopulated from that selection, and result tabs continue to render through the existing stacked widget flow.

**Tech Stack:** Python, PySide6, qfluentwidgets, unittest

---

### Task 1: Lock in plugin-selection behavior with tests

**Files:**
- Modify: `tests/test_local_terminal.py`
- Test: `tests/test_local_terminal.py`

**Step 1: Write the failing test**

Add tests covering:
- Selecting a plugin only loads that plugin's local/all blocks into `pluginSelect`
- Running plugin blocks without a selected plugin shows a user-facing info message
- Extracting with no selected plugin shows a user-facing info message instead of executing defaults

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover tests`
Expected: FAIL because the current implementation still populates all plugin blocks and falls back to default execution.

**Step 3: Write minimal implementation**

Update `src/local_terminal.py` so plugin selection drives the dropdown content and empty-state messaging.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover tests`
Expected: PASS

### Task 2: Improve plugin execution messaging

**Files:**
- Modify: `src/local_terminal.py`
- Test: `tests/test_local_terminal.py`

**Step 1: Write the failing test**

Add tests covering:
- File-extraction blocks render a clear explanatory message
- New result tabs become the active tab automatically

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover tests`
Expected: FAIL because the current copy is generic and the empty-state path still needs refinement.

**Step 3: Write minimal implementation**

Refine the file-block message copy and keep result-tab focus behavior explicit.

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover tests`
Expected: PASS
