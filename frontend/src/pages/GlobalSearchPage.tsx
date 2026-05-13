import { useState } from "react";

import { globalSearch, type SearchResultItem } from "../services/api";

export default function GlobalSearchPage() {
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSearch() {
    setLoading(true);
    setError("");
    try {
      const payload = await globalSearch(keyword);
      setResults(payload.results);
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "搜索失败");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel toolbar-panel">
        <label className="field-label grow">
          关键字
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索插件名称、积木名称、命令或模块" />
        </label>
        <button className="primary-button" onClick={handleSearch} disabled={loading || !keyword.trim()}>
          {loading ? "搜索中..." : "执行搜索"}
        </button>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

      <section className="panel">
        <h2>搜索结果</h2>
        {results.length ? (
          <div className="result-stack">
            {results.map((item, index) => (
              <article key={`${item.plugin}-${item.block_name}-${index}`} className="result-card">
                <h3>
                  {item.plugin} / {item.block_name}
                </h3>
                <div className="tag-list">
                  <span className="tag-chip">{item.module || "unknown"}</span>
                  <span className="tag-chip">{item.type || "未分类"}</span>
                  {item.author ? <span className="tag-chip">{item.author}</span> : null}
                </div>
                {item.description ? <p className="muted-text">{item.description}</p> : null}
                <pre>{item.cmd}</pre>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted-text">输入关键字后，可以在这里查看插件与取证积木的命中结果。</p>
        )}
      </section>
    </div>
  );
}
