from backend.app.services.ssh import run_ssh_plugin, test_ssh_connection


def ssh_test_connection(host: str, port: int, user: str, password: str) -> dict:
    payload = test_ssh_connection(host, port, user, password)
    return {
        "summary": {
            "host": host,
            "port": port,
            "user": user,
            "ok": bool(payload.get("ok")),
        },
        **payload,
    }


def ssh_run_plugin(host: str, port: int, user: str, password: str, plugin_name: str) -> dict:
    payload = run_ssh_plugin(host, port, user, password, plugin_name)
    return {
        "summary": {
            "host": host,
            "port": port,
            "user": user,
            "plugin_name": plugin_name,
            "ok": bool(payload.get("ok")),
            "result_count": len(payload.get("results", [])),
        },
        **payload,
    }
