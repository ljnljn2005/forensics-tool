import json
import os

import paramiko

from src.constants import PLUGINS_DIR


PLUGINS_FILE = os.path.join(PLUGINS_DIR, "ssh_plugins.json")


def test_ssh_connection(host: str, port: int, user: str, password: str) -> dict:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=user, password=password, timeout=8)
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        try:
            client.close()
        except Exception:
            pass
    return {"ok": True, "message": f"{host}:{port} 连接成功"}


def run_ssh_plugin(host: str, port: int, user: str, password: str, plugin_name: str) -> dict:
    plugin_payload = _load_plugins().get(plugin_name)
    if not plugin_payload:
        return {"ok": False, "message": "未找到插件", "results": []}
    blocks = plugin_payload.get("blocks", []) if isinstance(plugin_payload, dict) else plugin_payload

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=user, password=password, timeout=10)
    except Exception as exc:
        return {"ok": False, "message": str(exc), "results": []}
    results = []
    try:
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type", "")
            cmd = block.get("cmd", "")
            if not cmd or ("文件" in block_type or "提取" in block_type):
                continue
            stdin, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            results.append(
                {
                    "name": block.get("name", ""),
                    "cmd": cmd,
                    "type": block_type,
                    "output": out or err,
                }
            )
    finally:
        client.close()

    return {"ok": True, "results": results}


def _load_plugins() -> dict:
    try:
        with open(PLUGINS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
