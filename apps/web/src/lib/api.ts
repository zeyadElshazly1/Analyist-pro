const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `GET ${path} failed: ${res.status}`);
  }
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `POST ${path} failed: ${res.status}`);
  }
  return res.json();
}

// ── Projects ──────────────────────────────────────────────────────────────────

export function getProjects() {
  return get<{ id: number; name: string; status?: string }[]>("/projects");
}

export function createProject(name: string) {
  return post<{ id: number; name: string }>("/projects", { name });
}

// ── Upload ────────────────────────────────────────────────────────────────────

export async function uploadFile(projectId: number, file: File) {
  const formData = new FormData();
  formData.append("project_id", String(projectId));
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/upload`, {
    method: "POST",
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
