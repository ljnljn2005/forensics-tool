内存取证工具已内置到项目目录，后续打包时请一并带上 `tools/memory`。

当前内置内容：
- `memprocfs/`：当前软件使用到的 MemProcFS 运行时文件最小集合
- `volatility3/`：Volatility 3 脚本、内置插件和符号目录

默认路径解析规则：
- 软件优先使用项目内的 `tools/memory`
- 如果用户手动指定了别的工具目录，也支持按同样结构加载

当前约定目录结构：

```text
tools/
  memory/
    memprocfs/
      MemProcFS.exe
      *.dll
      plugins/
    volatility3/
      vol.py
      volatility3/
        plugins/
        symbols/
```

说明：
- Volatility 3 默认使用当前应用运行时的 Python 解释器；如果后续打包成独立发行版，也可以在工具目录下额外放置 `python3/python.exe` 或 `python/python.exe`，软件会自动优先使用它。
- 当前没有再依赖历史的 `E:\...` 外部路径。
