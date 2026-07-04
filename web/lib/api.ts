// API client for the M.A.R.S FastAPI backend

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://mars-api-c0kv.onrender.com";

export interface ResearchResult {
  query: string;
  final_report: string;
  papers_indexed: number;
  graph_nodes: number;
  hypotheses_count: number;
  debate_transcript: string;
  experiments_run: number;
  successful_discoveries: number;
  research_gaps: string[];
  twin_hypothesis: string;
  twin_persona: string;
  loop_iterations: number;
  latency_sec: number;
  benchmarks: Record<string, number>;
}

export interface Metrics {
  papers_indexed: number;
  graph_nodes: number;
  hypotheses_generated: number;
  experiments_run: number;
  successful_discoveries: number;
  arena_scored: number;
  cross_paper_combinations: number;
  [k: string]: number;
}

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export const api = {
  health: () => req<{ status: string; version: string }>("/health"),

  metrics: () => req<Metrics>("/metrics"),

  research: (body: {
    query: string;
    run_experiments?: boolean;
    twin_persona?: string;
    domain?: string;
  }) =>
    req<ResearchResult>("/research", {
      method: "POST",
      body: JSON.stringify({
        run_experiments: true,
        twin_persona: "Andrej Karpathy",
        ...body,
      }),
    }),

  memory: () =>
    req<{ total: number; entries: any[]; successful: number; failed: number }>(
      "/memory"
    ),

  graphNetwork: (maxNodes = 120) =>
    req<{ nodes: any[]; edges: any[] }>(`/graph/network?max_nodes=${maxNodes}`),

  graphGaps: () => req<{ gaps: any[] }>("/graph/gaps"),

  experiments: () =>
    req<{ experiments: any[]; count: number }>("/experiments"),

  arena: (topN = 30) =>
    req<{ entries: any[]; stats: Record<string, number> }>(
      `/arena?top_n=${topN}`
    ),
};

export const API_BASE = API_URL;
