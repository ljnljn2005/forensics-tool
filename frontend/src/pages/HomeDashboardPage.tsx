import { useEffect, useState } from "react";

import { deleteCase, loadCases, saveCase, selectCase, type CaseEvidenceItem, type CaseRecord } from "../services/api";

const evidenceTypeOptions: Array<{ value: CaseEvidenceItem["type"]; label: string }> = [
  { value: "windows", label: "Windows 本地检材" },
  { value: "linux", label: "Linux 本地检材" },
  { value: "android", label: "Android 检材" },
  { value: "ios", label: "iOS 检材" },
  { value: "windows_memory", label: "Windows 内存镜像" },
  { value: "linux_memory", label: "Linux 内存镜像" }
];

const emptyCase: CaseRecord = {
  id: "",
  name: "",
  description: "",
  evidence_items: [],
  evidence_paths: {
    windows: "",
    linux: "",
    android: "",
    ios: "",
    windows_memory: "",
    linux_memory: ""
  },
  ssh: {
    host: "",
    port: 22,
    user: "",
    password: ""
  }
};

function makeEvidenceItem(type: CaseEvidenceItem["type"] = "windows"): CaseEvidenceItem {
  const label = evidenceTypeOptions.find((item) => item.value === type)?.label ?? "检材";
  return {
    id: `ev-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    type,
    label,
    path: ""
  };
}

export default function HomeDashboardPage() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [currentCaseId, setCurrentCaseId] = useState("");
  const [editingCase, setEditingCase] = useState<CaseRecord>(emptyCase);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    loadCases()
      .then((payload) => {
        setCases(payload.cases);
        setCurrentCaseId(payload.current_case_id);
        if (payload.current_case) {
          setEditingCase(payload.current_case);
        }
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "案件加载失败"));
  }, []);

  function startNewCase() {
    setEditingCase({ ...emptyCase, id: "", evidence_items: [makeEvidenceItem("windows")] });
    setMessage("");
    setError("");
  }

  function startEditCase(record: CaseRecord) {
    setEditingCase({
      ...record,
      evidence_items: [...(record.evidence_items ?? [])],
      ssh: { ...emptyCase.ssh, ...record.ssh }
    });
    setMessage("");
    setError("");
  }

  function updateEvidenceItem(itemId: string, patch: Partial<CaseEvidenceItem>) {
    setEditingCase((current) => ({
      ...current,
      evidence_items: current.evidence_items.map((item) => (item.id === itemId ? { ...item, ...patch } : item))
    }));
  }

  function addEvidenceItem(type: CaseEvidenceItem["type"] = "windows") {
    setEditingCase((current) => ({
      ...current,
      evidence_items: [...current.evidence_items, makeEvidenceItem(type)]
    }));
  }

  function removeEvidenceItem(itemId: string) {
    setEditingCase((current) => ({
      ...current,
      evidence_items: current.evidence_items.filter((item) => item.id !== itemId)
    }));
  }

  function updateSsh(key: keyof CaseRecord["ssh"], value: string | number) {
    setEditingCase((current) => ({
      ...current,
      ssh: {
        ...current.ssh,
        [key]: value
      }
    }));
  }

  async function handleSave() {
    setError("");
    setMessage("");
    try {
      const payload = await saveCase(editingCase);
      setCases(payload.cases);
      setCurrentCaseId(payload.current_case_id);
      if (payload.current_case) {
        startEditCase(payload.current_case);
      }
      setMessage("案件已保存。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "案件保存失败");
    }
  }

  async function handleSelect(caseId: string) {
    setError("");
    setMessage("");
    try {
      const payload = await selectCase(caseId);
      setCases(payload.cases);
      setCurrentCaseId(payload.current_case_id);
      if (payload.current_case) {
        startEditCase(payload.current_case);
      }
      setMessage("当前案件已切换。");
    } catch (selectError) {
      setError(selectError instanceof Error ? selectError.message : "案件切换失败");
    }
  }

  async function handleDelete(caseId: string) {
    setError("");
    setMessage("");
    try {
      const payload = await deleteCase(caseId);
      setCases(payload.cases);
      setCurrentCaseId(payload.current_case_id);
      if (payload.current_case) {
        startEditCase(payload.current_case);
      } else {
        startNewCase();
      }
      setMessage("案件已删除。");
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "案件删除失败");
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-card">
        <div>
          <div className="eyebrow">Case Workspace</div>
          <h2>案件驱动的取证工作台</h2>
          <p>案件里按需添加检材项。后面每个分析页会按类型读取当前案件里的多个检材，并让你下拉选择。</p>
        </div>
      </section>

      <div className="three-column-layout">
        <section className="panel">
          <div className="button-row">
            <h2>案件列表</h2>
            <button className="secondary-button compact-button" onClick={startNewCase}>
              新建案件
            </button>
          </div>
          <div className="list-stack">
            {cases.length ? (
              cases.map((record) => (
                <div key={record.id} className="result-card">
                  <div className="result-entry-title">{record.name}</div>
                  {record.description ? <div className="muted-text">{record.description}</div> : null}
                  <div className="muted-text top-space">{record.evidence_items?.length ?? 0} 个检材项</div>
                  <div className="button-row top-space">
                    <button className="secondary-button compact-button" onClick={() => startEditCase(record)}>
                      编辑
                    </button>
                    <button className="secondary-button compact-button" onClick={() => handleSelect(record.id)}>
                      {currentCaseId === record.id ? "当前案件" : "设为当前"}
                    </button>
                    <button className="secondary-button compact-button" onClick={() => handleDelete(record.id)}>
                      删除
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted-text">还没有保存的案件。你可以先建案件，再按需逐条添加 Windows、Linux、Android、iOS、内存镜像等检材。</p>
            )}
          </div>
        </section>

        <section className="panel panel-span-2">
          <h2>{editingCase.id ? "编辑案件" : "新建案件"}</h2>
          <div className="form-grid">
            <label className="field-label">
              案件名称
              <input value={editingCase.name} onChange={(event) => setEditingCase({ ...editingCase, name: event.target.value })} placeholder="例如 2026-05-手机与主机联合取证" />
            </label>
            <label className="field-label">
              案件说明
              <input value={editingCase.description ?? ""} onChange={(event) => setEditingCase({ ...editingCase, description: event.target.value })} placeholder="可写备注、来源、目标等" />
            </label>
          </div>

          <div className="button-row top-space">
            <h2>检材项</h2>
            <button className="secondary-button compact-button" onClick={() => addEvidenceItem("windows")}>
              添加检材
            </button>
          </div>
          <div className="list-stack">
            {editingCase.evidence_items.length ? (
              editingCase.evidence_items.map((item) => (
                <div key={item.id} className="result-card">
                  <div className="form-grid">
                    <label className="field-label">
                      检材类型
                      <select value={item.type} onChange={(event) => updateEvidenceItem(item.id, { type: event.target.value as CaseEvidenceItem["type"] })}>
                        {evidenceTypeOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field-label">
                      检材名称
                      <input value={item.label} onChange={(event) => updateEvidenceItem(item.id, { label: event.target.value })} placeholder="例如 分区3 / 手机整包 / memdump-01" />
                    </label>
                  </div>
                  <label className="field-label top-space">
                    检材路径
                    <input value={item.path} onChange={(event) => updateEvidenceItem(item.id, { path: event.target.value })} placeholder="填写这个检材对应的路径" />
                  </label>
                  <div className="button-row top-space">
                    <button className="secondary-button compact-button" onClick={() => removeEvidenceItem(item.id)}>
                      删除该检材
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted-text">当前案件还没有检材项。你可以按需添加多个 Windows、Android、内存镜像等检材。</p>
            )}
          </div>

          <h2 className="top-space">SSH 信息</h2>
          <div className="form-grid">
            <label className="field-label">
              主机
              <input value={editingCase.ssh.host ?? ""} onChange={(event) => updateSsh("host", event.target.value)} />
            </label>
            <label className="field-label">
              端口
              <input value={String(editingCase.ssh.port ?? 22)} onChange={(event) => updateSsh("port", Number(event.target.value || "22"))} />
            </label>
            <label className="field-label">
              用户
              <input value={editingCase.ssh.user ?? ""} onChange={(event) => updateSsh("user", event.target.value)} />
            </label>
            <label className="field-label">
              密码
              <input type="password" value={editingCase.ssh.password ?? ""} onChange={(event) => updateSsh("password", event.target.value)} />
            </label>
          </div>

          <div className="button-row top-space">
            <button className="primary-button" onClick={handleSave}>
              保存案件
            </button>
            {editingCase.id ? (
              <button className="secondary-button" onClick={() => handleSelect(editingCase.id)}>
                设为当前案件
              </button>
            ) : null}
            {message ? <span className="success-text">{message}</span> : null}
          </div>
          {error ? <p className="error-text">{error}</p> : null}
        </section>
      </div>
    </div>
  );
}
