const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

async function post(path: string, body: object) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text() || `Request failed: ${path}`);
  return res.json();
}

export async function getProjects() {
  const res = await fetch(`${BASE}/projects`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch projects");
  return res.json();
}

export const createProject = (name: string) => post("/projects", { name });
export const runAnalysis = (project_id: number) => post("/analysis/run", { project_id });
export const getSuggestedChart = (project_id: number) => post("/charts/suggest", { project_id });

export async function uploadFile(projectId: number, file: File) {
  const form = new FormData();
  form.append("project_id", String(projectId));
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${await res.text()}`);
  return res.json();
}

// Explore
export const getTimeseriesColumns = (project_id: number) =>
  post("/explore/timeseries/columns", { project_id });
export const runTimeseries = (project_id: number, date_col: string, value_col: string) =>
  post("/explore/timeseries/run", { project_id, date_col, value_col });

export const getDuplicates = (project_id: number) =>
  post("/explore/duplicates", { project_id });

export const getOutlierColumns = (project_id: number) =>
  post("/explore/outliers/columns", { project_id });
export const runOutlierAnalysis = (project_id: number, column: string) =>
  post("/explore/outliers/run", { project_id, column });

export const getCorrelations = (project_id: number) =>
  post("/explore/correlations", { project_id });

export const getCompareColumns = (project_id: number) =>
  post("/explore/compare-columns/columns", { project_id });
export const runColumnCompare = (project_id: number, col_a: string, col_b: string) =>
  post("/explore/compare-columns/run", { project_id, col_a, col_b });

export const runMultifileCompare = (project_id_a: number, project_id_b: number) =>
  post("/explore/multifile", { project_id_a, project_id_b });
