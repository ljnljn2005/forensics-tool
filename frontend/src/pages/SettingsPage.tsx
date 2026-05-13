import { useEffect, useMemo, useState } from "react";

import { loadSettings, saveSettings, type AppSettings } from "../services/api";

function rootsToText(settings: AppSettings) {
  return (settings.android_system_roots ?? []).join("\n");
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>({});
  const [androidRootsText, setAndroidRootsText] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [error, setError] = useState("");

  const rootCount = useMemo(
    () => androidRootsText.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).length,
    [androidRootsText]
  );

  useEffect(() => {
    loadSettings()
      .then((payload) => {
        setSettings(payload);
        setAndroidRootsText(rootsToText(payload));
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "设置加载失败"));
  }, []);

  async function handleSave() {
    setError("");
    setSavedMessage("");
    try {
      const payload = await saveSettings({
        ...settings,
        android_system_roots: androidRootsText
          .split(/\r?\n/)
          .map((item) => item.trim())
          .filter(Boolean)
      });
      setSettings(payload);
      setAndroidRootsText(rootsToText(payload));
      setSavedMessage("设置已保存。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "设置保存失败");
    }
  }

  return (
    <div className="page-stack">
      <section className="panel">
        <h2>系统设置</h2>
        <div className="form-grid">
          <label className="field-label">
            代理
            <input value={settings.proxy ?? ""} onChange={(event) => setSettings({ ...settings, proxy: event.target.value })} placeholder="例如 http://127.0.0.1:7897" />
          </label>
          <label className="field-label">
            OpenAI API URL
            <input value={settings.api_url ?? ""} onChange={(event) => setSettings({ ...settings, api_url: event.target.value })} />
          </label>
          <label className="field-label">
            API Key
            <input type="password" value={settings.api_key ?? ""} onChange={(event) => setSettings({ ...settings, api_key: event.target.value })} />
          </label>
          <label className="field-label">
            模型
            <input value={settings.model ?? ""} onChange={(event) => setSettings({ ...settings, model: event.target.value })} />
          </label>
          <label className="field-label">
            插件市场仓库 URL
            <input value={settings.market_repo ?? ""} onChange={(event) => setSettings({ ...settings, market_repo: event.target.value })} />
          </label>
          <label className="field-label">
            默认映射路径
            <input value={settings.mapping_path ?? ""} onChange={(event) => setSettings({ ...settings, mapping_path: event.target.value })} />
          </label>
        </div>

        <div className="form-grid">
          <label className="field-label">
            Android 系统预设路径
            <textarea
              rows={6}
              value={androidRootsText}
              onChange={(event) => setAndroidRootsText(event.target.value)}
              placeholder={"/data/user/0\n/data/data\n/data/user_de/0"}
            />
          </label>
        </div>
        <p className="muted-text">
          自动取证会按“映射路径 + 系统预设路径 + 包名 + 插件积木细分路径”逐个尝试匹配。当前共配置 {rootCount} 条系统预设路径。
        </p>

        <div className="button-row">
          <button className="primary-button" onClick={handleSave}>
            保存设置
          </button>
          {savedMessage ? <span className="success-text">{savedMessage}</span> : null}
        </div>
        {error ? <p className="error-text">{error}</p> : null}
      </section>
    </div>
  );
}
