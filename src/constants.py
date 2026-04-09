import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BASE_DIR)  # project root
SETTINGS_DIR = os.path.join(BASE_DIR, 'settings')
PLUGINS_DIR = os.path.join(BASE_DIR, 'plugins')
os.makedirs(SETTINGS_DIR, exist_ok=True)
os.makedirs(PLUGINS_DIR, exist_ok=True)

def get_app_proxy():
    import json
    config_file = os.path.join(SETTINGS_DIR, 'app_settings.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('proxy', '')
        except Exception:
            pass
    return ''

def save_app_proxy(proxy_str):
    import json
    config_file = os.path.join(SETTINGS_DIR, 'app_settings.json')
    config = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            pass
    config['proxy'] = proxy_str
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)


def get_app_settings():
    import json
    config_file = os.path.join(SETTINGS_DIR, 'app_settings.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_app_settings(settings_dict: dict):
    import json
    config_file = os.path.join(SETTINGS_DIR, 'app_settings.json')
    cur = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cur = json.load(f)
        except Exception:
            cur = {}
    cur.update(settings_dict or {})
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(cur, f, indent=4, ensure_ascii=False)
