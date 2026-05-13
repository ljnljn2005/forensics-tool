import { useEffect, useState } from "react";

import {
  type CaseEvidenceItem,
  loadMemoryTasks,
  loadSettings,
  previewMemoryTask,
  runMemoryTask,
  stopMemoryMount,
  type MemoryTask
} from "../services/api";

type MemoryForensicsPageProps = {
  module: "windows" | "linux";
};

export default function MemoryForensicsPage({ module }: MemoryForensicsPageProps) {
  const [toolRoot, setToolRoot] = useState("");
  const [memoryImage, setMemoryImage] = useState("");
  const [evidenceOptions, setEvidenceOptions] = useState<CaseEvidenceItem[]>([]);
  const [offline, setOffline] = useState(false);
  const [tasks, setTasks] = useState<MemoryTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<MemoryTask | null>(null);
  const [previewText, setPreviewText] = useState("");
  const [resultText, setResultText] = useState("");
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadSettings()
      .then((settings) => {
        if (cancelled) {
          return;
        }
        const evidenceType = module === "windows" ? "windows_memory" : "linux_memory";
        const items = (settings.current_case?.evidence_items ?? []).filter((item) => item.type === evidenceType);
        setEvidenceOptions(items);
        const casePath = items[0]?.path || (module === "windows" ? settings.current_case?.evidence_paths?.windows_memory : settings.current_case?.evidence_paths?.linux_memory);
        if (casePath) {
          setMemoryImage(casePath);
        }
      })
      .catch(() => undefined);
    loadMemoryTasks(module)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setToolRoot(payload.default_tool_root);
        setTasks(payload.tasks);
      })
      .catch((loadError) => {
        if (cancelled) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "任务加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [module]);

  async function handleSelect(task: MemoryTask) {
    setSelectedTask(task);
    setError("");
    try {
      const payload = await previewMemoryTask(module, task, toolRoot, memoryImage, offline);
      setPreviewText(payload.preview_text);
    } catch (previewError) {
      setPreviewText("");
      setError(previewError instanceof Error ? previewError.message : "预览失败");
    }
  }

  async function handleRun() {
    if (!selectedTask) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = await runMemoryTask(module, selectedTask, toolRoot, memoryImage, offline);
      setResultText(payload.text);
      setRows(payload.rows);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "执行失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleStopMount() {
    setLoading(true);
    try {
      const payload = await stopMemoryMount();
      setResultText(payload.text);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "停止失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel toolbar-panel two-row">
        <label className="field-label grow">
          工具目录
          <input value={toolRoot} onChange={(event) => setToolRoot(event.target.value)} placeholder="内存取证工具目录" />
        </label>
        <label className="field-label grow">
          内存镜像路径
          <input value={memoryImage} onChange={(event) => setMemoryImage(event.target.value)} placeholder="例如 D:/evidence/memory.raw" />
        </label>
        {evidenceOptions.length ? (
          <label className="field-label grow">
            选择检材
            <select value={memoryImage} onChange={(event) => setMemoryImage(event.target.value)}>
              {evidenceOptions.map((item) => (
                <option key={item.id} value={item.path}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label className="checkbox-line">
          <input type="checkbox" checked={offline} onChange={(event) => setOffline(event.target.checked)} />
          高级引擎离线模式
        </label>
        <div className="button-row">
          <button className="primary-button" onClick={handleRun} disabled={loading || !selectedTask}>
            {loading ? "执行中..." : "运行选中任务"}
          </button>
          <button className="secondary-button" onClick={handleStopMount} disabled={loading}>
            停止内存文件系统
          </button>
        </div>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

      <div className="three-column-layout">
        <section className="panel">
          <h2>任务列表</h2>
          <div className="list-stack">
            {tasks.map((task) => (
              <button
                key={`${task.name}-${task.engine}`}
                className={selectedTask?.name === task.name ? "list-button active" : "list-button"}
                onClick={() => handleSelect(task)}
              >
                <strong>{task.name}</strong>
                <span>{task.engine}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>命令预览</h2>
          {previewText ? <pre>{previewText}</pre> : <p className="muted-text">选择任务后，这里会显示命令预览或结果路径。</p>}
        </section>

        <section className="panel">
          <h2>运行输出</h2>
          {resultText ? <pre>{resultText}</pre> : <p className="muted-text">执行任务后，这里会显示输出结果。</p>}
        </section>
      </div>

      <section className="panel">
        <h2>结构化结果</h2>
        {rows.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {Object.keys(rows[0]).map((header) => (
                    <th key={header}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 120).map((row, index) => (
                  <tr key={index}>
                    {Object.keys(rows[0]).map((header) => (
                      <td key={`${index}-${header}`}>{row[header]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted-text">CSV 结果会在这里表格化展示。</p>
        )}
      </section>
    </div>
  );
}
