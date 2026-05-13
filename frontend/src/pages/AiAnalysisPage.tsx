import { useState } from "react";

import { runAiAnalysis } from "../services/api";

export default function AiAnalysisPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAnalyze() {
    setLoading(true);
    setError("");
    try {
      const payload = await runAiAnalysis(text);
      setResult(payload.result);
    } catch (analysisError) {
      setResult("");
      setError(analysisError instanceof Error ? analysisError.message : "分析失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel">
        <h2>AI 分析</h2>
        <label className="field-label">
          输入待分析内容
          <input value={text} onChange={(event) => setText(event.target.value)} placeholder="输入题目描述、取证现象或日志摘要" />
        </label>
        <div className="button-row top-space">
          <button className="primary-button" onClick={handleAnalyze} disabled={loading || !text.trim()}>
            {loading ? "分析中..." : "开始分析"}
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      <section className="panel">
        <h2>分析结果</h2>
        {result ? <pre>{result}</pre> : <p className="muted-text">提交分析文本后，这里会展示启发式或远程模型分析结果。</p>}
      </section>
    </div>
  );
}
