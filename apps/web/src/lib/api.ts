import { supabase } from "./supabase";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

// ── Structured API error ──────────────────────────────────────────────────────

/**
 * Every failed API call throws an ApiError instead of a raw Error.
 * This lets callers inspect error.code and error.status to show
 * appropriate UI (401 → redirect to login, 503 → "try again", etc.).
 */
export class ApiError extends Error {
  constructor(
    /** User-friendly message — safe to display directly */
    public readonly userMessage: string,
    /** Machine-readable code from the backend (e.g. "NOT_FOUND") */
    public readonly code: string,
    /** HTTP status code */
    public readonly status: number,
    /** Request ID for cross-referencing server logs */
    public readonly requestId?: string,
    /** Validation field errors (status 422 only) */
    public readonly fields?: Record<string, string>,
  ) {
    super(userMessage);
    this.name = "ApiError";
  }

  get isAuthError()        { return this.status === 401; }
  get isForbidden()        { return this.status === 403; }
  get isNotFound()         { return this.status === 404; }
  get isPaymentRequired()  { return this.status === 402; }
  get isValidation()       { return this.status === 422; }
  get isServer()           { return this.status >= 500; }
  get isNetwork()          { return this.status === 0; }
  get isRetryable()        { return this.status === 503 || this.status === 504 || this.status === 429; }

  /** For 402 responses the backend sends a structured detail object. */
  get upgradeInfo(): { message: string; feature: string; current_plan: string } | null {
    if (this.status !== 402) return null;
    try {
      // userMessage may be the raw JSON string of the detail object
      const parsed = typeof this.userMessage === "string"
        ? JSON.parse(this.userMessage)
        : this.userMessage;
      if (parsed && parsed.feature) return parsed as { message: string; feature: string; current_plan: string };
    } catch { /* not JSON */ }
    return null;
  }
}

/**
 * Parse a failed Response into a structured ApiError.
 * Handles both our backend's JSON error format and raw text errors.
 */
async function parseError(res: Response, context: string): Promise<ApiError> {
  let body: Record<string, unknown> = {};
  const requestId = res.headers.get("X-Request-ID") ?? undefined;

  try {
    const text = await res.text();
    if (text) body = JSON.parse(text);
  } catch {
    // Non-JSON response body — use a generic message
  }

  const code = String(body.code ?? "UNKNOWN_ERROR");
  const fields = body.fields as Record<string, string> | undefined;

  // 402: detail is a structured object — preserve it as the userMessage so
  // upgradeInfo getter can parse it
  let userMessage: string;
  if (res.status === 402 && body.detail && typeof body.detail === "object") {
    userMessage = JSON.stringify(body.detail);
  } else {
    userMessage = String(body.error ?? body.detail ?? "");
    if (!userMessage) userMessage = statusToMessage(res.status, context);
  }

  return new ApiError(userMessage, code, res.status, requestId, fields);
}

