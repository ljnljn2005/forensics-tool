import { useEffect, useState } from "react";

import {
  exportMcpConfig,
  loadMcpSettings,
  saveMcpSettings,
  type McpExportResult,
  type McpServerSettings,
  type McpServerSettingsResult,
} from "../services/api";

const emptySettings: McpServerSettings = {
  enabled: false,
  transport: "stdio",
  host: "127.0.0.1",
  port: 8765,
  auto_start: false,
  exposed_tool_groups: ["cases", "android_auto_forensics", "file_browser", "database"],
};

export default function McpServerSettingsPage() {
  const [payload, setPayload] = useState<McpServerSettingsResult | null>(null);
  const [settings, setSettings] = useState<McpServerSettings>(emptySettings);
  const [exportPayload, setExportPayload] = useState<McpExportResult | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");

  useEffect(() => {
    loadMcpSettings()
      .then((result) => {
        setPayload(result);
        setSettings(result.settings);
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "MCP 设置加载失败"));

    exportMcpConfig()
      .then(setExportPayload)
      .catch(() => undefined);
  }, []);

  async function handleSave() {
    setError("");
    setMessage("");
    try {
      const result = await saveMcpSettings(settings);
      setPayload(result);
      setSettings(result.settings);
      setMessage("MCP 服务器设置已保存。");
      const exported = await exportMcpConfig();
      setExportPayload(exported);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "MCP 设置保存失败");
    }
  }

  function toggleGroup(groupKey: string) {
    setSettings((current) => ({
      ...current,
      exposed_tool_groups: current.exposed_tool_groups.includes(groupKey)
        ? current.exposed_tool_groups.filter((item) => item !== groupKey)
        : [...current.exposed_tool_groups, groupKey],
    }));
  }

  async function copyText(label: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyMessage(`${label} 已复制。`);
      window.setTimeout(() => setCopyMessage(""), 2500);
    } catch {
      setCopyMessage("复制失败，请手动复制。");
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-card">
        <div>
          <div className="eyebrow">MCP Server</div>
          <h2>把取证分析能力逐步暴露给 AI 使用</h2>
          <p>这一页先管理 MCP 服务器配置、工具组暴露范围，以及可直接导入 Agent 软件的 MCP 配置片段。</p>
        </div>
      </section>

      <div className="workbench-grid">
        <section className="panel">
          <h2>服务器配置</h2>
          <div className="single-column-form">
            <label className="checkbox-line">
              <input type="checkbox" checked={settings.enabled} onChange={(event) => setSettings({ ...settings, enabled: event.target.checked })} />
              启用 MCP 服务器
            </label>
            <label className="checkbox-line">
              <input type="checkbox" checked={settings.auto_start} onChange={(event) => setSettings({ ...settings, auto_start: event.target.checked })} />
              启动主程序时自动启动
            </label>
            <label className="field-label">
              传输方式
              <select value={settings.transport} onChange={(event) => setSettings({ ...settings, transport: event.target.value as "stdio" | "http" })}>
                <option value="stdio">stdio</option>
                <option value="http">http</option>
              </select>
            </label>
            <label className="field-label">
              Host
              <input value={settings.host} onChange={(event) => setSettings({ ...settings, host: event.target.value })} disabled={settings.transport !== "http"} />
            </label>
            <label className="field-label">
              Port
              <input value={String(settings.port)} onChange={(event) => setSettings({ ...settings, port: Number(event.target.value || "8765") })} disabled={settings.transport !== "http"} />
            </label>
          </div>
          <div className="button-row top-space">
            <button className="primary-button" onClick={handleSave}>
              保存 MCP 设置
            </button>
            {message ? <span className="success-text">{message}</span> : null}
          </div>
          {error ? <p className="error-text">{error}</p> : null}
        </section>

        <section className="panel panel-span-2">
          <h2>工具组暴露范围</h2>
          <div className="list-stack">
            {payload?.tool_groups.map((group) => (
              <article key={group.key} className="result-card">
                <div className="button-row">
                  <strong>{group.label}</strong>
                  <span className={payload.status.implemented_groups.includes(group.key) ? "status-pill ready" : "status-pill pending"}>
                    {payload.status.implemented_groups.includes(group.key) ? "已接入骨架" : "排队中"}
                  </span>
                </div>
                <p className="muted-text top-space">工具组键: {group.key}</p>
                <div className="tag-list top-space">
                  {group.tools.map((toolName) => (
                    <span key={toolName} className="tag-chip">
                      {toolName}
                    </span>
                  ))}
                </div>
                <label className="checkbox-line top-space">
                  <input type="checkbox" checked={settings.exposed_tool_groups.includes(group.key)} onChange={() => toggleGroup(group.key)} />
                  允许通过 MCP 暴露这个工具组
                </label>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className="panel">
        <h2>一键导出 Agent 配置</h2>
        {copyMessage ? <p className="success-text">{copyMessage}</p> : null}
        {exportPayload ? (
          <div className="list-stack">
            <article className="result-card">
              <div className="button-row">
                <strong>当前推荐配置</strong>
                <button className="secondary-button" onClick={() => copyText("当前推荐配置", exportPayload.active_json)}>
                  复制 JSON
                </button>
              </div>
              <p className="muted-text top-space">当前传输方式: {exportPayload.transport}</p>
              <pre>{exportPayload.active_json}</pre>
            </article>

            <article className="result-card">
              <div className="button-row">
                <strong>stdio 导入配置</strong>
                <button className="secondary-button" onClick={() => copyText("stdio 配置", exportPayload.stdio_json)}>
                  复制 JSON
                </button>
              </div>
              <p className="muted-text top-space">适合大多数支持 `mcpServers` 的 Agent 客户端。</p>
              <pre>{exportPayload.stdio_json}</pre>
            </article>

            <article className="result-card">
              <div className="button-row">
                <strong>HTTP 导入配置</strong>
                <button className="secondary-button" onClick={() => copyText("HTTP 配置", exportPayload.http_json)}>
                  复制 JSON
                </button>
              </div>
              <p className="muted-text top-space">适合支持 URL 型 MCP 的客户端。</p>
              <pre>{exportPayload.http_json}</pre>
            </article>

            <article className="result-card">
              <div className="button-row">
                <strong>连接信息</strong>
                <button className="secondary-button" onClick={() => copyText("HTTP 地址", exportPayload.http_url)}>
                  复制地址
                </button>
              </div>
              <p className="muted-text top-space">Python: {exportPayload.python_executable}</p>
              <p className="muted-text">项目目录: {exportPayload.project_root}</p>
              <p className="muted-text">模块: {exportPayload.module}</p>
              <pre>{exportPayload.http_url}</pre>
            </article>

            <article className="result-card">
              <strong>说明</strong>
              <ul className="top-space">
                {exportPayload.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </article>
          </div>
        ) : (
          <p className="muted-text">导出配置准备中。</p>
        )}
      </section>

      <section className="panel">
        <h2>当前状态</h2>
        <div className="status-grid">
          <div className={payload?.status.running ? "status-pill ready" : "status-pill pending"}>
            运行状态: {payload?.status.running ? "运行中" : "未运行"}
          </div>
          <div className="status-pill ready">Server 模块: {payload?.status.server_module ?? "mcp_server.server"}</div>
          <div className="status-pill ready">已实现骨架: {(payload?.status.implemented_groups ?? []).join(", ") || "无"}</div>
        </div>
      </section>
    </div>
  );
}
