const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type AndroidAutoForensicsEntry = {
  group: string;
  name: string;
  cmd: string;
  type: string;
  module: string;
  package_name?: string;
  resolved_path?: string;
  resolved_candidates?: string[];
  result?: string;
};

export type AndroidAutoForensicsResult = {
  mapping_path: string;
  android_system_roots?: string[];
  installed_packages: string[];
  matched_packages: Array<{
    package_name: string;
    entries: AndroidAutoForensicsEntry[];
  }>;
};

export type DatabaseTablePreview = {
  name: string;
  columns: string[];
  row_count: number;
  preview_rows: Array<Record<string, unknown>>;
};

export type DatabaseInspectResult = {
  ok: boolean;
  database_path: string;
  source_path: string;
  tried_paths: string[];
  message: string;
  tables: DatabaseTablePreview[];
};

export type FileBrowserChild = {
  name: string;
  path: string;
  is_dir: boolean;
  is_file: boolean;
  detected_kind?: string;
  detected_format?: string;
  detected_mime?: string;
  preferred_extension?: string;
};

export type FileBrowserInspectResult = {
  ok: boolean;
  kind: "file" | "directory";
  path: string;
  source_path: string;
  children: FileBrowserChild[];
  tried_paths: string[];
  detected_kind?: string;
  detected_format?: string;
  detected_mime?: string;
  preferred_extension?: string;
};

export type RegistryScanResult = {
  scan_item: string;
  mapping_path: string;
  text: string;
};

export type LogEntry = {
  name: string;
  path: string;
  display_path: string;
  category: string;
  size: number;
  modified: number;
};

export type LogScanResult = {
  module: "windows" | "linux";
  mapping_path: string;
  entries: LogEntry[];
};

export type LogEvent = {
  event_id: string;
  provider: string;
  time_created: string;
  level: string;
  raw: string;
};

export type LogDetailResult = {
  entry: LogEntry;
  text: string;
  events: LogEvent[];
};

export type MemoryTask = {
  name: string;
  engine: string;
  output: string;
  plugin?: string;
  result_path?: string;
};

export type MemoryTaskCatalog = {
  module: "windows" | "linux";
  default_tool_root: string;
  tasks: MemoryTask[];
};

export type MemoryTaskPreview = {
  module: "windows" | "linux";
  task: MemoryTask;
  tool_paths: Record<string, string>;
  preview_text: string;
};

export type MemoryTaskRunResult = {
  ok: boolean;
  text: string;
  rows: Record<string, string>[];
};

export type SearchResultItem = {
  plugin: string;
  author: string;
  description: string;
  block_name: string;
  cmd: string;
  type: string;
  module: string;
};

export type SearchResult = {
  keyword: string;
  results: SearchResultItem[];
};

export type ExtractorEntry = {
  group: string;
  plugin: string;
  name: string;
  cmd: string;
  type: string;
  module: string;
};

export type ExtractorCatalog = {
  module: string;
  module_label: string;
  entries: ExtractorEntry[];
  groups: Array<{ name: string; count: number }>;
};

export type ExtractorRunResult = {
  module: string;
  mapping_path: string;
  entry: ExtractorEntry;
  text: string;
};

export type AppSettings = {
  proxy?: string;
  api_url?: string;
  api_key?: string;
  model?: string;
  market_repo?: string;
  mapping_path?: string;
  android_system_roots?: string[];
  current_case_id?: string;
  current_case?: CaseRecord | null;
  ssh?: {
    host: string;
    port: number;
    user: string;
    password: string;
  };
  mcp_server?: McpServerSettings;
};

export type CaseRecord = {
  id: string;
  name: string;
  description?: string;
  evidence_items: CaseEvidenceItem[];
  evidence_paths: {
    windows?: string;
    linux?: string;
    android?: string;
    ios?: string;
    windows_memory?: string;
    linux_memory?: string;
  };
  ssh: {
    host?: string;
    port?: number;
    user?: string;
    password?: string;
  };
};

export type CaseEvidenceItem = {
  id: string;
  type: "windows" | "linux" | "android" | "ios" | "windows_memory" | "linux_memory";
  label: string;
  path: string;
};

