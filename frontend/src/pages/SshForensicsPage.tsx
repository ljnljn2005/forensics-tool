import { useEffect, useState } from "react";

import { loadPlugins, loadSettings, runSshPlugin, testSshConnection, type PluginDefinition } from "../services/api";

export default function SshForensicsPage() {
  const [host, setHost] = useState("");
  const [port, setPort] = useState("22");
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [plugins, setPlugins] = useState<PluginDefinition[]>([]);
  const [selectedPlugin, setSelectedPlugin] = useState("");
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadSettings()
      .then((settings) => {
        const ssh = settings.current_case?.ssh ?? settings.ssh;
        if (ssh) {
          setHost(ssh.host ?? "");
          setPort(String(ssh.port ?? 22));
          setUser(ssh.user ?? "");
          setPassword(ssh.password ?? "");
        }
      })
      .catch(() => undefined);
    loadPlugins()
      .then((payload) => {
        const sshPlugins = payload.plugins.filter((plugin) =>
          plugin.blocks.some((block) => block.type?.includes("SSH") || block.type?.includes("命令"))
        );
        setPlugins(sshPlugins);
        if (sshPlugins[0]) {
          setSelectedPlugin(sshPlugins[0].name);
        }
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "插件加载失败");
      });
  }, []);

  async function handleTest() {
    setLoading(true);
    setError("");
    try {
      const payload = await testSshConnection(host, Number(port || "22"), user, password);
      setOutput(payload.message);
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : "连接测试失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleRun() {
    setLoading(true);
    setError("");
    try {
      const payload = await runSshPlugin(host, Number(port || "22"), user, password, selectedPlugin);
      setOutput(
        payload.results.length
          ? payload.results.map((item) => `# ${item.name}\n命令: ${item.cmd}\n\n${item.output}`).join("\n\n----------------\n\n")
          : payload.message || "没有可执行结果"
      );
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "远程执行失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel toolbar-panel two-row">
        <label className="field-label grow">
          主机
          <input value={host} onChange={(event) => setHost(event.target.value)} placeholder="SSH 主机 IP" />
        </label>
        <label className="field-label">
          端口
          <input value={port} onChange={(event) => setPort(event.target.value)} placeholder="22" />
        </label>
        <label className="field-label grow">
          用户
          <input value={user} onChange={(event) => setUser(event.target.value)} placeholder="root" />
        </label>
        <label className="field-label grow">
          密码
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="密码" />
        </label>
        <label className="field-label grow">
          选择插件
          <select value={selectedPlugin} onChange={(event) => setSelectedPlugin(event.target.value)}>
            {plugins.map((plugin) => (
              <option key={plugin.name} value={plugin.name}>
                {plugin.name}
              </option>
            ))}
          </select>
        </label>
        <div className="button-row">
          <button className="secondary-button" onClick={handleTest} disabled={loading || !host || !user}>
            测试连接
          </button>
          <button className="primary-button" onClick={handleRun} disabled={loading || !host || !user || !selectedPlugin}>
            {loading ? "执行中..." : "执行选中插件"}
          </button>
        </div>
      </section>

      {error ? <p className="error-text">{error}</p> : null}

      <section className="panel">
        <h2>执行结果</h2>
        {output ? <pre>{output}</pre> : <p className="muted-text">测试连接或运行插件后，这里会显示远程执行输出。</p>}
      </section>
    </div>
  );
}
