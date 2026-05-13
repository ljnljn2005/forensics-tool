import { useEffect, useMemo, useState } from "react";

import {
  inspectMappedPath,
  loadSettings,
  openMappedPath,
  scanAndroidAutoForensics,
  type AndroidAutoForensicsEntry,
  type AndroidAutoForensicsResult,
  type CaseEvidenceItem,
  type FileBrowserInspectResult
} from "../services/api";

function entryKey(packageName: string, entry: AndroidAutoForensicsEntry) {
  return `${packageName}::${entry.group}::${entry.name}::${entry.cmd}`;
}

function isDatabaseKind(kind?: string) {
  return kind === "database";
}

function iconForKind(kind?: string) {
  switch (kind) {
    case "database":
      return "🗄️";
    case "image":
      return "🖼️";
    case "video":
      return "🎬";
    case "audio":
      return "🎵";
    case "directory":
      return "📁";
    default:
      return "📄";
  }
}

function describeDetectedKind(kind?: string) {
  switch (kind) {
    case "database":
      return "数据库";
    case "image":
      return "图片";
    case "video":
      return "视频";
    case "audio":
      return "音频";
    case "directory":
      return "目录";
    default:
      return "文件";
  }
}

function openDatabaseWindow(mappingPath: string, databasePath: string) {
  const pywebviewApi = (window as unknown as { pywebview?: { api?: { open_popup_window?: (popup: string, mappingPath: string, databasePath: string) => Promise<unknown> } } }).pywebview?.api;
  if (pywebviewApi?.open_popup_window) {
    void pywebviewApi.open_popup_window("db-viewer", mappingPath, databasePath);
    return;
  }
  const url = `/?popup=db-viewer&mappingPath=${encodeURIComponent(mappingPath)}&databasePath=${encodeURIComponent(databasePath)}`;
  window.open(url, "_blank", "width=1280,height=900");
}

function basename(path: string) {
  const normalized = path.replace(/\\/g, "/").replace(/\/+$/, "");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || path;
}

