import json
import re
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QObject, Signal, QThread
from qfluentwidgets import SubtitleLabel, PushButton, TextEdit, LineEdit, BodyLabel, InfoBar, InfoBarPosition

# 当作为独立脚本运行时，尝试回退到在父目录中查找 constants 模块，避免 "attempted relative import" 错误
try:
    from .constants import PLUGINS_DIR
except Exception:
    import sys
    import os as _os
    _root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '..'))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from constants import PLUGINS_DIR


class AiInterface(QWidget):
    """独立的 AI 分析界面：接收描述并返回分析结果（本地启发式 + 可选 OpenAI 兼容远程调用）。"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('aiInterface')

        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(24, 24, 24, 24)
        self.vbox.setSpacing(12)

        self.title = SubtitleLabel('AI 分析', self)
        self.vbox.addWidget(self.title)

        header = QHBoxLayout()
        self.promptEdit = LineEdit(self)
        self.promptEdit.setPlaceholderText('输入题目描述或要分析的内容...')
        self.analyzeBtn = PushButton('分析', self)
        header.addWidget(self.promptEdit, 2)
        header.addWidget(self.analyzeBtn)
        self.vbox.addLayout(header)

        self.output = TextEdit(self)
        self.output.setReadOnly(True)
        self.vbox.addWidget(self.output, 1)

        self.analyzeBtn.clicked.connect(self.perform_analysis)
        # 按 Enter 触发分析
        try:
            self.promptEdit.returnPressed.connect(self.perform_analysis)
        except Exception:
            pass

    def perform_analysis(self):
        text = self.promptEdit.text().strip()
        if not text:
            InfoBar.info('分析提示', '请先输入文本。', parent=self)
            return
        # 在后台线程执行分析，避免阻塞 UI
        # 如有正在运行的线程，先安全停止
        try:
            if hasattr(self, '_ai_thread') and self._ai_thread and self._ai_thread.isRunning():
                self._stop_current_thread()
        except Exception:
            pass

        self.analyzeBtn.setEnabled(False)
        self.promptEdit.setEnabled(False)
        self.output.setPlainText('正在分析，请稍候...')

        # 使用流式输出（若远程模型支持），否则回退到一次性输出
        worker = _AiWorker(self.analyze_with_ai, text, stream=True)
        thread = QThread()
        worker.moveToThread(thread)
        # 保存引用，防止被 GC
        self._ai_worker = worker
        self._ai_thread = thread

        def _on_finished(res: str):
            # 完成时仅在有返回文本时覆盖（避免覆盖流式期间已追加的文本）
            if res:
                try:
                    self.output.setPlainText(res)
                except Exception:
                    pass
            self.analyzeBtn.setEnabled(True)
            self.promptEdit.setEnabled(True)

        def _on_error(err: str):
            InfoBar.error('分析失败', err, parent=self, position=InfoBarPosition.TOP)
            self.analyzeBtn.setEnabled(True)
            self.promptEdit.setEnabled(True)

        def _on_progress(chunk: str):
            # 追加流式片段（保持光标在末尾）
            try:
                cur = self.output.toPlainText()
                if not cur or cur == '正在分析，请稍候...':
                    self.output.setPlainText(chunk)
                else:
                    self.output.setPlainText(cur + chunk)
            except Exception:
                pass

        thread.started.connect(worker.run)
        worker.finished.connect(_on_finished)
        worker.error.connect(_on_error)
        worker.progress.connect(_on_progress)
        # 清理
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.start()

    def _on_thread_finished(self):
        # 清理保存的引用
        try:
            if hasattr(self, '_ai_thread'):
                self._ai_thread = None
        except Exception:
            pass
        try:
            if hasattr(self, '_ai_worker'):
                self._ai_worker = None
        except Exception:
            pass

    def _stop_current_thread(self, wait_ms: int = 2000):
        """请求停止当前正在运行的 AI 线程并等待其退出（最多 wait_ms 毫秒）。"""
        try:
            thr = getattr(self, '_ai_thread', None)
            if thr and thr.isRunning():
                thr.quit()
                thr.wait(wait_ms)
        except Exception:
            pass

    def closeEvent(self, event):
        # 在窗口关闭前确保后台线程已停止，避免 QThread 在运行时被销毁
        try:
            self._stop_current_thread(wait_ms=2000)
        except Exception:
            pass
        return super().closeEvent(event)

    def analyze_with_ai(self, text: str) -> str:
        # 简单关键词抽取
        tokens = re.findall(r"[\u4e00-\u9fff\w]+", text)
        freq = {}
        for t in tokens:
            if len(t) <= 1:
                continue
            freq[t] = freq.get(t, 0) + 1
        sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [k for k, v in sorted_tokens[:10]]

        # 猜测考察点
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

        # 远程模型调用（若配置） - 支持代理、默认 OpenAI endpoint
        remote_err = ''
        try:
            from .constants import get_app_settings
            cfg = get_app_settings()
            api_url = (cfg.get('api_url') or '').strip()
            api_key = (cfg.get('api_key') or '').strip()
            model = (cfg.get('model') or '').strip() or 'gpt-3.5-turbo'
            proxy = (cfg.get('proxy') or '').strip()

            # 如果没有配置 api_url，但是配置了 api_key，则默认使用 OpenAI chat completions endpoint
            if not api_url and api_key:
                api_url = 'https://api.openai.com/v1/chat/completions'

            if api_url and api_key:
                payload = {
                    'model': model,
                    'messages': [{'role': 'user', 'content': text}],
                    'max_tokens': 512,
                    'temperature': 0.2
                }
                # 可配置超时（秒），默认 120s
                timeout = int(cfg.get('api_timeout') or 120)
                proxies = None
                if proxy:
                    proxies = {'http': proxy, 'https': proxy}

                # 首选使用 requests（更好处理 timeout 与 proxies），若不可用回退到 urllib
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
                            # 读超时，若是第一次尝试则重试一次
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

                # 如果没有 requests 或 requests 调用不可用，回退到 urllib
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


def analyze_with_ai_stream(text: str):
    """尝试对远程模型发起流式请求，逐步 yield 字符串片段。
    兼容 OpenAI-style streaming（每行 data: JSON 或直接 JSON 行），遇到 [DONE] 停止。
    如果远程不支持流式，会抛出异常以回退到一次性请求。
    """
    from .constants import get_app_settings
    cfg = get_app_settings()
    api_url = (cfg.get('api_url') or '').strip()
    api_key = (cfg.get('api_key') or '').strip()
    proxy = (cfg.get('proxy') or '').strip()
    if not api_url or not api_key:
        raise RuntimeError('未配置远程模型地址或 API Key')

    timeout = int(cfg.get('api_timeout') or 120)
    proxies = None
    if proxy:
        proxies = {'http': proxy, 'https': proxy}

    payload = {
        'model': (cfg.get('model') or 'gpt-3.5-turbo'),
        'messages': [{'role': 'user', 'content': text}],
        'max_tokens': 2000,
        'temperature': 0.2,
        'stream': True
    }

    try:
        import requests
    except Exception:
        raise RuntimeError('requests 模块不可用，无法进行流式请求')

    headers = {'Content-Type': 'application/json'}
    if api_key.lower().startswith('bearer '):
        headers['Authorization'] = api_key
    else:
        headers['Authorization'] = f'Bearer {api_key}'

    with requests.post(api_url, headers=headers, json=payload, stream=True, timeout=timeout, proxies=proxies) as resp:
        resp.raise_for_status()
        buffer = ''
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            text_line = line.strip()
            # 支持 'data: [DONE]' 或 '[DONE]'
            if text_line == '[DONE]' or text_line.endswith('[DONE]') or text_line == 'data: [DONE]':
                break
            # 移除 'data: ' 前缀
            if text_line.startswith('data:'):
                text_line = text_line[len('data:'):].strip()
            try:
                j = json.loads(text_line)
            except Exception:
                # 非 JSON 内容直接作为文本片段
                yield text_line
                continue

            # OpenAI-style chunk
            try:
                ch = j.get('choices')[0]
                # delta content 优先
                if isinstance(ch, dict):
                    delta = ch.get('delta') or {}
                    content = delta.get('content') or ch.get('text') or ''
                else:
                    content = ''
            except Exception:
                content = ''

            if content:
                yield content


class _AiWorker(QObject):
    """后台 worker：在单独线程运行传入的 call(callable) 并发回结果或错误信息。"""
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, func, text, stream: bool = False):
        super().__init__()
        self.func = func
        self.text = text
        self.stream = stream

    def run(self):
        try:
            # 如果请求流式输出且远程调用支持，我们尝试使用内置流式方法
            if self.stream:
                try:
                    self._accum = ''
                    for chunk in analyze_with_ai_stream(self.text):
                        # chunk 可能很小，逐步发出
                        try:
                            self._accum += chunk
                        except Exception:
                            pass
                        self.progress.emit(chunk)
                    # 发出累积的完整结果
                    self.finished.emit(getattr(self, '_accum', ''))
                    return
                except Exception:
                    # 流式失败则回退到一次性调用
                    pass

            res = self.func(self.text)
            if not isinstance(res, str):
                try:
                    res = json.dumps(res, ensure_ascii=False)
                except Exception:
                    res = str(res)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))

    def output_accumulated(self) -> str:
        return getattr(self, '_accum', '')
