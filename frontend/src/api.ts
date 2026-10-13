export type Status = "match" | "partial" | "unconfirmed" | "mismatch" | "review" | "na";

export interface DocumentInfo {
  id: number;
  filename: string;
  page_count: number;
  doc_type: string | null;
  status: string;
  error: string | null;
  info: Record<string, unknown>;
}

export interface Package {
  id: number;
  kind: "customer" | "bid";
  participant_name: string | null;
  status: string;
  error: string | null;
  created_at: string;
  documents: DocumentInfo[];
}

export interface Score {
  total?: number | null;
  total_min?: number | null;
  total_max?: number | null;
  product?: number | null;
  participant?: number | null;
  categories?: Record<string, number | null>;
  mandatory_done?: number;
  mandatory_total?: number;
  counts?: Record<Status, number>;
  problems?: number;
  verdict?: "ready" | "needs_work" | "rejection_risk";
  verdict_label?: string;
  forecast?: number | null;
  points?: Points | null;
  points_forecast?: number | null;
  warnings?: string[];
}

/** Evaluation points: unresolved items give a range; `passed` is null while undecided. */
export interface Points {
  min: number;
  max: number;
  total: number;
  pass: number | null;
  passed: boolean | null;
}

export interface Run {
  id: number;
  package_id: number;
  status: "queued" | "running" | "done" | "failed";
  stage: string | null;
  error: string | null;
  score: Score;
  created_at: string;
  finished_at: string | null;
  summary?: string | null;
}

export interface Project {
  id: number;
  title: string;
  customer_name: string | null;
  lot_number: string | null;
  submission_deadline: string | null;
  report_language: "ru" | "uz" | "en";
  status: "new" | "extracting" | "extracted" | "failed";
  error: string | null;
  checklist_approved: boolean;
  lot_positions: { number: number; name: string; quantity: string | null; unit: string | null }[];
  min_pass_score: number | null;
  created_at: string;
  packages: Package[];
  runs: Run[];
}

export interface ProjectListItem {
  id: number;
  title: string;
  customer_name: string | null;
  lot_number: string | null;
  submission_deadline: string | null;
  status: string;
  checklist_approved: boolean;
  created_at: string;
  score: number | null;
  verdict: Score["verdict"] | null;
}

export interface Source {
  document_id: number;
  filename: string;
  page: number | null;
  quote: string | null;
  verified: boolean | null;
}

export interface Requirement {
  id: number;
  code: string;
  scope: "product" | "participant";
  category: "technical" | "documents" | "qualification" | "commercial";
  lot_position: number | null;
  parameter: string;
  parameter_key: string;
  operator: string;
  value: string | null;
  unit: string | null;
  req_type: "mandatory" | "rated" | "desired";
  rated_points: number | null;
  proof_documents: string[];
  consequence: string;
  equivalent_allowed: boolean;
  note: string | null;
  sources: Source[];
  origin: "ai" | "user";
}

export interface Issue {
  id: number;
  kind: "contradiction" | "ambiguity" | "restrictive";
  description: string;
  sources: Source[];
}

export interface Evidence extends Source {
  doc_type: string | null;
  value: string;
}

export interface Match {
  id: number;
  status: Status;
  ai_status: Status;
  method: "rule" | "llm" | "manual";
  reasoning: string;
  evidence: Evidence[];
  comment: string | null;
  points: number | null;
  requirement: Requirement;
}

export interface Recommendation {
  id: number;
  requirement_id: number;
  code: string;
  parameter: string;
  problem: string;
  action: string;
  action_type: string;
  severity: "high" | "medium" | "low";
  impact: number;
  done: boolean;
}

export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { "Content-Type": "application/json" };
  }
  const res = await fetch(`/api/v1${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* keep status text */
    }
    throw new ApiError(detail);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: (path: string) => request<void>("DELETE", path),
};

export const documentUrl = (source: { document_id: number; page: number | null }) =>
  `/api/v1/documents/${source.document_id}/file${source.page ? `#page=${source.page}` : ""}`;