export default function AndroidAutoForensicsPage() {
  const [mappingPath, setMappingPath] = useState("");
  const [evidenceOptions, setEvidenceOptions] = useState<CaseEvidenceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [result, setResult] = useState<AndroidAutoForensicsResult | null>(null);
  const [pathDetails, setPathDetails] = useState<Record<string, FileBrowserInspectResult>>({});
  const [pathLoadingKey, setPathLoadingKey] = useState("");
  const [selectedPackage, setSelectedPackage] = useState("");
  const [selectedEntryKey, setSelectedEntryKey] = useState("");
  const [selectedChildPath, setSelectedChildPath] = useState("");

  const matchedPackages = result?.matched_packages ?? [];
  const currentPackage = matchedPackages.find((item) => item.package_name === selectedPackage) ?? matchedPackages[0] ?? null;
  const currentEntry =
    currentPackage?.entries.find((entry) => entryKey(currentPackage.package_name, entry) === selectedEntryKey) ??
    currentPackage?.entries[0] ??
    null;
  const currentEntryKey = currentPackage && currentEntry ? entryKey(currentPackage.package_name, currentEntry) : "";
  const currentPath = currentEntry?.resolved_path || currentEntry?.cmd || "";
  const currentDetail = currentEntryKey ? pathDetails[currentEntryKey] : undefined;
  const selectedChild = currentDetail?.children.find((child) => child.path === selectedChildPath) ?? null;

  const matchedEntryCount = useMemo(
    () => matchedPackages.reduce((sum, item) => sum + item.entries.length, 0),
    [matchedPackages]
  );

  const filteredTableRows = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (currentDetail?.kind === "directory") {
      const rows = currentDetail.children.map((child) => ({
        kind: "child" as const,
        child,
        searchable: `${child.name} ${child.path} ${child.detected_kind ?? ""}`.toLowerCase()
      }));
      return keyword ? rows.filter((row) => row.searchable.includes(keyword)) : rows;
    }

    const rows =
      currentPackage?.entries.map((entry) => ({
        kind: "entry" as const,
        entry,
        key: entryKey(currentPackage.package_name, entry),
        searchable: `${entry.name} ${entry.group} ${entry.type} ${entry.cmd} ${entry.resolved_path ?? ""}`.toLowerCase()
      })) ?? [];
    return keyword ? rows.filter((row) => row.searchable.includes(keyword)) : rows;
  }, [currentDetail, currentPackage, search]);

  useEffect(() => {
    loadSettings()
      .then((settings) => {
        const items = (settings.current_case?.evidence_items ?? []).filter((item) => item.type === "android");
        setEvidenceOptions(items);
        const casePath = items[0]?.path || settings.current_case?.evidence_paths?.android;
        if (casePath || settings.mapping_path) {
          setMappingPath(casePath || settings.mapping_path || "");
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!currentPackage) {
      return;
    }
    if (!selectedPackage || !matchedPackages.some((item) => item.package_name === selectedPackage)) {
      setSelectedPackage(currentPackage.package_name);
    }
  }, [currentPackage, matchedPackages, selectedPackage]);

  useEffect(() => {
    if (!currentPackage || !currentEntry) {
      return;
    }
    const key = entryKey(currentPackage.package_name, currentEntry);
    if (!selectedEntryKey || !currentPackage.entries.some((entry) => entryKey(currentPackage.package_name, entry) === selectedEntryKey)) {
      setSelectedEntryKey(key);
    }
  }, [currentEntry, currentPackage, selectedEntryKey]);

  useEffect(() => {
    if (!currentEntryKey || !currentPath || pathDetails[currentEntryKey] || pathLoadingKey === currentEntryKey) {
      return;
    }
    setPathLoadingKey(currentEntryKey);
    inspectMappedPath(mappingPath, currentPath)
      .then((payload) => {
        setPathDetails((current) => ({ ...current, [currentEntryKey]: payload }));
      })
      .catch(() => undefined)
      .finally(() => setPathLoadingKey(""));
  }, [currentEntryKey, currentPath, mappingPath, pathDetails, pathLoadingKey]);

  async function handleScan() {
    setLoading(true);
    setError("");
    setPathDetails({});
    setSelectedPackage("");
    setSelectedEntryKey("");
    setSelectedChildPath("");
    try {
      const payload = await scanAndroidAutoForensics(mappingPath, []);
      setResult(payload);
      const firstPackage = payload.matched_packages[0];
      if (firstPackage) {
        setSelectedPackage(firstPackage.package_name);
        if (firstPackage.entries[0]) {
          setSelectedEntryKey(entryKey(firstPackage.package_name, firstPackage.entries[0]));
        }
      }
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "自动取证扫描失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleInspect(packageName: string, entry: AndroidAutoForensicsEntry) {
    const key = entryKey(packageName, entry);
    const targetPath = entry.resolved_path || entry.cmd;
    setSelectedPackage(packageName);
    setSelectedEntryKey(key);
    setSelectedChildPath("");
    if (pathDetails[key]) {
      return;
    }
    setPathLoadingKey(key);
    setError("");
    try {
      const payload = await inspectMappedPath(mappingPath, targetPath);
      setPathDetails((current) => ({ ...current, [key]: payload }));
    } catch (inspectError) {
      setError(inspectError instanceof Error ? inspectError.message : "路径查看失败");
    } finally {
      setPathLoadingKey("");
    }
  }

  async function handleOpen(targetPath: string, action: "default" | "explorer") {
    setError("");
    try {
      await openMappedPath(mappingPath, targetPath, action);
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : "打开路径失败");
    }
  }

  return (
    <div className="page-stack">
      <section className="panel android-auto-toolbar">
        <label className="field-label android-auto-path-field">
          映射路径
          <input value={mappingPath} onChange={(event) => setMappingPath(event.target.value)} placeholder="例如 C:/evidence/android-backup" />
        </label>
        {evidenceOptions.length ? (
          <label className="field-label">
            选择检材
            <select value={mappingPath} onChange={(event) => setMappingPath(event.target.value)}>
              {evidenceOptions.map((item) => (
                <option key={item.id} value={item.path}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="android-auto-toolbar-actions">
          <button className="primary-button" onClick={handleScan} disabled={loading || !mappingPath.trim()}>
            {loading ? "扫描中..." : "扫描应用并自动分析"}
          </button>
        </div>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

      <section className="android-auto-workbench">
        <aside className="panel android-auto-sidebar">
          <div className="android-auto-case-picker">
            <input value={mappingPath} onChange={(event) => setMappingPath(event.target.value)} placeholder="选择或输入 Android 检材路径" />
          </div>
          <div className="android-auto-tree">
            <button className={selectedPackage ? "android-auto-tree-root active" : "android-auto-tree-root"} onClick={() => currentPackage && setSelectedPackage(currentPackage.package_name)}>
              <span className="android-auto-tree-icon">🤖</span>
              <span className="android-auto-tree-copy">
                <strong>{mappingPath ? basename(mappingPath) : "Android 检材"}</strong>
                <span>{matchedEntryCount} 个命中分析项</span>
              </span>
            </button>
            <div className="android-auto-tree-section">
              {matchedPackages.length ? (
                matchedPackages.map((pkg) => (
                  <div key={pkg.package_name} className="android-auto-tree-group">
                    <button
                      className={selectedPackage === pkg.package_name ? "android-auto-tree-node active" : "android-auto-tree-node"}
                      onClick={() => {
                        setSelectedPackage(pkg.package_name);
                        if (pkg.entries[0]) {
                          setSelectedEntryKey(entryKey(pkg.package_name, pkg.entries[0]));
                        }
                      }}
                    >
                      <span className="android-auto-tree-icon">📦</span>
                      <span className="android-auto-tree-copy">
                        <strong>{pkg.package_name}</strong>
                        <span>{pkg.entries.length} 个分析项</span>
                      </span>
                    </button>
                    {selectedPackage === pkg.package_name ? (
                      <div className="android-auto-tree-children">
                        {pkg.entries.map((entry) => {
                          const key = entryKey(pkg.package_name, entry);
                          const detectedKind = selectedEntryKey === key ? currentDetail?.detected_kind : undefined;
                          return (
                            <button
                              key={key}
                              className={selectedEntryKey === key ? "android-auto-tree-leaf active" : "android-auto-tree-leaf"}
                              onClick={() => handleInspect(pkg.package_name, entry)}
                            >
                              <span className="android-auto-tree-icon">{iconForKind(detectedKind)}</span>
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
                <p className="muted-text">扫描完成后，这里会按命中应用和分析项展开。</p>
              )}
            </div>
          </div>
        </aside>

        <section className="android-auto-main">
          <div className="panel android-auto-headerbar">
            <div className="android-auto-breadcrumb">
              <span>📁 {mappingPath ? basename(mappingPath) : "未选择检材"}</span>
              {currentPackage ? <span>› {currentPackage.package_name}</span> : null}
              {currentEntry ? <span>› {currentEntry.name}</span> : null}
            </div>
            <label className="field-label android-auto-search">
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="在当前结果中搜索" />
            </label>
          </div>

          <div className="panel android-auto-grid-panel">
            <div className="android-auto-grid-summary">
              <span>已识别包名 {result?.installed_packages.length ?? 0}</span>
              <span>命中分析项 {matchedEntryCount}</span>
              <span>系统预设路径 {result?.android_system_roots?.length ?? 0}</span>
            </div>

            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    {currentDetail?.kind === "directory" ? (
                      <>
                        <th>名称</th>
                        <th>类型</th>
                        <th>路径</th>
                        <th>操作</th>
                      </>
                    ) : (
                      <>
                        <th>分析项</th>
                        <th>来源插件</th>
                        <th>类型</th>
                        <th>完整路径</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {filteredTableRows.length ? (
                    filteredTableRows.map((row) =>
                      row.kind === "child" ? (
                        <tr key={row.child.path} onClick={() => setSelectedChildPath(row.child.path)}>
                          <td>{row.child.name}</td>
                          <td>{row.child.is_dir ? "目录" : describeDetectedKind(row.child.detected_kind)}</td>
                          <td>{row.child.path}</td>
                          <td>
                            <div className="button-row">
                              {row.child.is_file && isDatabaseKind(row.child.detected_kind) ? (
                                <button className="secondary-button compact-button" onClick={(event) => { event.stopPropagation(); openDatabaseWindow(mappingPath, row.child.path); }}>
                                  数据库窗口
                                </button>
                              ) : null}
                              <button className="secondary-button compact-button" onClick={(event) => { event.stopPropagation(); handleOpen(row.child.path, "default"); }}>
                                默认打开
                              </button>
                              <button className="secondary-button compact-button" onClick={(event) => { event.stopPropagation(); handleOpen(row.child.path, "explorer"); }}>
                                资源管理器
                              </button>
                            </div>
                          </td>
                        </tr>
                      ) : (
                        <tr key={row.key} onClick={() => handleInspect(currentPackage!.package_name, row.entry)}>
                          <td>{row.entry.name}</td>
                          <td>{row.entry.group}</td>
                          <td>{currentDetail && selectedEntryKey === row.key ? describeDetectedKind(currentDetail.detected_kind) : row.entry.type}</td>
                          <td>{row.entry.resolved_path || row.entry.cmd}</td>
                        </tr>
                      )
                    )
                  ) : (
                    <tr>
                      <td colSpan={4} className="android-auto-empty-cell">
                        暂无结果。
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel android-auto-detail-panel">
            <div className="android-auto-detail-header">
              <h2>详细信息</h2>
              {pathLoadingKey === currentEntryKey ? <span className="muted-text">正在读取路径...</span> : null}
            </div>

            {selectedChild ? (
              <div className="android-auto-detail-grid">
                <div><strong>名称：</strong>{selectedChild.name}</div>
                <div><strong>类型：</strong>{selectedChild.is_dir ? "目录" : describeDetectedKind(selectedChild.detected_kind)}</div>
                <div><strong>格式：</strong>{selectedChild.detected_format || "-"}</div>
                <div><strong>MIME：</strong>{selectedChild.detected_mime || "-"}</div>
                <div className="full-span"><strong>路径：</strong>{selectedChild.path}</div>
                <div className="full-span android-auto-detail-actions">
                  {selectedChild.is_file && isDatabaseKind(selectedChild.detected_kind) ? (
                    <button className="secondary-button" onClick={() => openDatabaseWindow(mappingPath, selectedChild.path)}>
                      打开数据库窗口
                    </button>
                  ) : null}
                  <button className="secondary-button" onClick={() => handleOpen(selectedChild.path, "default")}>
                    默认程序打开
                  </button>
                  <button className="secondary-button" onClick={() => handleOpen(selectedChild.path, "explorer")}>
                    资源管理器打开
                  </button>
                </div>
              </div>
            ) : currentEntry ? (
              <div className="android-auto-detail-grid">
                <div><strong>分析项：</strong>{currentEntry.name}</div>
                <div><strong>来源插件：</strong>{currentEntry.group}</div>
                <div><strong>识别类型：</strong>{describeDetectedKind(currentDetail?.detected_kind)}</div>
                <div><strong>包名：</strong>{currentPackage?.package_name}</div>
                <div><strong>格式：</strong>{currentDetail?.detected_format || "-"}</div>
                <div><strong>MIME：</strong>{currentDetail?.detected_mime || "-"}</div>
                <div className="full-span"><strong>插件细分路径：</strong>{currentEntry.cmd}</div>
                <div className="full-span"><strong>完整路径：</strong>{currentPath || "未命中现有预设路径"}</div>
                <div className="full-span"><strong>系统预设路径：</strong>{(result?.android_system_roots ?? []).join("、")}</div>
                {currentDetail?.tried_paths?.length ? (
                  <div className="full-span">
                    <strong>尝试路径：</strong>
                    <pre>{currentDetail.tried_paths.join("\n")}</pre>
                  </div>
                ) : null}
                <div className="full-span android-auto-detail-actions">
                  {isDatabaseKind(currentDetail?.detected_kind) ? (
                    <button className="secondary-button" onClick={() => openDatabaseWindow(mappingPath, currentPath)}>
                      打开数据库窗口
                    </button>
                  ) : null}
                  <button className="secondary-button" onClick={() => handleInspect(currentPackage!.package_name, currentEntry)}>
                    刷新路径内容
                  </button>
                  <button className="secondary-button" onClick={() => handleOpen(currentPath, "default")}>
                    默认程序打开
                  </button>
                  <button className="secondary-button" onClick={() => handleOpen(currentPath, "explorer")}>
                    资源管理器打开
                  </button>
                </div>
                {currentDetail?.kind === "file" && !isDatabaseKind(currentDetail?.detected_kind) ? (
                  <div className="full-span">
                    <strong>内容预览：</strong>
                    <pre>{currentEntry.result ?? "(无结果)"}</pre>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="muted-text">扫描并选择一个命中项后，这里会显示详细信息。</p>
            )}
          </div>
        </section>
      </section>
    </div>
  );
}
