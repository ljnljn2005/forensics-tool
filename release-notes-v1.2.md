# Forensics Tool v1.2

## 重点更新

- 启动流程加入本地激活校验；用户可联系作者获取 `activation.lic`。
- 发布包准备了 Python/venv 运行方式，并尝试生成 WebView EXE。
- 发布前会排除激活码生成器、测试激活文件、运行日志、数据库和其他敏感信息。
- README 和设置页补充了开源项目致谢与跳转链接。

## 激活码

软件启动时会读取项目根目录或 `settings/activation.lic`。
如需激活码，请联系作者并提供软件提示的机器码。

## 打包说明

如果 EXE 打包成功，直接运行发布包中的 EXE 会打开 WebView 界面。
如果当前机器无法完成 EXE 打包，可使用发布包中的 Python 运行方式：

```bat
start_webui.bat
```

首次运行前请确认 `venv` 已按 `requirements.txt` 安装依赖，前端资源已构建到 `frontend/dist`。

## 不进入 GitHub 的文件

- `activation.lic`
- `activation_generator.py`
- `activation_generator.bat`
- `private/`
- `release/`、`dist/`、`build/` 等打包产物目录
- 本地配置、日志、数据库和其他敏感信息
