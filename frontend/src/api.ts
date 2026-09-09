const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (e) {
    throw new ApiError(
      "Cannot reach the API. Is the backend running?",
      0,
    );
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail =
      (body && (body.detail || body.error)) || `Request failed (${res.status})`;
    throw new ApiError(
      typeof detail === "string" ? detail : JSON.stringify(detail),
      res.status,
    );
  }
  return body as T;
}

export const api = {
  meta: () => request<any>("/meta"),
  ready: () => request<any>("/ready"),
  dashboard: (refresh = false) =>
    request<any>(`/dashboard/summary${refresh ? "?refresh=true" : ""}`),

  catalog: () => request<any>("/workspace/catalog"),
  runQuery: (payload: { sql?: string; query_id?: string; explain?: boolean }) =>
    request<any>("/workspace/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  scenarios: () => request<any>("/performance/scenarios"),
  benchmark: (id: string) =>
    request<any>(`/performance/scenarios/${id}/benchmark`, { method: "POST" }),
  scalingBenchmark: () =>
    request<any>("/performance/scaling-benchmark", { method: "POST" }),

  customerAnalyses: () => request<any>("/customers/analyses"),
  customerAnalysis: (key: string) => request<any>(`/customers/${key}`),

  aiExamples: () => request<any>("/ai/examples"),
  ask: (question: string, execute = true) =>
    request<any>("/ai/ask", {
      method: "POST",
      body: JSON.stringify({ question, execute }),
    }),

  dataQuality: () => request<any>("/data-quality/checks"),
  recommendations: () => request<any>("/recommendations"),
};