function statusToMessage(status: number, context: string): string {
  switch (status) {
    case 400: return `Invalid request. Please check your input.`;
    case 401: return `Your session has expired. Please sign in again.`;
    case 403: return `You don't have permission to perform this action.`;
    case 404: return `${context} not found.`;
    case 409: return `A conflict occurred. The resource may already exist.`;
    case 413: return `The file is too large to upload.`;
    case 415: return `This file type is not supported.`;
    case 422: return `The request data is invalid. Please check your input.`;
    case 429: return `Too many requests. Please wait a moment and try again.`;
    case 503: return `The service is temporarily unavailable. Please try again in a moment.`;
    case 504: return `The request timed out. Please try again.`;
    default:  return `An unexpected error occurred (${status}). Please try again.`;
  }
}

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
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      headers: await authHeaders(),
    });
  } catch (e) {
    // Network-level failure (offline, DNS, CORS, etc.)
    throw new ApiError(
      "Could not reach the server. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }

  if (res.status === 401) {
    // Token expired — clear stale credentials and let the caller handle redirect
    clearToken();
  }

  if (!res.ok) {
    throw await parseError(res, path.split("/").filter(Boolean).pop() ?? "Resource");
  }

  try {
    return await res.json();
  } catch {
    throw new ApiError(
      "The server returned an unexpected response format.",
      "PARSE_ERROR",
      res.status,
    );
  }
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await authHeaders()) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(
      "Could not reach the server. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }

  if (res.status === 401) {
    clearToken();
  }

  if (!res.ok) {
    throw await parseError(res, path.split("/").filter(Boolean).pop() ?? "Resource");
  }

  try {
    return await res.json();
  } catch {
    throw new ApiError(
      "The server returned an unexpected response format.",
      "PARSE_ERROR",
      res.status,
    );
  }
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...(await authHeaders()) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(
      "Could not reach the server. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }
  if (res.status === 401) clearToken();
  if (!res.ok) {
    throw await parseError(res, path.split("/").filter(Boolean).pop() ?? "Resource");
  }
  try {
    return await res.json();
  } catch {
    throw new ApiError("The server returned an unexpected response format.", "PARSE_ERROR", res.status);
  }
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

/** GDPR: permanently delete the current user's account and all data. */
export async function deleteMyAccount(): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/auth/me`, {
      method: "DELETE",
      headers: await authHeaders(),
    });
  } catch {
    throw new ApiError(
      "Could not reach the server. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }
  if (res.status === 401) clearToken();
  if (!res.ok) throw await parseError(res, "Account");
}

/** GDPR: download a full JSON export of the current user's data. */
export async function exportMyData(): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/auth/me/export`, {
      headers: await authHeaders(),
    });
  } catch {
    throw new ApiError(
      "Could not reach the server. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }
  if (res.status === 401) clearToken();
  if (!res.ok) throw await parseError(res, "Export");

  // Trigger browser download
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "analyistpro-data-export.json";
  a.click();
  URL.revokeObjectURL(url);
}

// ── Projects ──────────────────────────────────────────────────────────────────

export function getProjects() {
  return get<{ id: number; name: string; status: string; created_at?: string }[]>("/projects");
}

export function getProject(projectId: number) {
  return get<{ id: number; name: string; status: string; created_at: string }>(`/projects/${projectId}`);
}

export function getAnnotations(projectId: number) {
  return get<{ annotations: Record<string, string> }>(`/projects/${projectId}/annotations`);
}

export function setAnnotation(projectId: number, column: string, note: string) {
  return put<{ annotations: Record<string, string> }>(
    `/projects/${projectId}/annotations/${encodeURIComponent(column)}`,
    { note },
  );
}

export function createProject(name: string) {
  return post<{ id: number; name: string }>("/projects", { name });
}

export async function deleteProject(projectId: number) {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    });
  } catch {
    throw new ApiError(
      "Could not reach the server. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }
  if (res.status === 401) clearToken();
  if (!res.ok) throw await parseError(res, "Project");
}

export function getProjectsWithLatestRun() {
  return get<{
    id: number;
    name: string;
    status: string;
    created_at: string;
    latest_run_at: string | null;
    latest_run_id: number | null;
  }[]>("/projects/with-latest-run");
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
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/upload`, {
      method: "POST",
      headers: await authHeaders(),
      body: formData,
    });
  } catch {
    throw new ApiError(
      "Could not reach the server. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }
  if (res.status === 401) clearToken();
  if (!res.ok) throw await parseError(res, "Upload");
  try {
    return await res.json();
  } catch {
    throw new ApiError("The server returned an unexpected response format.", "PARSE_ERROR", res.status);
  }
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

export type ColumnFilterOp =
  | "eq" | "neq" | "contains"
  | "gt" | "gte" | "lt" | "lte"
  | "is_null" | "not_null";

export interface ColumnFilter {
  col: string;
  op: ColumnFilterOp;
  value: string;
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
  active_filters: ColumnFilter[];
}

export function getDataTable(
  projectId: number,
  opts: {
    page?: number;
    perPage?: number;
    sortCol?: string;
    sortDir?: "asc" | "desc";
    search?: string;
    columnFilters?: ColumnFilter[];
  } = {}
) {
  const params = new URLSearchParams();
  params.set("project_id", String(projectId));
  if (opts.page) params.set("page", String(opts.page));
  if (opts.perPage) params.set("per_page", String(opts.perPage));
  if (opts.sortCol) params.set("sort_col", opts.sortCol);
  if (opts.sortDir) params.set("sort_dir", opts.sortDir);
  if (opts.search) params.set("search", opts.search);
  if (opts.columnFilters && opts.columnFilters.length > 0) {
    params.set("column_filters", JSON.stringify(opts.columnFilters));
  }
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

// ── Explore: Join ─────────────────────────────────────────────────────────────

export function getJoinColumns(projectIdLeft: number, projectIdRight: number) {
  return get<{
    left_columns: string[];
    right_columns: string[];
    suggested_join_keys: string[];
  }>(`/explore/join/columns?project_id_left=${projectIdLeft}&project_id_right=${projectIdRight}`);
}

export function runJoin(
  projectIdLeft: number,
  projectIdRight: number,
  leftOn: string,
  rightOn: string,
  how: "inner" | "left" | "right" | "outer",
) {
  return post<{
    rows: number;
    left_rows: number;
    right_rows: number;
    columns: string[];
    how: string;
    left_on: string;
    right_on: string;
    preview: Record<string, string>[];
  }>("/explore/join/run", {
    project_id_left: projectIdLeft,
    project_id_right: projectIdRight,
    left_on: leftOn,
    right_on: rightOn,
    how,
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
  const hdrs: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  let res: Response;
  try {
    res = await fetch(url, { headers: hdrs });
  } catch {
    throw new ApiError(
      "Could not reach the server to export the report. Please check your connection.",
      "NETWORK_ERROR",
      0,
    );
  }

  if (!res.ok) {
    throw await parseError(res, "Report");
  }

  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  const ext = format === "xlsx" ? "xlsx" : format === "pdf" ? "pdf" : "html";
  a.download = `analysis_report_${projectId}.${ext}`;
  a.click();
  // Clean up object URL after a short delay
  setTimeout(() => URL.revokeObjectURL(a.href), 60_000);
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

// ── Analysis diff ─────────────────────────────────────────────────────────────

export interface DiffMetric {
  name: string;
  a: number | null;
  b: number | null;
  delta: number;
  direction: "up" | "down" | "unchanged";
}

export interface AnalysisDiff {
  run_a: { id: number; created_at: string | null; file_hash: string | null };
  run_b: { id: number; created_at: string | null; file_hash: string | null };
  same_file: boolean;
  metrics: DiffMetric[];
  insights: {
    new: Record<string, unknown>[];
    resolved: Record<string, unknown>[];
    unchanged_count: number;
  };
  columns: {
    added: Record<string, unknown>[];
    removed: Record<string, unknown>[];
    changed: { name: string; changes: Record<string, { a: unknown; b: unknown }> }[];
  };
}

export function getAnalysisDiff(runA: number, runB: number) {
  return get<AnalysisDiff>(`/analysis/diff?run_a=${runA}&run_b=${runB}`);
}

export function createCheckoutSession(plan: "pro" | "team"): Promise<{ checkout_url: string }> {
  return post<{ checkout_url: string }>("/billing/create-checkout-session", { plan });
}

export function getModelInfo(projectId: number) {
  return get<{
    project_id: number;
    problem_type: string;
    target_col: string;
    best_model_name: string;
    feature_names: string[];
    class_labels: string[] | null;
  }>(`/ml/model-info/${projectId}`);
}

export function predictRows(
  projectId: number,
  rows: Record<string, unknown>[],
): Promise<{
  problem_type: string;
  target_col: string;
  best_model_name: string;
  predictions: { prediction: unknown; confidence?: number }[];
}> {
  return post(`/ml/predict/${projectId}`, { rows });
}
