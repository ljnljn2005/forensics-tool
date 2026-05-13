import { useEffect, useMemo, useState } from "react";

import { loadExtractorEntries, loadSettings, runExtractorEntry, type CaseEvidenceItem, type ExtractorEntry } from "../services/api";

type ExtractorWorkbenchPageProps = {
  module: "windows" | "linux" | "android" | "ios";
};

export default function ExtractorWorkbenchPage({ module }: ExtractorWorkbenchPageProps) {
  const [mappingPath, setMappingPath] = useState("");
  const [evidenceOptions, setEvidenceOptions] = useState<CaseEvidenceItem[]>([]);
  const [entries, setEntries] = useState<ExtractorEntry[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<ExtractorEntry | null>(null);
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadSettings()
      .then((settings) => {
        const items = (settings.current_case?.evidence_items ?? []).filter((item) => item.type === module);
        if (!cancelled) {
          setEvidenceOptions(items);
          const casePath = items[0]?.path || settings.current_case?.evidence_paths?.[module];
          if (casePath || settings.mapping_path) {
            setMappingPath(casePath || settings.mapping_path || "");
          }
        }
      })
      .catch(() => undefined);
    loadExtractorEntries(module)
      .then((payload) => {
        if (!cancelled) {
          setEntries(payload.entries);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "加载失败");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [module]);

  const filteredEntries = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) {
      return entries;
    }
    return entries.filter((entry) =>
      [entry.group, entry.name, entry.cmd, entry.type].join(" ").toLowerCase().includes(keyword)
    );
  }, [entries, search]);

  async function handleRun(entry: ExtractorEntry) {
    setSelectedEntry(entry);
    setLoading(true);
    setError("");
    try {
      const payload = await runExtractorEntry(module, mappingPath, entry);
      setOutput(payload.text);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "执行失败");
      setOutput("");
    } finally {
      setLoading(false);
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
        <label className="field-label grow">
          搜索积木
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索名称、路径或插件组" />
        </label>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

      <div className="three-column-layout">
        <section className="panel">
          <h2>插件组</h2>
          <div className="list-stack">
            {Array.from(new Set(filteredEntries.map((entry) => entry.group))).map((group) => (
              <div key={group} className="result-card">
                <strong>{group}</strong>
                <div className="muted-text">{filteredEntries.filter((entry) => entry.group === group).length} 个积木</div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel panel-span-2">
          <h2>提取积木</h2>
          {filteredEntries.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>类型</th>
                    <th>来源插件</th>
                    <th>路径/命令</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEntries.map((entry) => (
                    <tr key={`${entry.group}-${entry.name}-${entry.cmd}`}>
                      <td>{entry.name}</td>
                      <td>{entry.type}</td>
                      <td>{entry.group}</td>
                      <td>{entry.cmd}</td>
                      <td>
                        <button className="primary-button compact-button" onClick={() => handleRun(entry)} disabled={loading}>
                          运行
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted-text">当前模块没有可用的文件提取积木。</p>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>结果预览</h2>
        {selectedEntry ? <div className="stat-line">当前选择: {selectedEntry.group} / {selectedEntry.name}</div> : null}
        {loading ? <p className="muted-text">执行中...</p> : output ? <pre>{output}</pre> : <p className="muted-text">点击“运行”后，这里会显示提取结果。</p>}
      </section>
    </div>
  );
}
