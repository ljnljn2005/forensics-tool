import { useMemo, useState } from "react";

import AppShell, { type NavGroup } from "./layout/AppShell";
import AiAnalysisPage from "./pages/AiAnalysisPage";
import AndroidAutoForensicsPage from "./pages/AndroidAutoForensicsPage";
import AutoForensicsPage from "./pages/AutoForensicsPage";
import DatabaseViewerPage from "./pages/DatabaseViewerPage";
import ExtractorWorkbenchPage from "./pages/ExtractorWorkbenchPage";
import GlobalSearchPage from "./pages/GlobalSearchPage";
import HomeDashboardPage from "./pages/HomeDashboardPage";
import LogAnalysisPage from "./pages/LogAnalysisPage";
import McpServerSettingsPage from "./pages/McpServerSettingsPage";
import MemoryForensicsPage from "./pages/MemoryForensicsPage";
import PluginEditorPage from "./pages/PluginEditorPage";
import PluginMarketPage from "./pages/PluginMarketPage";
import RegistryScanPage from "./pages/RegistryScanPage";
import SettingsPage from "./pages/SettingsPage";
import SshForensicsPage from "./pages/SshForensicsPage";
import ToolboxPage from "./pages/ToolboxPage";

const navGroups: NavGroup[] = [
  { title: "总览", icon: "🏠", items: [{ key: "home", label: "主页", icon: "🏠" }] },
  {
    title: "Windows 取证",
    icon: "🪟",
    items: [
      { key: "windows-auto", label: "自动取证", icon: "⚙️" },
      {
        key: "windows-manual", label: "手动取证", icon: "🔧",
        children: [
          { key: "windows-local", label: "本地取证", icon: "📁" },
          { key: "windows-registry", label: "注册表取证", icon: "🧾" },
          { key: "windows-memory", label: "内存取证", icon: "🧠" },
          { key: "windows-logs", label: "日志分析", icon: "📜" },
        ],
      },
    ],
  },
  {
    title: "Linux 取证",
    icon: "🐧",
    items: [
      { key: "linux-auto", label: "自动取证", icon: "⚙️" },
      {
        key: "linux-manual", label: "手动取证", icon: "🔧",
        children: [
          { key: "linux-local", label: "本地取证", icon: "📁" },
          { key: "linux-ssh", label: "SSH 远程取证", icon: "🖧" },
          { key: "linux-memory", label: "内存取证", icon: "🧠" },
          { key: "linux-logs", label: "日志分析", icon: "📜" },
        ],
      },
    ],
  },
  {
    title: "Android 取证",
    icon: "🤖",
    items: [
      { key: "android-auto", label: "自动取证", icon: "⚙️" },
      {
        key: "android-manual", label: "手动取证", icon: "🔧",
        children: [
          { key: "android-local", label: "本地取证", icon: "📁" },
        ],
      },
    ],
  },
  {
    title: "iOS 取证",
    icon: "🍎",
    items: [
      { key: "ios-auto", label: "自动取证", icon: "⚙️" },
      {
        key: "ios-manual", label: "手动取证", icon: "🔧",
        children: [
          { key: "ios-local", label: "本地取证", icon: "📁" },
        ],
      },
    ],
  },
  {
    title: "插件市场",
    icon: "🧰",
    items: [{ key: "plugin-market", label: "插件市场", icon: "🧰" }],
  },
  {
    title: "插件编辑",
    icon: "✏️",
    items: [
      { key: "plugin-editor", label: "插件编辑器", icon: "✏️" },
    ],
  },
  {
    title: "工具箱",
    icon: "🧪",
    items: [{ key: "toolbox-jigsaw", label: "Jigsaw Puzzle", icon: "🧩" }],
  },
  {
    title: "其他功能",
    icon: "✨",
    items: [
      { key: "global-search", label: "全局搜索", icon: "🔎" },
      { key: "ai-analysis", label: "AI 分析", icon: "🤖" },
      { key: "mcp-server-settings", label: "MCP 服务器设置", icon: "🧩" },
      { key: "settings", label: "设置", icon: "⚙️" },
    ],
  },
];

