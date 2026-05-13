import { useEffect, useMemo, useState } from "react";

import {
  loadSettings,
  scanAutoForensics,
  scanAutoForensicsLogs,
  scanAutoForensicsRegistry,
  scanAutoForensicsSystemInfo,
  type AutoForensicsEntry,
  type AutoForensicsResult,
  type CaseEvidenceItem,
} from "../services/api";

type LoadingPhase = "idle" | "system-info" | "files" | "registry" | "logs" | "done";

function entryKey(groupName: string, entry: AutoForensicsEntry) {
  return `${groupName}::${entry.name}::${entry.cmd}`;
}

function iconForType(type?: string) {
  switch (type) {
    case "数据库":
    case "database":
      return "🗄️";
    case "图片":
    case "image":
      return "🖼️";
    case "视频":
    case "video":
      return "🎬";
    case "音频":
    case "audio":
      return "🎵";
    case "注册表":
    case "registry":
      return "🧾";
    case "日志":
    case "log":
      return "📜";
    default:
      return "📄";
  }
}

function basename(path: string) {
  const normalized = path.replace(/\\/g, "/").replace(/\/+$/, "");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || path;
}

/** Parse system info result text into rows of [chinese, english, value]. */
function parseSysInfoRows(text: string): Array<[string, string, string]> {
  return text.split("\n").filter(Boolean).map((line) => {
    const parenIdx = line.indexOf("(");
    const closeIdx = line.indexOf("):");
    if (parenIdx > 0 && closeIdx > parenIdx) {
      const chn = line.slice(0, parenIdx).trim();
      const eng = line.slice(parenIdx + 1, closeIdx).trim();
      const val = line.slice(closeIdx + 2).trim();
      return [chn, eng, val];
    }
    const colonIdx = line.indexOf(":");
    if (colonIdx > 0) {
      return [line.slice(0, colonIdx).trim(), "", line.slice(colonIdx + 1).trim()];
    }
    return [line, "", ""];
  });
}

