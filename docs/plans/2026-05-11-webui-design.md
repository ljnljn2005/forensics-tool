# WebUI 替代桌面主界面设计

## 背景

当前项目的主界面基于 `PySide6` 桌面窗口，业务逻辑和界面逻辑大量耦合在 `src/*.py` 的 `QWidget` 页面中。随着取证页面数量增多，继续在桌面 UI 上叠加功能会带来三个问题：

1. 业务能力难以复用到 Web 端。
2. 页面状态、任务执行、结果展示都混在单个 QWidget 内，后续维护成本高。
3. 后续如果需要远程访问、统一部署、多人协作，桌面主界面会成为瓶颈。

因此，本次改造目标不是“再加一个网页壳”，而是逐步将当前桌面主界面替换为 `Python 后端 + 前端页面` 的 WebUI 架构。

## 目标

- 保留当前 Python 取证能力，避免重写核心分析逻辑。
- 新增一套独立的 WebUI 架构，逐步承接桌面版主界面职责。
- 先迁移最适合 Web 化的页面，建立统一导航、接口和任务返回模型。
- 桌面版在迁移过程中继续可用，直到 WebUI 足够覆盖主要流程。

## 非目标

- 第一阶段不替换全部桌面功能。
- 第一阶段不做多用户权限系统。
- 第一阶段不做完整任务队列或分布式执行。
- 第一阶段不直接重构所有现有 `src/*.py` 页面。

## 方案对比

### 方案 1：FastAPI + React + Vite

这是推荐方案。

后端负责对外暴露取证能力，前端负责工作台式 UI。页面、状态、导航、结果表格、预览区都放到 React 中，Python 只处理分析和数据返回。这样可以把“UI”与“取证逻辑”切开，适合后续长期演进。

优点：

- 架构清晰，适合逐步替代桌面版主界面。
- 前后端边界明确，便于后续远程部署。
- 复杂工作台 UI 更容易维护。
- 后续接任务系统、文件上传、远程执行更自然。

缺点：

- 需要新增前端工程。
- 需要先抽一层可复用 service。

### 方案 2：FastAPI + 模板页面

只用 Python 后端输出 HTML 模板，前端交互依赖服务端渲染或轻量 JS。

优点：

- 起步快。

缺点：

- 不适合你现在这种“导航 + 树/表 + 预览 + 异步任务”的工作台交互。
- 后续页面复杂后维护会很痛。

### 方案 3：Gradio / Streamlit

只能做验证原型，不适合当前产品。

优点：

- 原型速度快。

缺点：

- UI 可控性太低。
- 很难做出你现在这类专业取证工作台风格。
- 后续几乎一定会推倒重来。

## 结论

采用 `FastAPI + React + Vite`。

## 架构设计

### 总体结构

项目将逐步演进为三层：

1. `frontend/`
   - WebUI 页面
   - 左侧导航
   - 工作台布局
   - 调用后端 API

2. `backend/`
   - FastAPI 应用入口
   - 路由层
   - 请求/响应模型
   - Service 层封装

3. `src/`
   - 现有桌面版代码
   - 渐进式改为调用共享 service，而不是自己直接做业务

### 推荐目录

```text
backend/
  app/
    main.py
    api/
      routes/
    models/
    services/
    utils/
frontend/
  src/
    app/
    pages/
    components/
    services/
src/
  ...
```

## 分层策略

### 现状

例如：

- `src/extractor.py`
- `src/registry_interface.py`
- `src/log_analysis.py`
- `src/memory_forensics.py`

这些文件现在同时承担：

- 页面构建
- 状态维护
- 取证逻辑
- 文本结果格式化

### 目标

后续要把这些责任拆开：

1. Service 层
   - 纯 Python
   - 不依赖 Qt
   - 返回结构化数据

2. API 层
   - 把 Service 能力暴露成 HTTP 接口

3. UI 层
   - 桌面版 QWidget 或 React 页面
   - 只负责展示和调用

## 页面迁移顺序

### 第一阶段

优先迁移：

1. Android 自动取证
2. 注册表扫描

原因：

- 都是“给定路径 -> 扫描 -> 返回结构化结果”的模式。
- 对 WebUI 最友好。
- 依赖最少，不涉及复杂终端会话。

### 第二阶段

继续迁移：

1. Windows / Linux 日志分析
2. 本地取证工作台

### 第三阶段

最后迁移：

1. Windows / Linux 内存取证
2. SSH 远程取证
3. 本地终端

原因：

- 这几块都带有更强的异步执行和状态管理特征。

## 第一阶段页面设计

### 1. Android 自动取证页

Web 页面应包含：

- 映射路径输入框
- 扫描按钮
- 已识别应用列表
- 命中模板列表
- 自动分析结果面板

后端返回结构建议：

```json
{
  "mapping_path": "C:/evidence/android",
  "installed_packages": ["com.tencent.mm", "com.miui.notes"],
  "matched_packages": [
    {
      "package_name": "com.tencent.mm",
      "entries": [
        {
          "group": "微信提取",
          "name": "MicroMsg",
          "cmd": "/data/com.tencent.mm/MicroMsg/note.txt",
          "result": "..."
        }
      ]
    }
  ]
}
```

### 2. 注册表扫描页

Web 页面应包含：

- 映射路径输入框
- 扫描项列表
- 扫描结果表
- 详情预览区

## API 设计建议

第一阶段只做最少接口：

- `GET /api/health`
- `POST /api/android/auto-forensics/scan`
- `POST /api/windows/registry/scan`
- `GET /api/plugins/android/templates`

请求和响应统一 JSON 化，不直接返回桌面版那种拼好的大段文本作为主数据结构。文本可以保留为辅助字段。

## 兼容策略

### 桌面版短期内继续保留

桌面版仍然存在，继续作为过渡入口。

### 渐进式复用业务

WebUI 不直接调用 QWidget。

取而代之：

- 先把 Android 自动取证与注册表扫描的逻辑抽成 service
- 桌面版调用 service
- Web 版也调用同一份 service

这样以后替换主界面时，业务层不会被撕裂成两套。

## 错误处理

第一阶段统一处理这些情况：

- 映射路径不存在
- 插件模板为空
- 未识别到安装应用
- 命中模板但结果文件不存在
- 注册表读取失败

API 应返回结构化错误：

```json
{
  "ok": false,
  "message": "映射路径不存在"
}
```

## 测试策略

第一阶段至少覆盖：

- service 层单元测试
- API 层接口测试
- WebUI 页面基础渲染测试

桌面版原有测试继续保留，防止抽 service 时把现有功能带坏。

## 里程碑

### 里程碑 1

- 建立 `backend/` 与 `frontend/`
- 启动 WebUI 基础壳
- 有健康检查接口

### 里程碑 2

- Android 自动取证 service 化
- Web 页面接入 Android 自动取证

### 里程碑 3

- 注册表扫描 service 化
- Web 页面接入注册表扫描

### 里程碑 4

- 导航统一
- 可作为主入口进行基础取证工作

## 风险

1. 现有 QWidget 页面中混有太多业务逻辑，抽 service 时容易牵一发而动全身。
2. 结果数据目前很多还是文本型，Web 侧如果不提前做结构化，后面会重复返工。
3. 内存取证、SSH、终端类模块后续需要更强的异步任务模型，第一阶段不应提前过度设计。

## 推荐下一步

1. 建立 WebUI 第一阶段实施计划。
2. 先创建 `backend/app/main.py` 与 `frontend/` 壳工程。
3. 只实现 Android 自动取证与注册表扫描两页，不扩散到其他模块。
