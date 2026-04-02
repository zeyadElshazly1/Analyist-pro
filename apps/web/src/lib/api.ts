const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export type ProjectIntent =
  | "marketing"
  | "saas"
  | "sales"
  | "finance"
  | "operations"
  | "general";

export type ProjectSummary = {
  id: number;
  name: string;
  status: string;
  intent?: ProjectIntent;
  latest_dataset_id?: number | null;
  latest_job_id?: number | null;
};

export type DatasetRecord = {
  id: number;
  project_id: number;
  filename: string;
  storage_path: string;
  file_size: number;
  file_hash: string;
  status: string;
  rows_count?: number | null;
  columns_count?: number | null;
  uploaded_at: string;
  updated_at: string;
};

export type AnalysisArtifactPayload = {
  dataset_summary: {
    rows: number;
    columns: number;
    numeric_cols: number;
    categorical_cols: number;
    datetime_cols?: number;
    missing_pct: number;
  };
  cleaning_summary: Record<string, unknown>;
  cleaning_report: Array<Record<string, unknown>>;
  health_score: Record<string, unknown>;
  profile: Record<string, unknown>;
  insights: Array<Record<string, unknown>>;
  narrative: string;
  analysis_version: string;
};

export type AnalysisArtifact = {
  id: number;
  kind: string;
  version: string;
  created_at: string;
  payload: AnalysisArtifactPayload;
};

export type AnalysisJob = {
  id: number;
  project_id: number;
  dataset_id: number;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  stage: string;
  analysis_version: string;
  error_message?: string | null;
  result_artifact?: AnalysisArtifact | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type ProjectDetail = ProjectSummary & {
  latest_dataset?: DatasetRecord | null;
  latest_job?: AnalysisJob | null;
  latest_analysis?: AnalysisArtifact | null;
};

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

export function getProjects() {
  return get<ProjectSummary[]>("/projects");
}

export function getProject(projectId: number) {
  return get<ProjectDetail>(`/projects/${projectId}`);
}

export function createProject(name: string, intent: ProjectIntent = "general") {
  return post<ProjectSummary>("/projects", { name, intent });
}

export async function uploadFile(projectId: number, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/projects/${projectId}/datasets`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json() as Promise<DatasetRecord>;
}

export function startAnalysis(datasetId: number) {
  return post<AnalysisJob>(`/datasets/${datasetId}/analyze`);
}

export function getAnalysisJob(jobId: number) {
  return get<AnalysisJob>(`/analysis-jobs/${jobId}`);
}

export function getLatestAnalysis(projectId: number) {
  return get<AnalysisArtifactPayload>(`/analysis/latest/${projectId}`);
}

export function runAnalysis(projectId: number) {
  return post<AnalysisJob>("/analysis/run", { project_id: projectId });
}

export function getSuggestedCharts(projectId: number) {
  return post<{ charts: unknown[] }>("/charts/suggest", { project_id: projectId });
}

export function getSuggestedChart(projectId: number) {
  return getSuggestedCharts(projectId);
}

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

export function getDuplicates(projectId: number) {
  return post<Record<string, unknown>>("/explore/duplicates", { project_id: projectId });
}

export function getOutlierColumns(projectId: number) {
  return get<{ numeric_columns: string[] }>(`/explore/outliers/columns?project_id=${projectId}`);
}

export function runOutlierAnalysis(projectId: number, column: string) {
  return post<Record<string, unknown>>("/explore/outliers/run", {
    project_id: projectId,
    column,
  });
}

export function getCorrelations(projectId: number) {
  return post<Record<string, unknown>>("/explore/correlations", { project_id: projectId });
}

export function getCompareColumnOptions(projectId: number) {
  return get<{ columns: string[] }>(`/explore/compare-columns/columns?project_id=${projectId}`);
}

export function runColumnCompare(projectId: number, colA: string, colB: string) {
  return post<Record<string, unknown>>("/explore/compare-columns/run", {
    project_id: projectId,
    col_a: colA,
    col_b: colB,
  });
}

export function runMultifileCompare(projectIdA: number, projectIdB: number) {
  return post<Record<string, unknown>>("/explore/multifile", {
    project_id_a: projectIdA,
    project_id_b: projectIdB,
  });
}

export function getMlColumns(projectId: number) {
  return get<{ columns: string[] }>(`/ml/columns?project_id=${projectId}`);
}

export function trainModel(projectId: number, targetCol: string) {
  return post<Record<string, unknown>>("/ml/train", {
    project_id: projectId,
    target_col: targetCol,
  });
}

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

export function exportReport(projectId: number, format: "html" | "pdf" = "html") {
  const url = `${API_BASE_URL}/reports/export/${projectId}?format=${format}`;
  window.open(url, "_blank");
}

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
