import { useEffect, useMemo, useState } from "react";

import { deletePlugin, loadPlugins, savePlugin, type PluginBlock, type PluginDefinition } from "../services/api";

type PluginEditorMode = "local" | "remote" | "auto-android";

type PluginEditorPageProps = {
  mode?: PluginEditorMode;
};

const MODE_OPTIONS: { value: PluginEditorMode; label: string }[] = [
  { value: "local", label: "本地取证" },
  { value: "remote", label: "远程取证" },
  { value: "auto-android", label: "自动取证" },
];

function editorDefaults(mode: PluginEditorMode): { module: string; blockType: string; title: string; packageAware: boolean } {
  switch (mode) {
    case "remote":
      return {
        module: "linux",
        blockType: "SSH命令",
        title: "远程取证插件制作",
        packageAware: false
      };
    case "auto-android":
      return {
        module: "android",
        blockType: "文件提取",
        title: "Android 自动取证插件制作",
        packageAware: true
      };
    default:
      return {
        module: "windows",
        blockType: "文件提取",
        title: "本地取证插件制作",
        packageAware: false
      };
  }
}

function createEmptyPlugin(mode: PluginEditorMode): PluginDefinition {
  const defaults = editorDefaults(mode);
  return {
    name: "",
    author: "",
    description: "",
    module: defaults.module,
    package_names: defaults.packageAware ? [] : [],
    blocks: []
  };
}

function createEmptyBlock(mode: PluginEditorMode): PluginBlock {
  const defaults = editorDefaults(mode);
  return {
    name: "",
    cmd: "",
    type: defaults.blockType,
    module: defaults.module,
    category: "",
    package_name: defaults.packageAware ? "" : ""
  };
}

function normalizeForMode(plugin: PluginDefinition, mode: PluginEditorMode): PluginDefinition {
  const defaults = editorDefaults(mode);
  const filteredBlocks = plugin.blocks.filter((block) => {
    if (mode === "remote") {
      return (block.type ?? "").includes("SSH") || (block.module ?? "").toLowerCase() === "linux";
    }
    if (mode === "auto-android") {
      return (block.module ?? "").toLowerCase() === "android";
    }
    return (block.type ?? "").includes("提取") || ["windows", "linux", "android", "ios"].includes((block.module ?? "").toLowerCase());
  });
  return {
    ...plugin,
    module: defaults.module,
    package_names: plugin.package_names ?? [],
    blocks: filteredBlocks
  };
}

const MODULE_FILTER_OPTIONS = [
  { value: "", label: "全部平台" },
  { value: "windows", label: "Windows" },
  { value: "linux", label: "Linux" },
  { value: "android", label: "Android" },
  { value: "ios", label: "iOS" },
];

