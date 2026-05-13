import { useEffect, useState } from "react";

import { loadSettings, scanRegistry, type CaseEvidenceItem, type RegistryScanResult } from "../services/api";

const scanOptions = [
  { value: "default_apps", label: "默认应用" },
  { value: "custom_path", label: "自定义注册表路径" }
];

export default function RegistryScanPage() {
  const [mappingPath, setMappingPath] = useState("");
  const [evidenceOptions, setEvidenceOptions] = useState<CaseEvidenceItem[]>([]);
  const [scanItem, setScanItem] = useState("default_apps");
  const [registryPath, setRegistryPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RegistryScanResult | null>(null);

  useEffect(() => {
    loadSettings()
      .then((settings) => {
        const items = (settings.current_case?.evidence_items ?? []).filter((item) => item.type === "windows");
        setEvidenceOptions(items);
        const casePath = items[0]?.path || settings.current_case?.evidence_paths?.windows;
        if (casePath || settings.mapping_path) {
          setMappingPath(casePath || settings.mapping_path || "");
        }
      })
      .catch(() => undefined);
  }, []);

  async function handleScan() {
    setLoading(true);
    setError("");
    try {
      const payload = await scanRegistry(mappingPath, scanItem, registryPath);
      setResult(payload);
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "扫描失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="workbench-grid">
      <section className="panel">
        <h2>扫描设置</h2>
        <label className="field-label">
          映射路径
          <input value={mappingPath} onChange={(event) => setMappingPath(event.target.value)} placeholder="例如 C:/evidence/windows" />
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
        <label className="field-label">
          扫描项
          <select value={scanItem} onChange={(event) => setScanItem(event.target.value)}>
            {scanOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          注册表路径
          <input
            value={registryPath}
            onChange={(event) => setRegistryPath(event.target.value)}
            placeholder="例如 HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"
            disabled={scanItem !== "custom_path"}
          />
        </label>
        <button className="primary-button" onClick={handleScan} disabled={loading || !mappingPath.trim()}>
          {loading ? "扫描中..." : "运行注册表扫描"}
        </button>
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      <section className="panel panel-span-2">
        <h2>扫描结果</h2>
        {result ? <pre>{result.text}</pre> : <p className="muted-text">扫描完成后，这里会展示注册表分析结果。</p>}
      </section>
    </div>
  );
}
