import { useEffect, useMemo, useState } from "react";

import { fetchPluginMarket, loadSettings, savePlugin, type PluginDefinition } from "../services/api";

const defaultMarketUrl = "https://api.github.com/repos/ljnljn2005/forensics-plugin-market/contents/";

export default function PluginMarketPage() {
  const [marketUrl, setMarketUrl] = useState(defaultMarketUrl);
  const [plugins, setPlugins] = useState<PluginDefinition[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");
  const [scope, setScope] = useState<"all" | "android">("android");

  const filteredPlugins = useMemo(() => {
    const filteredByScope = plugins.filter((plugin) => {
      if (scope === "all") {
        return true;
      }
      const modules = plugin.detected_modules ?? [];
      return modules.includes("android") || (plugin.package_names?.length ?? 0) > 0;
    });

    const normalizedKeyword = keyword.trim().toLowerCase();
    if (!normalizedKeyword) {
      return filteredByScope;
    }
    return filteredByScope.filter((plugin) =>
      [
        plugin.name,
        plugin.author ?? "",
        plugin.description ?? "",
        ...(plugin.package_names ?? []),
        ...plugin.blocks.map((block) => `${block.name} ${block.cmd} ${block.type} ${block.module ?? ""}`)
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedKeyword)
    );
  }, [plugins, keyword, scope]);

  async function handleLoad() {
    setError("");
    setMessage("");
    try {
      const payload = await fetchPluginMarket(marketUrl);
      setPlugins(payload.plugins);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "插件市场拉取失败");
    }
  }

  useEffect(() => {
    const run = async () => {
      try {
        const settings = await loadSettings();
        const nextUrl = settings.market_repo || defaultMarketUrl;
        setMarketUrl(nextUrl);
        const payload = await fetchPluginMarket(nextUrl);
        setPlugins(payload.plugins);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "插件市场拉取失败");
      }
    };
    void run();
  }, []);

  async function handleInstall(plugin: PluginDefinition) {
    setError("");
    try {
      await savePlugin(plugin);
      if (plugin.package_names?.length) {
        setMessage(`已安装 ${plugin.name}，Android 自动取证将按包名自动匹配：${plugin.package_names.join(", ")}`);
      } else {
        setMessage(`已安装插件 ${plugin.name}`);
      }
    } catch (installError) {
      setError(installError instanceof Error ? installError.message : "插件安装失败");
    }
  }

  return (
    <div className="page-stack">
      <section className="panel toolbar-panel two-row">
        <label className="field-label grow">
          市场 URL
          <input value={marketUrl} onChange={(event) => setMarketUrl(event.target.value)} />
        </label>
        <label className="field-label grow">
          搜索插件 / 包名
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="例如 com.tencent.mm" />
        </label>
        <label className="field-label">
          范围
          <select value={scope} onChange={(event) => setScope(event.target.value as "all" | "android")}>
            <option value="android">Android 自动取证优先</option>
            <option value="all">全部插件</option>
          </select>
        </label>
        <button className="primary-button" onClick={handleLoad}>
          拉取插件市场
        </button>
      </section>

      {message ? <p className="success-text">{message}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <section className="panel">
        <h2>Android 自动取证插件优先视图</h2>
        <p className="muted-text">安装带包名规则的 Android 插件后，Android 自动取证页会根据检材中的包名自动匹配并分析对应软件。</p>
      </section>

      <section className="panel">
        <h2>插件市场</h2>
        <div className="result-stack">
          {filteredPlugins.map((plugin) => (
            <article key={plugin.name} className="result-card">
              <h3>{plugin.name}</h3>
              {plugin.author ? <p className="muted-text">作者: {plugin.author}</p> : null}
              {plugin.description ? <p className="muted-text">{plugin.description}</p> : null}
              <div className="tag-list top-space">
                <span className="tag-chip">{plugin.blocks.length} 个积木</span>
                {(plugin.detected_modules ?? []).map((module) => (
                  <span key={`${plugin.name}-${module}`} className="tag-chip">
                    {module}
                  </span>
                ))}
                {(plugin.package_names ?? []).map((pkg) => (
                  <span key={`${plugin.name}-${pkg}`} className="tag-chip">
                    {pkg}
                  </span>
                ))}
              </div>
              <div className="button-row top-space">
                <button className="primary-button" onClick={() => handleInstall(plugin)}>
                  安装到本地
                </button>
              </div>
            </article>
          ))}
          {!filteredPlugins.length ? <p className="muted-text">当前筛选条件下没有可显示的插件。</p> : null}
        </div>
      </section>
    </div>
  );
}