export type CaseListResult = {
  cases: CaseRecord[];
  current_case_id: string;
  current_case: CaseRecord | null;
};

export type McpServerSettings = {
  enabled: boolean;
  transport: "stdio" | "http";
  host: string;
  port: number;
  auto_start: boolean;
  exposed_tool_groups: string[];
};

export type McpToolGroup = {
  key: string;
  label: string;
  status: string;
  tools: string[];
};

export type McpServerSettingsResult = {
  settings: McpServerSettings;
  tool_groups: McpToolGroup[];
  status: {
    implemented_groups: string[];
    server_module: string;
    running: boolean;
  };
};

export type McpExportResult = {
  server_name: string;
  transport: "stdio" | "http";
  python_executable: string;
  project_root: string;
  module: string;
  http_url: string;
  active_json: string;
  stdio_json: string;
  http_json: string;
  notes: string[];
};

export type PluginBlock = {
  name: string;
  cmd: string;
  type: string;
  module?: string;
  category?: string;
  package_name?: string;
};

export type PluginDefinition = {
  name: string;
  author?: string;
  description?: string;
  module?: string;
  package_names?: string[];
  detected_modules?: string[];
  blocks: PluginBlock[];
};

export type PluginListResult = {
  plugins: PluginDefinition[];
};

export type PluginMarketResult = {
  plugins: PluginDefinition[];
};

export type SshPluginRunResult = {
  ok: boolean;
  message?: string;
  results: Array<{
    name: string;
    cmd: string;
    type: string;
    output: string;
  }>;
};

export type AiAnalysisResult = {
  text: string;
  result: string;
};

export type ToolboxTool = {
  key: string;
  name: string;
  description: string;
  tool_dir: string;
  entry_path: string;
  readme_path: string;
};

export type ToolboxCatalog = {
  tools: ToolboxTool[];
};

export type JigsawCatalog = {
  key: string;
  name: string;
  description: string;
  tool_dir: string;
  features: Array<{ key: string; name: string }>;
};

export type JigsawMontageAnalysis = {
  folder_path: string;
  count: number;
  files: string[];
  layout: null | {
    cols: number;
    rows: number;
    canvas_width: number;
    canvas_height: number;
    memory_mb: number;
  };
};

export type JigsawSquarePreview = {
  input_path: string;
  original_width: number;
  original_height: number;
  cols: number;
  rows: number;
  cell_width: number;
  cell_height: number;
  new_width: number;
  new_height: number;
  new_cell_width: number;
  new_cell_height: number;
  mode: string;
};

export type JigsawPuzzleInspect = {
  image_path: string;
  width: number;
  height: number;
  valid_piece_sizes: number[];
  suggested: null | {
    piece_size: number;
    cols: number;
    rows: number;
    total_pieces: number;
    adapted_width: number;
    adapted_height: number;
    loss_pixels: number;
    loss_ratio: number;
    used_ratio: number;
    exact_fit: boolean;
  };
  suggestions: Array<{
    piece_size: number;
    cols: number;
    rows: number;
    total_pieces: number;
    adapted_width: number;
    adapted_height: number;
    loss_pixels: number;
    loss_ratio: number;
    used_ratio: number;
    exact_fit: boolean;
  }>;
};

export type JigsawPuzzleTask = {
  task_id: string;
  status: string;
  progress: number;
  message: string;
  output_path?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json"
    },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function scanAndroidAutoForensics(mappingPath: string, entries: AndroidAutoForensicsEntry[]) {
  return request<AndroidAutoForensicsResult>("/api/android/auto-forensics/scan", {
    method: "POST",
    body: JSON.stringify({
      mapping_path: mappingPath,
      entries
    })
  });
}

export function loadCases() {
  return request<CaseListResult>("/api/cases");
}

export function saveCase(payload: CaseRecord) {
  return request<CaseListResult>("/api/cases", {
    method: "POST",
    body: JSON.stringify({ payload })
  });
}

export function selectCase(caseId: string) {
  return request<CaseListResult>("/api/cases/select", {
    method: "POST",
    body: JSON.stringify({ case_id: caseId })
  });
}

export function deleteCase(caseId: string) {
  return request<CaseListResult>(`/api/cases/${encodeURIComponent(caseId)}`, {
    method: "DELETE"
  });
}

