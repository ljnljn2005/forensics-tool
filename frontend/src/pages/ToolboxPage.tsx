import { useEffect, useState } from "react";

import {
  adaptJigsawPuzzle,
  analyzeJigsawMontage,
  createJigsawPuzzle,
  inspectJigsawPuzzle,
  loadJigsawCatalog,
  loadJigsawPuzzleTask,
  previewJigsawSquare,
  runJigsawMontage,
  runJigsawSquare,
  solveJigsawPuzzle,
  type JigsawCatalog,
  type JigsawMontageAnalysis,
  type JigsawPuzzleInspect,
  type JigsawPuzzleTask,
  type JigsawSquarePreview,
} from "../services/api";

type FeatureKey = "montage" | "square" | "puzzle";

const defaultCatalog: JigsawCatalog = {
  key: "jigsaw-puzzle",
  name: "Jigsaw Puzzle",
  description: "集成超级拼接、正方形转换、拼图生成与拼图还原。",
  tool_dir: "",
  features: [
    { key: "montage", name: "超级拼接" },
    { key: "square", name: "正方形转换" },
    { key: "puzzle", name: "拼图生成 / 还原" },
  ],
};

export default function ToolboxPage() {
  const [catalog, setCatalog] = useState<JigsawCatalog>(defaultCatalog);
  const [activeFeature, setActiveFeature] = useState<FeatureKey>("montage");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [solveTask, setSolveTask] = useState<JigsawPuzzleTask | null>(null);

  const [montageFolder, setMontageFolder] = useState("D:/Coding/forensicstool/tools/toolbox/Jigsaw Puzzle/114514");
  const [montageSort, setMontageSort] = useState("name_asc");
  const [montageCols, setMontageCols] = useState(0);
  const [montageCellWidth, setMontageCellWidth] = useState(200);
  const [montageCellHeight, setMontageCellHeight] = useState(200);
  const [montageGap, setMontageGap] = useState(0);
  const [montageBackground, setMontageBackground] = useState("white");
  const [montageOutput, setMontageOutput] = useState("D:/Coding/forensicstool/tools/toolbox/Jigsaw Puzzle/10086/拼接结果.jpg");
  const [montageAnalysis, setMontageAnalysis] = useState<JigsawMontageAnalysis | null>(null);

  const [squareInput, setSquareInput] = useState("");
  const [squareCols, setSquareCols] = useState(4);
  const [squareRows, setSquareRows] = useState(3);
  const [squareMode, setSquareMode] = useState("area");
  const [squareOutput, setSquareOutput] = useState("");
  const [squarePreview, setSquarePreview] = useState<JigsawSquarePreview | null>(null);

  const [puzzleSource, setPuzzleSource] = useState("");
  const [puzzleTarget, setPuzzleTarget] = useState("D:/Coding/forensicstool/tools/toolbox/Jigsaw Puzzle/10086/generated_puzzle.png");
  const [puzzleImage, setPuzzleImage] = useState("");
  const [puzzleOutput, setPuzzleOutput] = useState("D:/Coding/forensicstool/tools/toolbox/Jigsaw Puzzle/10086/solved_result.png");
  const [puzzlePieceSize, setPuzzlePieceSize] = useState<number | "">(64);
  const [puzzleGenerations, setPuzzleGenerations] = useState(20);
  const [puzzlePopulation, setPuzzlePopulation] = useState(200);
  const [puzzleSelection, setPuzzleSelection] = useState("tournament");
  const [puzzleMutation, setPuzzleMutation] = useState(0.02);
  const [puzzleInspect, setPuzzleInspect] = useState<JigsawPuzzleInspect | null>(null);

  useEffect(() => {
    loadJigsawCatalog()
      .then((payload) => setCatalog(payload))
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "工具箱加载失败"));
  }, []);

  useEffect(() => {
    if (!solveTask || solveTask.status !== "running") {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const payload = await loadJigsawPuzzleTask(solveTask.task_id);
        setSolveTask(payload);
        if (payload.status === "completed") {
          setMessage(payload.message);
          window.clearInterval(timer);
        } else if (payload.status === "failed") {
          setError(payload.message);
          window.clearInterval(timer);
        }
      } catch (pollError) {
        setError(pollError instanceof Error ? pollError.message : "任务进度获取失败");
        window.clearInterval(timer);
      }
    }, 800);
    return () => window.clearInterval(timer);
  }, [solveTask]);

  function resetFeedback() {
    setMessage("");
    setError("");
  }

  async function handleMontageAnalyze() {
    setBusy(true);
    resetFeedback();
    try {
      const payload = await analyzeJigsawMontage({
        folder_path: montageFolder,
        sort_mode: montageSort,
        cols: montageCols,
        cell_width: montageCellWidth,
        cell_height: montageCellHeight,
        gap: montageGap,
      });
      setMontageAnalysis(payload);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "超级拼接分析失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleMontageRun() {
    setBusy(true);
    resetFeedback();
    try {
      const payload = await runJigsawMontage({
        folder_path: montageFolder,
        sort_mode: montageSort,
        cols: montageCols,
        cell_width: montageCellWidth,
        cell_height: montageCellHeight,
        gap: montageGap,
        background: montageBackground,
        output_path: montageOutput,
      });
      setMessage(payload.message);
      const analysis = await analyzeJigsawMontage({
        folder_path: montageFolder,
        sort_mode: montageSort,
        cols: montageCols,
        cell_width: montageCellWidth,
        cell_height: montageCellHeight,
        gap: montageGap,
      });
      setMontageAnalysis(analysis);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "超级拼接执行失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleSquarePreview() {
    setBusy(true);
    resetFeedback();
    try {
      const payload = await previewJigsawSquare({
        image_path: squareInput,
        cols: squareCols,
        rows: squareRows,
        mode: squareMode,
      });
      setSquarePreview(payload);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "正方形转换预览失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleSquareRun() {
    setBusy(true);
    resetFeedback();
    try {
      const payload = await runJigsawSquare({
        image_path: squareInput,
        cols: squareCols,
        rows: squareRows,
        mode: squareMode,
        output_path: squareOutput,
      });
      setSquarePreview(payload.preview);
      setMessage(payload.message);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "正方形转换失败");
    } finally {
      setBusy(false);
    }
  }

  async function handlePuzzleInspect() {
    setBusy(true);
    resetFeedback();
    try {
      const payload = await inspectJigsawPuzzle({ image_path: puzzleSource || puzzleImage });
      setPuzzleInspect(payload);
      if (payload.suggested) {
        setPuzzlePieceSize(payload.suggested.piece_size);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "原图分析失败");
    } finally {
      setBusy(false);
    }
  }

  async function handlePuzzleAdapt() {
    if (puzzlePieceSize === "") {
      return;
    }
    setBusy(true);
    resetFeedback();
    try {
      const payload = await adaptJigsawPuzzle({
        image_path: puzzleSource,
        piece_size: Number(puzzlePieceSize),
      });
      setPuzzleSource(payload.output_path);
      setMessage(
        payload.adapted
          ? `已按中心裁切适配到 ${payload.crop.adapted_width} × ${payload.crop.adapted_height}。`
          : "当前原图已经符合碎片尺寸，无需适配。"
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "智能适配失败");
    } finally {
      setBusy(false);
    }
  }

  async function handlePuzzleCreate() {
    if (puzzlePieceSize === "") {
      return;
    }
    setBusy(true);
    resetFeedback();
    try {
      const payload = await createJigsawPuzzle({
        image_path: puzzleSource,
        output_path: puzzleTarget,
        piece_size: Number(puzzlePieceSize),
      });
      setPuzzleImage(payload.output_path);
      setMessage(payload.message);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "拼图生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function handlePuzzleSolve() {
    setBusy(true);
    resetFeedback();
    try {
      const payload = await solveJigsawPuzzle({
        puzzle_path: puzzleImage,
        output_path: puzzleOutput,
        piece_size: puzzlePieceSize,
        generations: puzzleGenerations,
        population: puzzlePopulation,
        selection: puzzleSelection,
        mutation: puzzleMutation,
      });
      setSolveTask(payload);
      setMessage("拼图还原任务已启动。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "拼图还原失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel">
        <h2>{catalog.name}</h2>
        <p className="muted-text">{catalog.description}</p>
        <div className="status-grid top-space">
          <span className="status-pill ready">代码已原生集成</span>
          <span className="status-pill">{catalog.tool_dir || "工具目录加载中..."}</span>
        </div>
      </section>

      {solveTask ? (
        <section className="panel">
          <h2>拼图还原进度</h2>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${solveTask.progress}%` }} />
          </div>
          <div className="stat-line">{solveTask.progress.toFixed(1)}% · {solveTask.message}</div>
          {solveTask.output_path ? <div className="muted-text">输出: {solveTask.output_path}</div> : null}
        </section>
      ) : null}

      {message ? <p className="success-text">{message}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <section className="panel">
        <div className="button-row">
          {catalog.features.map((feature) => (
            <button
              key={feature.key}
              className={activeFeature === feature.key ? "primary-button compact-button" : "secondary-button compact-button"}
              onClick={() => setActiveFeature(feature.key as FeatureKey)}
            >
              {feature.name}
            </button>
          ))}
        </div>
      </section>

      {activeFeature === "montage" ? (
        <div className="page-stack">
          <section className="panel toolbar-panel two-row">
            <label className="field-label grow">
              图片文件夹
              <input value={montageFolder} onChange={(event) => setMontageFolder(event.target.value)} />
            </label>
            <label className="field-label">
              排序
              <select value={montageSort} onChange={(event) => setMontageSort(event.target.value)}>
                <option value="name_asc">名称升序</option>
                <option value="name_desc">名称降序</option>
                <option value="mtime_asc">修改时间升序</option>
                <option value="mtime_desc">修改时间降序</option>
              </select>
            </label>
            <label className="field-label">
              列数
              <input type="number" value={montageCols} onChange={(event) => setMontageCols(Number(event.target.value))} />
            </label>
            <label className="field-label">
              单格宽
              <input type="number" value={montageCellWidth} onChange={(event) => setMontageCellWidth(Number(event.target.value))} />
            </label>
            <label className="field-label">
              单格高
              <input type="number" value={montageCellHeight} onChange={(event) => setMontageCellHeight(Number(event.target.value))} />
            </label>
            <label className="field-label">
              间距
              <input type="number" value={montageGap} onChange={(event) => setMontageGap(Number(event.target.value))} />
            </label>
            <label className="field-label">
              背景色
              <input value={montageBackground} onChange={(event) => setMontageBackground(event.target.value)} />
            </label>
            <label className="field-label grow">
              输出路径
              <input value={montageOutput} onChange={(event) => setMontageOutput(event.target.value)} />
            </label>
            <div className="button-row">
              <button className="secondary-button" onClick={handleMontageAnalyze} disabled={busy}>
                分析布局
              </button>
              <button className="primary-button" onClick={handleMontageRun} disabled={busy}>
                {busy ? "处理中..." : "执行拼接"}
              </button>
            </div>
          </section>

          <div className="three-column-layout">
            <section className="panel">
              <h2>布局信息</h2>
              {montageAnalysis?.layout ? (
                <div className="result-stack">
                  <div className="result-card"><strong>图片数量</strong><div className="muted-text">{montageAnalysis.count}</div></div>
                  <div className="result-card"><strong>网格</strong><div className="muted-text">{montageAnalysis.layout.cols} 列 × {montageAnalysis.layout.rows} 行</div></div>
                  <div className="result-card"><strong>画布</strong><div className="muted-text">{montageAnalysis.layout.canvas_width} × {montageAnalysis.layout.canvas_height}</div></div>
                  <div className="result-card"><strong>预计内存</strong><div className="muted-text">{montageAnalysis.layout.memory_mb} MB</div></div>
                </div>
              ) : (
                <p className="muted-text">先做一次布局分析，这里会显示画布和内存估算。</p>
              )}
            </section>

            <section className="panel panel-span-2">
              <h2>源文件列表</h2>
              {montageAnalysis?.files?.length ? <pre>{montageAnalysis.files.join("\n")}</pre> : <p className="muted-text">这里会显示当前参与拼接的图片列表。</p>}
            </section>
          </div>
        </div>
      ) : null}

      {activeFeature === "square" ? (
        <div className="page-stack">
          <section className="panel toolbar-panel two-row">
            <label className="field-label grow">
              输入图片
              <input value={squareInput} onChange={(event) => setSquareInput(event.target.value)} />
            </label>
            <label className="field-label">
              列数
              <input type="number" value={squareCols} onChange={(event) => setSquareCols(Number(event.target.value))} />
            </label>
            <label className="field-label">
              行数
              <input type="number" value={squareRows} onChange={(event) => setSquareRows(Number(event.target.value))} />
            </label>
            <label className="field-label">
              模式
              <select value={squareMode} onChange={(event) => setSquareMode(event.target.value)}>
                <option value="area">面积近似不变</option>
                <option value="keep_width">保持宽度</option>
                <option value="keep_height">保持高度</option>
              </select>
            </label>
            <label className="field-label grow">
              输出路径
              <input value={squareOutput} onChange={(event) => setSquareOutput(event.target.value)} />
            </label>
            <div className="button-row">
              <button className="secondary-button" onClick={handleSquarePreview} disabled={busy}>
                预览参数
              </button>
              <button className="primary-button" onClick={handleSquareRun} disabled={busy}>
                {busy ? "处理中..." : "执行转换"}
              </button>
            </div>
          </section>

          <section className="panel">
            <h2>转换预览</h2>
            {squarePreview ? (
              <pre>{[
                `原图尺寸: ${squarePreview.original_width} × ${squarePreview.original_height}`,
                `网格: ${squarePreview.cols} × ${squarePreview.rows}`,
                `原始格子: ${squarePreview.cell_width} × ${squarePreview.cell_height}`,
                `转换后: ${squarePreview.new_width} × ${squarePreview.new_height}`,
                `转换后格子: ${squarePreview.new_cell_width} × ${squarePreview.new_cell_height}`,
                `模式: ${squarePreview.mode}`,
              ].join("\n")}</pre>
            ) : (
              <p className="muted-text">这里会显示正方形转换前后的尺寸对比。</p>
            )}
          </section>
        </div>
      ) : null}

      {activeFeature === "puzzle" ? (
        <div className="page-stack">
          <section className="panel toolbar-panel two-row">
            <label className="field-label grow">
              原图路径
              <input value={puzzleSource} onChange={(event) => setPuzzleSource(event.target.value)} />
            </label>
            <label className="field-label">
              碎片大小
              <input type="number" value={puzzlePieceSize} onChange={(event) => setPuzzlePieceSize(event.target.value ? Number(event.target.value) : "")} />
            </label>
            <div className="button-row">
              <button className="secondary-button" onClick={handlePuzzleInspect} disabled={busy}>
                分析原图
              </button>
              <button className="secondary-button" onClick={handlePuzzleAdapt} disabled={busy || puzzlePieceSize === ""}>
                智能适配
              </button>
            </div>
          </section>

          <div className="three-column-layout">
            <section className="panel">
              <h2>推荐配置</h2>
              {puzzleInspect?.suggested ? (
                <div className="page-stack">
                  <div className="result-card">
                    <strong>推荐碎片大小</strong>
                    <div className="muted-text">{puzzleInspect.suggested.piece_size}px</div>
                  </div>
                  <div className="result-card">
                    <strong>拼图规模</strong>
                    <div className="muted-text">
                      {puzzleInspect.suggested.cols} × {puzzleInspect.suggested.rows} / {puzzleInspect.suggested.total_pieces} 片
                    </div>
                  </div>
                  <div className="result-card">
                    <strong>适配后尺寸</strong>
                    <div className="muted-text">
                      {puzzleInspect.suggested.adapted_width} × {puzzleInspect.suggested.adapted_height}
                    </div>
                  </div>
                  <div className="result-card">
                    <strong>裁切损耗</strong>
                    <div className="muted-text">
                      {Math.round(puzzleInspect.suggested.loss_ratio * 10000) / 100}% / {puzzleInspect.suggested.loss_pixels} px
                    </div>
                  </div>
                </div>
              ) : (
                <p className="muted-text">先分析原图，这里会显示推荐碎片大小和裁切损耗。</p>
              )}
            </section>

            <section className="panel panel-span-2">
              <h2>候选尺寸</h2>
              {puzzleInspect?.suggestions?.length ? (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>尺寸</th>
                        <th>拼图规模</th>
                        <th>适配后尺寸</th>
                        <th>损耗</th>
                        <th>精确整除</th>
                      </tr>
                    </thead>
                    <tbody>
                      {puzzleInspect.suggestions.map((item) => (
                        <tr key={item.piece_size}>
                          <td>{item.piece_size}px</td>
                          <td>{item.cols} × {item.rows} / {item.total_pieces}</td>
                          <td>{item.adapted_width} × {item.adapted_height}</td>
                          <td>{Math.round(item.loss_ratio * 10000) / 100}%</td>
                          <td>{item.exact_fit ? "是" : "否"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted-text">这里会显示当前图像可选的碎片大小候选。</p>
              )}
            </section>
          </div>

          <section className="panel toolbar-panel two-row">
            <label className="field-label grow">
              拼图输出
              <input value={puzzleTarget} onChange={(event) => setPuzzleTarget(event.target.value)} />
            </label>
            <button className="primary-button" onClick={handlePuzzleCreate} disabled={busy || puzzlePieceSize === ""}>
              生成拼图
            </button>
          </section>

          <section className="panel toolbar-panel two-row">
            <label className="field-label grow">
              拼图路径
              <input value={puzzleImage} onChange={(event) => setPuzzleImage(event.target.value)} />
            </label>
            <label className="field-label grow">
              还原输出
              <input value={puzzleOutput} onChange={(event) => setPuzzleOutput(event.target.value)} />
            </label>
            <label className="field-label">
              代数
              <input type="number" value={puzzleGenerations} onChange={(event) => setPuzzleGenerations(Number(event.target.value))} />
            </label>
            <label className="field-label">
              种群
              <input type="number" value={puzzlePopulation} onChange={(event) => setPuzzlePopulation(Number(event.target.value))} />
            </label>
            <label className="field-label">
              选择
              <select value={puzzleSelection} onChange={(event) => setPuzzleSelection(event.target.value)}>
                <option value="tournament">tournament</option>
                <option value="roulette">roulette</option>
                <option value="rank">rank</option>
              </select>
            </label>
            <label className="field-label">
              变异率
              <input type="number" step="0.01" value={puzzleMutation} onChange={(event) => setPuzzleMutation(Number(event.target.value))} />
            </label>
            <button className="primary-button" onClick={handlePuzzleSolve} disabled={busy || solveTask?.status === "running"}>
              {solveTask?.status === "running" ? "任务进行中..." : "开始还原"}
            </button>
          </section>
        </div>
      ) : null}
    </div>
  );
}