function resolvePage(activeKey: string) {
  switch (activeKey) {
    case "windows-auto":
      return { title: "Windows 自动取证", subtitle: "自动提取 Windows 系统关键证据。", content: <AutoForensicsPage module="windows" /> };
    case "linux-auto":
      return { title: "Linux 自动取证", subtitle: "自动提取 Linux 系统关键证据。", content: <AutoForensicsPage module="linux" /> };
    case "android-auto":
      return { title: "Android 自动取证", subtitle: "扫描应用并按插件规则自动分析。", content: <AndroidAutoForensicsPage /> };
    case "ios-auto":
      return { title: "iOS 自动取证", subtitle: "自动提取 iOS 系统关键证据。", content: <AutoForensicsPage module="ios" /> };
    case "windows-registry":
      return { title: "Windows 注册表取证", subtitle: "读取离线 hive 并执行注册表分析。", content: <RegistryScanPage /> };
    case "windows-logs":
      return { title: "Windows 日志分析", subtitle: "扫描 EVTX 和常见日志文件。", content: <LogAnalysisPage module="windows" /> };
    case "linux-logs":
      return { title: "Linux 日志分析", subtitle: "扫描 /var/log 及常见日志文件。", content: <LogAnalysisPage module="linux" /> };
    case "windows-memory":
      return { title: "Windows 内存取证", subtitle: "浏览并执行常见内存分析任务。", content: <MemoryForensicsPage module="windows" /> };
    case "linux-memory":
      return { title: "Linux 内存取证", subtitle: "浏览并执行 Linux 内存分析任务。", content: <MemoryForensicsPage module="linux" /> };
    case "global-search":
      return { title: "全局搜索", subtitle: "搜索插件、积木、命令和模块。", content: <GlobalSearchPage /> };
    case "windows-local":
      return { title: "Windows 本地取证", subtitle: "离线提取工作台。", content: <ExtractorWorkbenchPage module="windows" /> };
    case "linux-local":
      return { title: "Linux 本地取证", subtitle: "Linux 离线提取工作台。", content: <ExtractorWorkbenchPage module="linux" /> };
    case "linux-ssh":
      return { title: "SSH 远程取证", subtitle: "连接远程主机并执行 SSH 取证插件。", content: <SshForensicsPage /> };
    case "android-local":
      return { title: "Android 本地取证", subtitle: "Android 映射路径提取工作台。", content: <ExtractorWorkbenchPage module="android" /> };
    case "ios-local":
      return { title: "iOS 本地取证", subtitle: "iOS 映射路径提取工作台。", content: <ExtractorWorkbenchPage module="ios" /> };
    case "plugin-market":
      return { title: "插件市场", subtitle: "浏览和安装插件。", content: <PluginMarketPage /> };
    case "plugin-editor":
      return { title: "插件编辑器", subtitle: "制作和管理取证插件。", content: <PluginEditorPage /> };
    case "toolbox-jigsaw":
      return { title: "工具箱", subtitle: "统一集成的取证辅助工具。", content: <ToolboxPage /> };
    case "ai-analysis":
      return { title: "AI 分析", subtitle: "分析取证内容与线索描述。", content: <AiAnalysisPage /> };
    case "mcp-server-settings":
      return { title: "MCP 服务器设置", subtitle: "配置 MCP 服务暴露范围，并逐步接入取证分析能力。", content: <McpServerSettingsPage /> };
    case "settings":
      return { title: "设置", subtitle: "管理代理、模型、仓库和路径设置。", content: <SettingsPage /> };
    case "home":
    default:
      return { title: "综合取证分析工具", subtitle: "新的内嵌 WebUI 主工作台。", content: <HomeDashboardPage /> };
  }
}

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const popup = params.get("popup");

  if (popup === "db-viewer") {
    return <DatabaseViewerPage mappingPath={params.get("mappingPath") ?? ""} databasePath={params.get("databasePath") ?? ""} />;
  }

  const [activeKey, setActiveKey] = useState("home");
  const page = useMemo(() => resolvePage(activeKey), [activeKey]);

  return (
    <AppShell title={page.title} subtitle={page.subtitle} navGroups={navGroups} activeKey={activeKey} onChange={setActiveKey}>
      {page.content}
    </AppShell>
  );
}
