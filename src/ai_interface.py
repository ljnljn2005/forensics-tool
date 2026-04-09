import json
import re
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import SubtitleLabel, PushButton, TextEdit, LineEdit, BodyLabel, InfoBar, InfoBarPosition
from .constants import PLUGINS_DIR


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
        try:
            result = self.analyze_with_ai(text)
            self.output.setPlainText(result)
        except Exception as e:
            InfoBar.error('分析失败', str(e), parent=self, position=InfoBarPosition.TOP)

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
                try:
                    import urllib.request
                    import urllib.error

                    data = json.dumps(payload).encode('utf-8')
                    req = urllib.request.Request(api_url, data=data, method='POST')
                    req.add_header('Content-Type', 'application/json')
                    # 接受两种形式：Bearer 开头或纯 key（自动加 Bearer）
                    if api_key.lower().startswith('bearer '):
                        req.add_header('Authorization', api_key)
                    else:
                        req.add_header('Authorization', f'Bearer {api_key}')

                    opener = urllib.request.build_opener()
                    if proxy:
                        # proxy 支持 http(s) 代理，如 http://127.0.0.1:7890
                        ph = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
                        opener = urllib.request.build_opener(ph)

                    with opener.open(req, timeout=30) as resp:
                        raw = resp.read().decode('utf-8')
                        try:
                            j = json.loads(raw)
                        except Exception:
                            return raw

                        # OpenAI 风格响应
                        if isinstance(j, dict) and 'choices' in j and len(j['choices']) > 0:
                            ch = j['choices'][0]
                            # chat-completions
                            if isinstance(ch, dict) and 'message' in ch and isinstance(ch['message'], dict) and 'content' in ch['message']:
                                return ch['message']['content']
                            # completion text
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
