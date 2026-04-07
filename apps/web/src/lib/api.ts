import { supabase } from "./supabase";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

// ── Auth token helpers ────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

export function setToken(token: string) {
  localStorage.setItem("auth_token", token);
  // Also set a cookie so Next.js middleware can read it for route protection
  document.cookie = `auth_token=${token}; path=/; SameSite=Strict; max-age=${60 * 60 * 24 * 7}`;
}

export function clearToken() {
  localStorage.removeItem("auth_token");
  document.cookie = "auth_token=; path=/; max-age=0";
}

/**
 * Always returns the freshest available token.
 * Prefers the live Supabase session (auto-refreshed) over the cached localStorage value.
 * Exported so SSE endpoints (EventSource) can also get a fresh token before connecting.
 */
export async function getFreshToken(): Promise<string | null> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token ?? null;
    if (token) {
      // Keep localStorage + cookie in sync so middleware still works
      setToken(token);
    }
    return token;
  } catch {
    // Supabase not available (SSR, missing env vars) — fall back to cached token
    return getToken();
  }
}

// Keep localStorage/cookie fresh whenever Supabase silently refreshes the session
if (typeof window !== "undefined") {
  supabase.auth.onAuthStateChange((_event, session) => {
    if (session?.access_token) {
      setToken(session.access_token);
    } else {
      clearToken();
    }
  });
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getFreshToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Base fetch helpers ────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `GET ${path} failed: ${res.status}`);
  }
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `POST ${path} failed: ${res.status}`);
  }
  return res.json();
}

// ── Auth (Supabase) ───────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
  const token = data.session!.access_token;
  setToken(token);
  return data;
}

export async function register(email: string, password: string) {
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw new Error(error.message);
  // session is null if email confirmation is required
  if (data.session) {
    setToken(data.session.access_token);
  }
  return data;
}

export function getMe() {
  return get<{ id: string; email: string; plan: string; created_at: string }>("/auth/me");
}

export async function logout() {
  await supabase.auth.signOut();
  clearToken();
  window.location.href = "/login";
}

// ── Projects ──────────────────────────────────────────────────────────────────

export function getProjects() {
  return get<{ id: number; name: string; status?: string; created_at?: string }[]>("/projects");
}

export function createProject(name: string) {
  return post<{ id: number; name: string }>("/projects", { name });
}

