import { useEffect, useState } from "react";

import { inspectDatabase, type DatabaseInspectResult } from "../services/api";

type Props = {
  mappingPath: string;
  databasePath: string;
};

export default function DatabaseViewerPage({ mappingPath, databasePath }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DatabaseInspectResult | null>(null);

  useEffect(() => {
    setLoading(true);
    setError("");
    inspectDatabase(mappingPath, databasePath)
      .then((payload) => setResult(payload))
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "数据库加载失败"))
      .finally(() => setLoading(false));
  }, [databasePath, mappingPath]);

  return (
    <div className="page-stack popup-page">
      <section className="panel">
        <h2>数据库查看器</h2>
        <div className="muted-text">映射路径: {mappingPath}</div>
        <div className="muted-text">数据库路径: {databasePath}</div>
        {loading ? <p className="muted-text">正在解析数据库...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
        {result ? (
          <div className="db-preview-stack top-space">
            <div className="muted-text">数据库来源: {result.source_path}</div>
            {result.message ? <div className="error-text">{result.message}</div> : null}
            {result.tables.map((table) => (
              <details key={table.name} open>
                <summary>
                  {table.name} ({table.row_count} rows)
                </summary>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {table.columns.map((column) => (
                          <th key={column}>{column}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.preview_rows.map((row, rowIndex) => (
                        <tr key={`${table.name}-${rowIndex}`}>
                          {table.columns.map((column) => (
                            <td key={`${table.name}-${rowIndex}-${column}`}>{String(row[column] ?? "")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
