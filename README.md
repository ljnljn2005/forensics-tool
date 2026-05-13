# Forensics Tool

A Python-based forensic analysis workbench with an embedded WebUI desktop shell.

## Recommended Start

Windows double-click:

```bash
start_webui.bat
```

Or run directly:

```bash
python main.py
```

This startup path will:

- build the bundled WebUI if `frontend/dist` is missing
- start the FastAPI backend inside the Python process
- open the application in a lightweight system WebView window
- avoid relying on an external browser or a separate Vite dev server

On Windows, the embedded window uses the system Edge WebView2 runtime through `pywebview`, so the packaged app no longer needs to ship a full Qt WebEngine stack.

## Development

Install Python dependencies:

```bash
pip install -r requirements.txt
```

If you are changing the WebUI frontend source, rebuild it with:

```bash
cd frontend
npm install --cache .npm-cache
npm run build
```
