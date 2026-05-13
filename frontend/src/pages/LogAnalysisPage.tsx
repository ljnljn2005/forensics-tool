import { useEffect, useState } from "react";

import { loadLogDetail, loadSettings, scanLogs, type CaseEvidenceItem, type LogDetailResult, type LogEntry } from "../services/api";

type LogAnalysisPageProps = {
  module: "windows" | "linux";
};

function formatTimestamp(timestamp: number) {
  if (!timestamp) {
    return "-";
  }
  return new Date(timestamp * 1000).toLocaleString();
}

export default function LogAnalysisPage({ module }: LogAnalysisPageProps) {
  const [mappingPath, setMappingPath] = useState("");
  const [evidenceOptions, setEvidenceOptions] = useState<CaseEvidenceItem[]>([]);
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<LogEntry | null>(null);
  const [detail, setDetail] = useState<LogDetailResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

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
  }, []);

  async function handleScan() {
    setLoading(true);
    setError("");
    setDetail(null);
    setSelectedEntry(null);
    try {
      const payload = await scanLogs(mappingPath, module);
      setEntries(payload.entries);
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "扫描失败");
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSelect(entry: LogEntry) {
    setSelectedEntry(entry);
    setDetailLoading(true);
    try {
      const payload = await loadLogDetail(entry);
      setDetail(payload);
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "详情加载失败");
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel toolbar-panel">
        <label className="field-label grow">
          映射路径
          <input value={mappingPath} onChange={(event) => setMappingPath(event.target.value)} placeholder={`例如 C:/evidence/${module}`} />
        </label>
        {evidenceOptions.length ? (
          <label className="field-label grow">
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
        <button className="primary-button" onClick={handleScan} disabled={loading || !mappingPath.trim()}>
          {loading ? "扫描中..." : `扫描 ${module === "windows" ? "Windows" : "Linux"} 日志`}
        </button>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

      <div className="three-column-layout">
        <section className="panel">
          <h2>日志来源</h2>
          <div className="list-stack">
            {entries.length ? (
              entries.map((entry) => (
                <button
                  key={`${entry.path}-${entry.modified}`}
                  className={selectedEntry?.path === entry.path ? "list-button active" : "list-button"}
                  onClick={() => handleSelect(entry)}
                >
                  <strong>{entry.name}</strong>
                  <span>{entry.category}</span>
                </button>
              ))
            ) : (
              <p className="muted-text">扫描完成后，这里会显示日志文件列表。</p>
            )}
          </div>
        </section>

        <section className="panel panel-span-2">
          <h2>日志结果</h2>
          {entries.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>分类</th>
                    <th>路径</th>
                    <th>大小</th>
                    <th>修改时间</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={`${entry.path}-${entry.modified}`} onClick={() => handleSelect(entry)}>
                      <td>{entry.name}</td>
                      <td>{entry.category}</td>
                      <td>{entry.display_path}</td>
                      <td>{entry.size}</td>
                      <td>{formatTimestamp(entry.modified)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted-text">暂无结果。</p>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>详情预览</h2>
        {detailLoading ? <p className="muted-text">正在加载详情...</p> : null}
        {detail ? (
          <div className="page-stack">
            {detail.events.length ? (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Event ID</th>
                      <th>Provider</th>
                      <th>TimeCreated</th>
                      <th>Level</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.events.map((event, index) => (
                      <tr key={`${event.event_id}-${event.time_created}-${index}`}>
                        <td>{event.event_id}</td>
                        <td>{event.provider}</td>
                        <td>{event.time_created}</td>
                        <td>{event.level}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <pre>{detail.text}</pre>
          </div>
        ) : (
          <p className="muted-text">选择日志后，这里会显示结构化事件和原始详情。</p>
        )}
      </section>
    </div>
  );
}