export function loadMcpSettings() {
  return request<McpServerSettingsResult>("/api/mcp/settings");
}

export function saveMcpSettings(settings: McpServerSettings) {
  return request<McpServerSettingsResult>("/api/mcp/settings", {
    method: "POST",
    body: JSON.stringify(settings)
  });
}

export function exportMcpConfig() {
  return request<McpExportResult>("/api/mcp/export");
}

export function inspectDatabase(mappingPath: string, databasePath: string) {
  return request<DatabaseInspectResult>("/api/database/inspect", {
    method: "POST",
    body: JSON.stringify({
      mapping_path: mappingPath,
      database_path: databasePath
    })
  });
}

export function inspectMappedPath(mappingPath: string, targetPath: string) {
  return request<FileBrowserInspectResult>("/api/file-browser/inspect", {
    method: "POST",
    body: JSON.stringify({
      mapping_path: mappingPath,
      target_path: targetPath
    })
  });
}

export function openMappedPath(mappingPath: string, targetPath: string, action: "default" | "explorer") {
  return request<{ ok: boolean; opened_path: string; source_path: string; kind: string }>("/api/file-browser/open", {
    method: "POST",
    body: JSON.stringify({
      mapping_path: mappingPath,
      target_path: targetPath,
      action
    })
  });
}

export function scanRegistry(mappingPath: string, scanItem: string, registryPath = "") {
  return request<RegistryScanResult>("/api/windows/registry/scan", {
    method: "POST",
    body: JSON.stringify({
      mapping_path: mappingPath,
      scan_item: scanItem,
      registry_path: registryPath
    })
  });
}

export function scanLogs(mappingPath: string, module: "windows" | "linux") {
  return request<LogScanResult>("/api/logs/scan", {
    method: "POST",
    body: JSON.stringify({
      mapping_path: mappingPath,
      module
    })
  });
}

export function loadLogDetail(entry: LogEntry) {
  return request<LogDetailResult>("/api/logs/detail", {
    method: "POST",
    body: JSON.stringify({ entry })
  });
}

export function loadMemoryTasks(module: "windows" | "linux") {
  return request<MemoryTaskCatalog>(`/api/memory/tasks?module=${module}`);
}

export function previewMemoryTask(
  module: "windows" | "linux",
  task: MemoryTask,
  toolRoot: string,
  memoryImage: string,
  offline: boolean
) {
  return request<MemoryTaskPreview>("/api/memory/preview", {
    method: "POST",
    body: JSON.stringify({
      module,
      task,
      tool_root: toolRoot,
      memory_image: memoryImage,
      offline
    })
  });
}

export function runMemoryTask(
  module: "windows" | "linux",
  task: MemoryTask,
  toolRoot: string,
  memoryImage: string,
  offline: boolean
) {
  return request<MemoryTaskRunResult>("/api/memory/run", {
    method: "POST",
    body: JSON.stringify({
      module,
      task,
      tool_root: toolRoot,
      memory_image: memoryImage,
      offline
    })
  });
}

export function stopMemoryMount() {
  return request<{ ok: boolean; text: string }>("/api/memory/stop-mount", {
    method: "POST"
  });
}

export function globalSearch(keyword: string) {
  return request<SearchResult>(`/api/search?keyword=${encodeURIComponent(keyword)}`);
}

export function loadExtractorEntries(module: "windows" | "linux" | "android" | "ios") {
  return request<ExtractorCatalog>(`/api/extractor/entries?module=${module}`);
}

export function runExtractorEntry(module: "windows" | "linux" | "android" | "ios", mappingPath: string, entry: ExtractorEntry) {
  return request<ExtractorRunResult>("/api/extractor/run", {
    method: "POST",
    body: JSON.stringify({
      module,
      mapping_path: mappingPath,
      entry
    })
  });
}

export function loadSettings() {
  return request<AppSettings>("/api/settings");
}

export function saveSettings(settings: AppSettings) {
  return request<AppSettings>("/api/settings", {
    method: "POST",
    body: JSON.stringify(settings)
  });
}

export function loadPlugins() {
  return request<PluginListResult>("/api/plugins");
}

