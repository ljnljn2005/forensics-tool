import json
import re

from src.constants import get_app_settings


def _analyze_with_ai(text: str) -> str:
    """Analyze text (local heuristic + optional OpenAI remote call)."""
    tokens = re.findall(r"[\u4e00-\u9fff\w]+", text)
    freq = {}
    for t in tokens:
        if len(t) <= 1:
            continue
        freq[t] = freq.get(t, 0) + 1
    sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    keywords = [k for k, v in sorted_tokens[:10]]

    points = []
    low = text.lower()
    if 'ssh' in low or '远程' in text:
        points.append('远程登录/SSH相关取证（连接历史、账号、授权密钥）')
    if 'web' in low or 'panel' in low or '面板' in text:
        points.append('Web 面板/面向服务的配置与敏感文件')
    if 'disk' in low or '磁盘' in text or '分区' in text:
        points.append('磁盘/分区/文件系统取证（挂载点、重要文件）')
    if 'process' in low or '进程' in text or 'ps ' in low:
        points.append('进程与网络连接（ps、netstat/ss 输出）')
    if not points:
        points.append('常规配置与敏感信息查找（用户、服务、网络、计划任务）')

    collect = [
        '系统信息 (uname, hostname, /etc/*)',
        '用户相关 (/home, /var/log/auth.log, last, w)',
        '网络连接 (ss/netstat, ip a)',
        '计划任务 (crontab, systemd timers)'
    ]

    # Remote model call
    remote_err = ''
    try:
        cfg = get_app_settings()
        api_url = (cfg.get('api_url') or '').strip()
        api_key = (cfg.get('api_key') or '').strip()
        model = (cfg.get('model') or '').strip() or 'gpt-3.5-turbo'
        proxy = (cfg.get('proxy') or '').strip()

        if not api_url and api_key:
            api_url = 'https://api.openai.com/v1/chat/completions'

        if api_url and api_key:
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': text}],
                'max_tokens': 512,
                'temperature': 0.2
            }
            timeout = int(cfg.get('api_timeout') or 120)
            proxies = None
            if proxy:
                proxies = {'http': proxy, 'https': proxy}

            tried_requests = False
            try:
                import requests
                tried_requests = True
                headers = {'Content-Type': 'application/json'}
                if api_key.lower().startswith('bearer '):
                    headers['Authorization'] = api_key
                else:
                    headers['Authorization'] = f'Bearer {api_key}'

                for attempt in range(2):
                    try:
                        resp = requests.post(api_url, headers=headers, json=payload, timeout=timeout, proxies=proxies)
                        resp.raise_for_status()
                        j = resp.json()
                        if isinstance(j, dict) and 'choices' in j and len(j['choices']) > 0:
                            ch = j['choices'][0]
                            if isinstance(ch, dict) and 'message' in ch and isinstance(ch['message'], dict) and 'content' in ch['message']:
                                return ch['message']['content']
                            if 'text' in ch:
                                return ch['text']
                        return json.dumps(j, ensure_ascii=False)
                    except requests.exceptions.ReadTimeout:
                        if attempt == 0:
                            continue
                        remote_err = f"(远程模型调用失败: ReadTimeout after {timeout}s)"
                    except requests.exceptions.HTTPError as he:
                        remote_err = f"(远程模型调用失败: HTTP {resp.status_code} - {resp.text})"
                        break
                    except Exception as e:
                        remote_err = f"(远程模型调用失败: {e})"
                        break
            except Exception:
                tried_requests = False

            if not tried_requests:
                try:
                    import urllib.request
                    import urllib.error

                    data = json.dumps(payload).encode('utf-8')
                    req = urllib.request.Request(api_url, data=data, method='POST')
                    req.add_header('Content-Type', 'application/json')
                    if api_key.lower().startswith('bearer '):
                        req.add_header('Authorization', api_key)
                    else:
                        req.add_header('Authorization', f'Bearer {api_key}')

                    opener = urllib.request.build_opener()
                    if proxy:
                        ph = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
                        opener = urllib.request.build_opener(ph)

                    with opener.open(req, timeout=timeout) as resp:
                        raw = resp.read().decode('utf-8')
                        try:
                            j = json.loads(raw)
                        except Exception:
                            return raw
                        if isinstance(j, dict) and 'choices' in j and len(j['choices']) > 0:
                            ch = j['choices'][0]
                            if isinstance(ch, dict) and 'message' in ch and isinstance(ch['message'], dict) and 'content' in ch['message']:
                                return ch['message']['content']
                            if 'text' in ch:
                                return ch['text']
                        return raw
                except urllib.error.HTTPError as he:
                    try:
                        err_body = he.read().decode('utf-8')
                    except Exception:
                        err_body = str(he)
                    remote_err = f"(远程模型调用失败: {he.code} {he.reason} - {err_body})"
                except Exception as e:
                    remote_err = f"(远程模型调用失败: {e})"
    except Exception:
        remote_err = ''

    out = []
    out.append('== 自动抽取关键词 ==')
    out.append(', '.join(keywords) or '无')
    out.append('\n== 猜测可能考察点 ==')
    out.extend(['- ' + p for p in points])
    out.append('\n== 建议采集项 ==')
    out.extend(['- ' + c for c in collect])
    if remote_err:
        out.append('\n' + remote_err)
    return '\n'.join(out)


def run_ai_analysis(text: str) -> dict:
    result = _analyze_with_ai(text)
    return {
        "text": text,
        "result": result,
    }