export async function deleteProject(projectId: number) {
  return fetch(`${API_BASE_URL}/projects/${projectId}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
}

export function getProjectStats() {
  return get<{
    total_projects: number;
    total_files: number;
    total_analyses: number;
    ready_projects: number;
  }>("/projects/stats");
}

// ── Upload ────────────────────────────────────────────────────────────────────

export async function uploadFile(projectId: number, file: File) {
  const formData = new FormData();
  formData.append("project_id", String(projectId));
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/upload`, {
    method: "POST",
    headers: await authHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json();
}

// ── Analysis ──────────────────────────────────────────────────────────────────

export function runAnalysis(projectId: number) {
  return post<Record<string, unknown>>("/analysis/run", { project_id: projectId });
}

export function getDataPreview(projectId: number, rows = 5) {
  return get<{
    columns: string[];
    rows: unknown[][];
    total_rows: number;
    total_columns: number;
    missing_pct: number;
  }>(`/analysis/preview/${projectId}?rows=${rows}`);
}

export interface DataTableColumn {
  name: string;
  dtype: "integer" | "float" | "boolean" | "datetime" | "text";
  null_count: number;
  null_pct: number;
  unique_count: number;
  min?: number | string;
  max?: number | string;
  mean?: number;
}

export interface DataTableResponse {
  project_id: number;
  columns: DataTableColumn[];
  rows: (string | number | boolean | null)[][];
  total_rows: number;
  total_pages: number;
  page: number;
  per_page: number;
  sort_col: string | null;
  sort_dir: "asc" | "desc";
  search: string;
}

export function getDataTable(
  projectId: number,
  opts: {
    page?: number;
    perPage?: number;
    sortCol?: string;
    sortDir?: "asc" | "desc";
    search?: string;
  } = {}
) {
  const params = new URLSearchParams();
  params.set("project_id", String(projectId));
  if (opts.page) params.set("page", String(opts.page));
  if (opts.perPage) params.set("per_page", String(opts.perPage));
  if (opts.sortCol) params.set("sort_col", opts.sortCol);
  if (opts.sortDir) params.set("sort_dir", opts.sortDir);
  if (opts.search) params.set("search", opts.search);
  return get<DataTableResponse>(`/analysis/data-table?${params.toString()}`);
}

export interface ProjectInsights {
  project_id: number;
  project_name: string;
  analysis_id: number | null;
  created_at: string | null;
  health_score: number | null;
  insights: { type: string; title: string; finding: string; severity: string }[];
}

export function getProjectLatestInsights(projectId: number) {
  return get<ProjectInsights>(`/projects/${projectId}/latest-insights`);
}

export function shareAnalysis(projectId: number) {
  return post<{ share_token: string }>(`/analysis/share/${projectId}`);
}

export function getSharedAnalysis(token: string) {
  return get<{ project_id: number; created_at: string; result: Record<string, unknown> }>(
    `/analysis/shared/${token}`
  );
}

export function getAnalysisHistory(projectId: number, limit = 10) {
  return get<{ id: number; project_id: number; created_at: string; file_hash: string | null }[]>(
    `/analysis/history/${projectId}?limit=${limit}`
  );
}

export function getAnalysisResult(analysisId: number) {
  return get<{
    id: number;
    project_id: number;
    created_at: string;
    file_hash: string | null;
    result: Record<string, unknown>;
  }>(`/analysis/result/${analysisId}`);
}

export interface StorySlide {
  slide_num: number;
  title: string;
  narrative: string;
  key_points: string[];
}

export interface DataStory {
  title: string;
  slides: StorySlide[];
}

export function generateStory(analysisId: number) {
  return post<DataStory>(`/analysis/story/${analysisId}`);
}

// ── Charts ────────────────────────────────────────────────────────────────────

export function getSuggestedCharts(projectId: number) {
  return post<{ charts: unknown[] }>("/charts/suggest", { project_id: projectId });
}

/** @deprecated use getSuggestedCharts */
export function getSuggestedChart(projectId: number) {
  return getSuggestedCharts(projectId);
}

// ── Explore: Time Series ──────────────────────────────────────────────────────

export function getTimeseriesColumns(projectId: number) {
  return get<{ date_columns: string[]; value_columns: string[] }>(
    `/explore/timeseries/columns?project_id=${projectId}`
  );
}

export function runTimeseries(projectId: number, dateCol: string, valueCol: string) {
  return post<Record<string, unknown>>("/explore/timeseries/run", {
    project_id: projectId,
    date_col: dateCol,
    value_col: valueCol,
  });
}

// ── Explore: Duplicates ───────────────────────────────────────────────────────

export function getDuplicates(projectId: number) {
  return post<Record<string, unknown>>("/explore/duplicates", { project_id: projectId });
}

// ── Explore: Outliers ─────────────────────────────────────────────────────────

export function getOutlierColumns(projectId: number) {
  return get<{ numeric_columns: string[] }>(
    `/explore/outliers/columns?project_id=${projectId}`
  );
}

export function runOutlierAnalysis(projectId: number, column: string) {
  return post<Record<string, unknown>>("/explore/outliers/run", {
    project_id: projectId,
    column,
  });
}

// ── Explore: Correlations ─────────────────────────────────────────────────────

export function getCorrelations(projectId: number) {
  return post<Record<string, unknown>>("/explore/correlations", { project_id: projectId });
}

// ── Explore: Column Compare ───────────────────────────────────────────────────

export function getCompareColumnOptions(projectId: number) {
  return get<{ columns: string[] }>(
    `/explore/compare-columns/columns?project_id=${projectId}`
  );
}

export function runColumnCompare(projectId: number, colA: string, colB: string) {
  return post<Record<string, unknown>>("/explore/compare-columns/run", {
    project_id: projectId,
    col_a: colA,
    col_b: colB,
  });
}

// ── Explore: Multi-file Compare ───────────────────────────────────────────────

export function runMultifileCompare(projectIdA: number, projectIdB: number) {
  return post<Record<string, unknown>>("/explore/multifile", {
    project_id_a: projectIdA,
    project_id_b: projectIdB,
  });
}

// ── AutoML ────────────────────────────────────────────────────────────────────

export function getMlColumns(projectId: number) {
  return get<{ columns: string[] }>(`/ml/columns?project_id=${projectId}`);
}

export function trainModel(projectId: number, targetCol: string) {
  return post<Record<string, unknown>>("/ml/train", {
    project_id: projectId,
    target_col: targetCol,
  });
}

// ── AI Chat ───────────────────────────────────────────────────────────────────

export function sendChatMessage(
  projectId: number,
  message: string,
  history: { role: string; content: string }[]
) {
  return post<Record<string, unknown>>("/chat/query", {
    project_id: projectId,
    message,
    history,
  });
}

// ── Report Export ─────────────────────────────────────────────────────────────

export async function exportReport(projectId: number, format: "html" | "pdf" | "xlsx" = "html") {
  const token = await getFreshToken();
  const url = `${API_BASE_URL}/reports/export/${projectId}?format=${format}`;
  const hdrs = token ? { Authorization: `Bearer ${token}` } : {};
  // All formats: download via fetch so the Authorization header is sent
  const res = await fetch(url, { headers: hdrs });
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  const ext = format === "xlsx" ? "xlsx" : format === "pdf" ? "pdf" : "html";
  a.download = `analysis_report_${projectId}.${ext}`;
  a.click();
}

// ── Pivot ─────────────────────────────────────────────────────────────────────

export function getPivotColumns(projectId: number) {
  return get<{ all_columns: string[]; numeric_columns: string[] }>(
    `/pivot/columns?project_id=${projectId}`
  );
}

export function runPivot(
  projectId: number,
  rows: string[],
  cols: string[],
  values: string,
  aggfunc: string
) {
  return post<Record<string, unknown>>("/pivot/run", {
    project_id: projectId,
    rows,
    cols,
    values,
    aggfunc,
  });
}

// ── Cohorts ───────────────────────────────────────────────────────────────────

export function getCohortColumns(projectId: number) {
  return get<{ all_columns: string[]; numeric_columns: string[]; datetime_columns: string[] }>(
    `/cohorts/columns?project_id=${projectId}`
  );
}

export function runRfm(
  projectId: number,
  customerCol: string,
  dateCol: string,
  revenueCol: string
) {
  return post<Record<string, unknown>>("/cohorts/rfm", {
    project_id: projectId,
    customer_col: customerCol,
    date_col: dateCol,
    revenue_col: revenueCol,
  });
}

export function runRetention(
  projectId: number,
  cohortCol: string,
  periodCol: string,
  userCol: string
) {
  return post<Record<string, unknown>>("/cohorts/retention", {
    project_id: projectId,
    cohort_col: cohortCol,
    period_col: periodCol,
    user_col: userCol,
  });
}

// ── Statistical Tests ─────────────────────────────────────────────────────────

export function getStatsColumns(projectId: number) {
  return get<{ numeric_columns: string[]; categorical_columns: string[] }>(
    `/stats/columns?project_id=${projectId}`
  );
}

export function runStatsTest(
  projectId: number,
  testType: string,
  colA: string,
  colB?: string,
  alpha: number = 0.05
) {
  return post<Record<string, unknown>>("/stats/test", {
    project_id: projectId,
    test_type: testType,
    col_a: colA,
    col_b: colB ?? null,
    alpha,
  });
}

export function runPowerAnalysis(
  effectSize: number,
  alpha: number,
  power: number,
  testType: string = "ttest"
) {
  return post<Record<string, unknown>>("/stats/power", {
    effect_size: effectSize,
    alpha,
    power,
    test_type: testType,
  });
}

// ── SQL Engine ────────────────────────────────────────────────────────────────

export function getQuerySchema(projectId: number) {
  return get<{ columns: { name: string; dtype: string; sample_values: string[] }[]; table_name: string }>(
    `/query/schema?project_id=${projectId}`
  );
}

export function executeQuery(projectId: number, sql: string) {
  return post<Record<string, unknown>>("/query/execute", {
    project_id: projectId,
    sql,
  });
}

// ── Feature Engineering ───────────────────────────────────────────────────────

export function suggestFeatures(projectId: number) {
  return get<{ suggestions: { name: string; formula: string; rationale: string; category: string }[] }>(
    `/features/suggest?project_id=${projectId}`
  );
}

export function createFeature(projectId: number, name: string, formula: string) {
  return post<Record<string, unknown>>("/features/create", {
    project_id: projectId,
    name,
    formula,
  });
}

// ── Segments ──────────────────────────────────────────────────────────────────

export function getSegmentColumns(projectId: number) {
  return get<{ categorical_columns: string[]; numeric_columns: string[] }>(
    `/explore/segments/columns?project_id=${projectId}`
  );
}

export function runSegments(projectId: number, segmentCol: string, metricCol: string) {
  return post<Record<string, unknown>>("/explore/segments/run", {
    project_id: projectId,
    segment_col: segmentCol,
    metric_col: metricCol,
  });
}