export default function PluginEditorPage({ mode: initialMode = "local" }: PluginEditorPageProps) {
  const [mode, setMode] = useState<PluginEditorMode>(initialMode);
  const [moduleFilter, setModuleFilter] = useState("");
  const defaults = useMemo(() => editorDefaults(mode), [mode]);
  const [plugins, setPlugins] = useState<PluginDefinition[]>([]);
  const [editing, setEditing] = useState<PluginDefinition>(createEmptyPlugin(mode));
  const [packageNamesText, setPackageNamesText] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const filterModule = moduleFilter || undefined;
    const payload = await loadPlugins(filterModule);
    const filtered = payload.plugins
      .map((plugin) => normalizeForMode(plugin, mode))
      .filter((plugin) => plugin.blocks.length > 0 || mode !== "auto-android");
    setPlugins(filtered);
  }

  useEffect(() => {
    setEditing(createEmptyPlugin(mode));
    setPackageNamesText("");
    refresh().catch((loadError) => setError(loadError instanceof Error ? loadError.message : "插件加载失败"));
  }, [mode, moduleFilter]);

  useEffect(() => {
    setPackageNamesText((editing.package_names ?? []).join("\n"));
  }, [editing.package_names]);

  function updateBlock(index: number, field: keyof PluginBlock, value: string) {
    const blocks = [...editing.blocks];
    blocks[index] = { ...blocks[index], [field]: value };
    setEditing({ ...editing, blocks });
  }

  function addBlock() {
    setEditing({
      ...editing,
      blocks: [...editing.blocks, createEmptyBlock(mode)]
    });
  }

  function removeBlock(index: number) {
    setEditing({
      ...editing,
      blocks: editing.blocks.filter((_, currentIndex) => currentIndex !== index)
    });
  }

  async function handleSave() {
    setError("");
    setMessage("");
    try {
      const packageNames = defaults.packageAware
        ? packageNamesText
            .split(/\r?\n|,/)
            .map((item) => item.trim())
            .filter(Boolean)
        : [];
      const payload: PluginDefinition = {
        ...editing,
        module: defaults.module,
        package_names: packageNames,
        blocks: editing.blocks.map((block) => ({
          ...block,
          module: defaults.packageAware ? "android" : block.module || defaults.module,
          type: block.type || defaults.blockType
        }))
      };
      await savePlugin(payload);
      setEditing(payload);
      await refresh();
      setMessage(`插件已保存: ${payload.name}`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "插件保存失败");
    }
  }

  async function handleDelete() {
    if (!editing.name) {
      return;
    }
    setError("");
    setMessage("");
    try {
      await deletePlugin(editing.name);
      setEditing(createEmptyPlugin(mode));
      setPackageNamesText("");
      await refresh();
      setMessage("插件已删除。");
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "插件删除失败");
    }
  }

  return (
    <div className="page-stack">
      {message ? <p className="success-text">{message}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <section className="panel toolbar-panel">
        <label className="field-label">
          编辑模式
          <select
            value={mode}
            onChange={(event) => {
              const newMode = event.target.value as PluginEditorMode;
              setMode(newMode);
              setEditing(createEmptyPlugin(newMode));
              setPackageNamesText("");
              setMessage("");
              setError("");
            }}
          >
            {MODE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
        <label className="field-label">
          平台筛选
          <select
            value={moduleFilter}
            onChange={(event) => {
              setModuleFilter(event.target.value);
              setMessage("");
              setError("");
            }}
          >
            {MODULE_FILTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
      </section>

      <div className="three-column-layout">
        <section className="panel">
          <h2>已保存插件</h2>
          <div className="list-stack">
            <button
              className="secondary-button"
              onClick={() => {
                setEditing(createEmptyPlugin(mode));
                setPackageNamesText("");
              }}
            >
              新建插件
            </button>
            {plugins.map((plugin) => (
              <button key={plugin.name} className="list-button" onClick={() => setEditing(normalizeForMode(plugin, mode))}>
                <strong>{plugin.name}</strong>
                <span>{plugin.description || "无描述"}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel panel-span-2">
          <h2>{defaults.title}</h2>

          <div className="form-grid">
            <label className="field-label">
              插件名称
              <input value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} />
            </label>
            <label className="field-label">
              作者
              <input value={editing.author ?? ""} onChange={(event) => setEditing({ ...editing, author: event.target.value })} />
            </label>
            <label className="field-label full-span">
              描述
              <input value={editing.description ?? ""} onChange={(event) => setEditing({ ...editing, description: event.target.value })} />
            </label>
          </div>

          {defaults.packageAware ? (
            <div className="single-column-form top-space">
              <label className="field-label">
                Android 包名
                <textarea
                  rows={4}
                  value={packageNamesText}
                  onChange={(event) => setPackageNamesText(event.target.value)}
                  placeholder={"每行一个包名，例如\ncom.tencent.mm\ncom.xiaomi.notes"}
                />
              </label>
              <p className="muted-text">这里填写的包名会直接参与 Android 自动取证匹配，命中后自动分析对应应用。</p>
            </div>
          ) : null}

          <div className="button-row top-space">
            <button className="secondary-button" onClick={addBlock}>
              添加积木
            </button>
            <button className="primary-button" onClick={handleSave}>
              保存插件
            </button>
            <button className="secondary-button" onClick={handleDelete}>
              删除插件
            </button>
          </div>

          <div className="result-stack top-space">
            {editing.blocks.map((block, index) => (
              <article key={index} className="result-card">
                <div className="form-grid">
                  <label className="field-label">
                    名称
                    <input value={block.name} onChange={(event) => updateBlock(index, "name", event.target.value)} />
                  </label>
                  <label className="field-label">
                    类型
                    <input value={block.type} onChange={(event) => updateBlock(index, "type", event.target.value)} />
                  </label>
                  <label className="field-label">
                    模块
                    <input
                      value={defaults.packageAware ? "android" : block.module ?? ""}
                      onChange={(event) => updateBlock(index, "module", event.target.value)}
                      disabled={defaults.packageAware}
                    />
                  </label>
                  <label className="field-label">
                    分类
                    <input value={block.category ?? ""} onChange={(event) => updateBlock(index, "category", event.target.value)} />
                  </label>
                  {defaults.packageAware ? (
                    <label className="field-label full-span">
                      当前积木包名
                      <input
                        value={block.package_name ?? ""}
                        onChange={(event) => updateBlock(index, "package_name", event.target.value)}
                        placeholder="可留空，默认沿用上面的 Android 包名列表或从路径推断"
                      />
                    </label>
                  ) : null}
                  <label className="field-label full-span">
                    命令 / 路径
                    <input value={block.cmd} onChange={(event) => updateBlock(index, "cmd", event.target.value)} />
                  </label>
                </div>
                <div className="button-row top-space">
                  <button className="secondary-button compact-button" onClick={() => removeBlock(index)}>
                    删除积木
                  </button>
                </div>
              </article>
            ))}
            {!editing.blocks.length ? <p className="muted-text">当前还没有积木，先添加一个开始编辑。</p> : null}
          </div>
        </section>
      </div>
    </div>
  );
}