function SysInfoTable({ text }: { text: string }) {
  const rows = useMemo(() => parseSysInfoRows(text), [text]);
  return (
    <div className="table-wrap">
      <table className="sysinfo-table">
        <tbody>
          {rows.map(([chn, eng, val], i) => (
            <tr key={i}>
              <td>{chn}<br /><span style={{ fontSize: "0.78rem", color: "var(--text-faint)" }}>{eng}</span></td>
              <td>{val}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function hasExtractedContent(entry: AutoForensicsEntry): boolean {
  const text = entry.result ?? "";
  if (!text || text.length < 10) return false;
  const failurePrefixes = [
    "目标文件未找到",
    "执行失败",
    "查询失败",
    "扫描失败",
    "未找到匹配",
    "暂不支持",
    "未找到匹配的注册表值",
    "未识别到已安装应用",
    "未命中内置应用模板",
  ];
  return !failurePrefixes.some((prefix) => text.startsWith(prefix));
}

const MODULE_LABELS: Record<string, string> = {
  windows: "Windows",
  linux: "Linux",
  android: "Android",
  ios: "iOS",
};

type Props = {
  module: "windows" | "linux" | "android" | "ios";
};

const PHASE_LABELS: Record<LoadingPhase, string> = {
  idle: "",
  "system-info": "正在提取系统信息...",
  files: "正在提取文件...",
  registry: "正在扫描注册表...",
  logs: "正在分析日志...",
  done: "",
};

export default function AutoForensicsPage({ module }: Props) {
  const [mappingPath, setMappingPath] = useState("");
  const [evidenceOptions, setEvidenceOptions] = useState<CaseEvidenceItem[]>([]);
  const [loadingPhase, setLoadingPhase] = useState<LoadingPhase>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<AutoForensicsResult | null>(null);
  const [totalRaw, setTotalRaw] = useState(0);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedEntryKey, setSelectedEntryKey] = useState("");

  const matchedGroups = useMemo(() => {
    const raw = result?.matched_groups ?? [];
    return raw
      .map((g) => ({
        ...g,
        entries: g.entries.filter(hasExtractedContent),
      }))
      .filter((g) => g.entries.length > 0);
  }, [result]);

  const currentGroup =
    matchedGroups.find((g) => g.group_name === selectedGroup) ?? matchedGroups[0] ?? null;
  const currentEntry =
    currentGroup?.entries.find((e) => entryKey(currentGroup.group_name, e) === selectedEntryKey) ??
    currentGroup?.entries[0] ??
    null;

  const totalEntryCount = useMemo(
    () => matchedGroups.reduce((sum, g) => sum + g.entries.length, 0),
    [matchedGroups]
  );

  const isWindows = module === "windows";

  useEffect(() => {
    loadSettings()
      .then((settings) => {
        const items = (settings.current_case?.evidence_items ?? []).filter((item) => item.type === module);
        setEvidenceOptions(items);
        const casePath = items[0]?.path || settings.current_case?.evidence_paths?.[module];
        if (casePath || settings.mapping_path) {
          setMappingPath(casePath || settings.mapping_path || "");
        }
      })
      .catch(() => undefined);
  }, [module]);

  useEffect(() => {
    if (!currentGroup) return;
    if (!selectedGroup || !matchedGroups.some((g) => g.group_name === selectedGroup)) {
      setSelectedGroup(currentGroup.group_name);
    }
  }, [currentGroup, matchedGroups, selectedGroup]);

  useEffect(() => {
    if (!currentGroup || !currentEntry) return;
    const key = entryKey(currentGroup.group_name, currentEntry);
    if (
      !selectedEntryKey ||
      !currentGroup.entries.some((e) => entryKey(currentGroup.group_name, e) === selectedEntryKey)
    ) {
      setSelectedEntryKey(key);
    }
  }, [currentEntry, currentGroup, selectedEntryKey]);

  /** Merge a phase response into the accumulated result. */
  function mergePhaseResult(phaseResult: AutoForensicsResult) {
    setResult((prev) => {
      if (!prev) return phaseResult;
      return {
        ...prev,
        matched_groups: [...prev.matched_groups, ...phaseResult.matched_groups],
        total_entries: prev.total_entries + phaseResult.total_entries,
        has_registry: prev.has_registry || phaseResult.has_registry || phaseResult.phase === "registry",
        has_logs: prev.has_logs || phaseResult.has_logs || phaseResult.phase === "logs",
      };
    });
    setTotalRaw((prev) => prev + phaseResult.total_entries);
  }

  /** Schedule auto-select after state settles. */
  function autoSelectAfterPhase() {
    // Use setTimeout to let state settle before computing filtered groups
    setTimeout(() => {
      setResult((current) => {
        const groups = (current?.matched_groups ?? [])
          .map((g) => ({ ...g, entries: g.entries.filter(hasExtractedContent) }))
          .filter((g) => g.entries.length > 0);
        if (groups.length > 0) {
          const g = groups[0];
          setSelectedGroup(g.group_name);
          if (g.entries[0]) {
            setSelectedEntryKey(entryKey(g.group_name, g.entries[0]));
          }
        }
        return current; // no change
      });
    }, 0);
  }

  async function handleScan() {
    setError("");
    setResult(null);
    setTotalRaw(0);
    setSelectedGroup("");
    setSelectedEntryKey("");

    try {
      // Phase 0: system info (Windows only)
      if (isWindows) {
        setLoadingPhase("system-info");
        const sysResult = await scanAutoForensicsSystemInfo(mappingPath);
        mergePhaseResult(sysResult);
        autoSelectAfterPhase();
      }

      // Phase 1: file extraction
      setLoadingPhase("files");
      const fileResult = await scanAutoForensics(mappingPath, module);
      mergePhaseResult(fileResult);
      autoSelectAfterPhase();

      // Phase 2 & 3: registry + logs (Windows only, fire in parallel)
      if (isWindows) {
        setLoadingPhase("registry");
        const registryPromise = scanAutoForensicsRegistry(mappingPath).then((regResult) => {
          mergePhaseResult(regResult);
          autoSelectAfterPhase();
        });

        setLoadingPhase("logs");
        const logsPromise = scanAutoForensicsLogs(mappingPath).then((logResult) => {
          mergePhaseResult(logResult);
          autoSelectAfterPhase();
        });

        await Promise.all([registryPromise, logsPromise]);
      }
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "自动取证扫描失败");
    } finally {
      setLoadingPhase("done");
    }
  }

  const moduleLabel = MODULE_LABELS[module] ?? module.toUpperCase();

  return (
    <div className="page-stack">
      <section className="panel android-auto-toolbar">
        <label className="field-label android-auto-path-field">
          映射路径
          <input
            value={mappingPath}
            onChange={(e) => setMappingPath(e.target.value)}
            placeholder={`例如 C:/evidence/${module}`}
          />
        </label>
        {evidenceOptions.length ? (
          <label className="field-label">
            选择检材
            <select value={mappingPath} onChange={(e) => setMappingPath(e.target.value)}>
              {evidenceOptions.map((item) => (
                <option key={item.id} value={item.path}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="android-auto-toolbar-actions">
          <button
            className="primary-button"
            onClick={handleScan}
            disabled={loadingPhase !== "idle" && loadingPhase !== "done" || !mappingPath.trim()}
          >
            {loadingPhase === "idle" || loadingPhase === "done" ? "扫描并自动分析" : "扫描中..."}
          </button>
        </div>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

      {loadingPhase !== "idle" && loadingPhase !== "done" ? (
        <p className="muted-text" style={{ padding: "0 4px" }}>{PHASE_LABELS[loadingPhase]}</p>
      ) : null}

      <section className="android-auto-workbench">
        <aside className="panel android-auto-sidebar">
          <div className="android-auto-tree">
              {matchedGroups.length ? (
                matchedGroups.map((group) => (
                  <div key={group.group_name} className="android-auto-tree-group">
                    <button
                      className={
                        selectedGroup === group.group_name
                          ? "android-auto-tree-node active"
                          : "android-auto-tree-node"
                      }
                      onClick={() => {
                        setSelectedGroup(group.group_name);
                        if (group.entries[0]) {
                          setSelectedEntryKey(entryKey(group.group_name, group.entries[0]));
                        }
                      }}
                    >
                      <span className="android-auto-tree-icon">📦</span>
                      <span className="android-auto-tree-copy">
                        <strong>{group.group_name}</strong>
                        <span>{group.entries.length} 项</span>
                      </span>
                    </button>
                    {selectedGroup === group.group_name ? (
                      <div className="android-auto-tree-children">
                        {group.entries.map((entry) => {
                          const key = entryKey(group.group_name, entry);
                          return (
                            <button
                              key={key}
                              className={
                                selectedEntryKey === key
                                  ? "android-auto-tree-leaf active"
                                  : "android-auto-tree-leaf"
                              }
                              onClick={() => setSelectedEntryKey(key)}
                            >
                              <span className="android-auto-tree-icon">{iconForType(entry.type)}</span>
                              <span className="android-auto-tree-copy">
                                <strong>{entry.name}</strong>
                                <span>{entry.group}</span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="muted-text">
                  {result || loadingPhase !== "idle"
                    ? "所有扫描项均未提取到有效内容。"
                    : "扫描完成后，这里会按命中的插件组分开展开。"}
                </p>
              )}
          </div>
        </aside>

        <section className="android-auto-main">
          <div className="panel android-auto-headerbar">
            <div className="android-auto-breadcrumb">
              <span>📁 {mappingPath ? basename(mappingPath) : "未选择检材"}</span>
              {currentGroup ? <span>› {currentGroup.group_name}</span> : null}
              {currentEntry ? <span>› {currentEntry.name}</span> : null}
            </div>
            <div className="android-auto-toolbar-actions" style={{ gap: 6 }}>
              {result?.has_registry ? <span className="status-pill ready">🧾 注册表</span> : null}
              {result?.has_logs ? <span className="status-pill ready">📜 日志</span> : null}
              {totalRaw > 0 ? (
                <span className="status-pill">
                  {totalEntryCount}/{totalRaw} 项有结果
                </span>
              ) : null}
            </div>
          </div>

          {currentEntry ? (
            <div className="panel android-auto-detail-panel" style={{ display: "grid", gap: 14 }}>
              <div className="android-auto-detail-header">
                <h2>{currentEntry.name}</h2>
              </div>

              <div className="android-auto-detail-grid">
                <div>
                  <strong>来源：</strong>
                  {currentEntry.group}
                </div>
                <div>
                  <strong>类型：</strong>
                  <span className="tag-chip">{currentEntry.type}</span>
                </div>
                <div className="full-span">
                  <strong>路径：</strong>
                  {currentEntry.cmd}
                </div>
                {(
                  currentEntry as AutoForensicsEntry & {
                    log_meta?: { category?: string; size?: number; event_count?: number };
                  }
                ).log_meta ? (
                  <div className="full-span">
                    <strong>日志元信息：</strong>
                    <div className="status-grid" style={{ marginTop: 6 }}>
                      <span className="status-pill">
                        分类: {(currentEntry as any).log_meta?.category ?? "-"}
                      </span>
                      <span className="status-pill">
                        大小: {(currentEntry as any).log_meta?.size ?? 0} bytes
                      </span>
                      <span className="status-pill">
                        事件数: {(currentEntry as any).log_meta?.event_count ?? 0}
                      </span>
                    </div>
                  </div>
                ) : null}
              </div>

              {currentEntry.result ? (
                <div>
                  <strong>提取结果：</strong>
                  {currentEntry.type === "系统信息" ? (
                    <div style={{ marginTop: 8 }}>
                      <SysInfoTable text={currentEntry.result} />
                    </div>
                  ) : (
                    <pre style={{ marginTop: 8 }}>{currentEntry.result}</pre>
                  )}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="panel android-auto-detail-panel">
              <p className="muted-text">
                {matchedGroups.length
                  ? "选择一个左侧的提取项查看结果。"
                  : "扫描完成后，选择左侧提取项查看详细结果。"}
              </p>
            </div>
          )}
        </section>
      </section>
    </div>
  );
}