export function savePlugin(plugin: PluginDefinition) {
  return request<{ ok: boolean; plugin: PluginDefinition }>("/api/plugins", {
    method: "POST",
    body: JSON.stringify(plugin)
  });
}

export function deletePlugin(name: string) {
  return request<{ ok: boolean }>(`/api/plugins/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
}

export function fetchPluginMarket(url: string) {
  return request<PluginMarketResult>(`/api/plugin-market?url=${encodeURIComponent(url)}`);
}

export function testSshConnection(host: string, port: number, user: string, password: string) {
  return request<{ ok: boolean; message: string }>("/api/ssh/test", {
    method: "POST",
    body: JSON.stringify({ host, port, user, password })
  });
}

export function runSshPlugin(host: string, port: number, user: string, password: string, pluginName: string) {
  return request<SshPluginRunResult>("/api/ssh/run-plugin", {
    method: "POST",
    body: JSON.stringify({
      host,
      port,
      user,
      password,
      plugin_name: pluginName
    })
  });
}

export function runAiAnalysis(text: string) {
  return request<AiAnalysisResult>("/api/ai/analyze", {
    method: "POST",
    body: JSON.stringify({ text })
  });
}

export function loadToolboxTools() {
  return request<ToolboxCatalog>("/api/toolbox/tools");
}

export function launchToolboxTool(toolKey: string) {
  return request<{ ok: boolean; message: string; pid: number; entry_path: string }>("/api/toolbox/launch", {
    method: "POST",
    body: JSON.stringify({ tool_key: toolKey })
  });
}

export function loadJigsawCatalog() {
  return request<JigsawCatalog>("/api/toolbox/jigsaw");
}

export function analyzeJigsawMontage(payload: {
  folder_path: string;
  sort_mode: string;
  cols: number;
  cell_width: number;
  cell_height: number;
  gap: number;
}) {
  return request<JigsawMontageAnalysis>("/api/toolbox/jigsaw/montage/analyze", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function runJigsawMontage(payload: {
  folder_path: string;
  sort_mode: string;
  cols: number;
  cell_width: number;
  cell_height: number;
  gap: number;
  background: string;
  output_path: string;
}) {
  return request<{ ok: boolean; output_path: string; count: number; message: string }>("/api/toolbox/jigsaw/montage/run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function previewJigsawSquare(payload: { image_path: string; cols: number; rows: number; mode: string }) {
  return request<JigsawSquarePreview>("/api/toolbox/jigsaw/square/preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function runJigsawSquare(payload: { image_path: string; cols: number; rows: number; mode: string; output_path: string }) {
  return request<{ ok: boolean; output_path: string; preview: JigsawSquarePreview; message: string }>("/api/toolbox/jigsaw/square/run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function inspectJigsawPuzzle(payload: { image_path: string }) {
  return request<JigsawPuzzleInspect>("/api/toolbox/jigsaw/puzzle/inspect", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function adaptJigsawPuzzle(payload: { image_path: string; piece_size: number }) {
  return request<{
    ok: boolean;
    output_path: string;
    adapted: boolean;
    mode: string;
    crop: {
      original_width: number;
      original_height: number;
      adapted_width: number;
      adapted_height: number;
      crop_left: number;
      crop_top: number;
      crop_right: number;
      crop_bottom: number;
    };
  }>("/api/toolbox/jigsaw/puzzle/adapt", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createJigsawPuzzle(payload: { image_path: string; output_path: string; piece_size: number }) {
  return request<{ ok: boolean; output_path: string; piece_size: number; rows: number; columns: number; pieces: number; message: string }>(
    "/api/toolbox/jigsaw/puzzle/create",
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export function solveJigsawPuzzle(payload: {
  puzzle_path: string;
  output_path: string;
  piece_size: number | "";
  generations: number;
  population: number;
  selection: string;
  mutation: number;
}) {
  return request<JigsawPuzzleTask>("/api/toolbox/jigsaw/puzzle/solve", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function loadJigsawPuzzleTask(taskId: string) {
  return request<JigsawPuzzleTask>(`/api/toolbox/jigsaw/puzzle/tasks/${encodeURIComponent(taskId)}`);
}
