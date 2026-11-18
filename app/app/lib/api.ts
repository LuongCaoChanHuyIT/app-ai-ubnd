export interface HelloPayload {
  message: string;
  service: string;
  version: string;
  timestamp: string;
}

export type HelloResult =
  | {
      connected: true;
      data: HelloPayload;
      latencyMs: number;
    }
  | {
      connected: false;
      error: string;
      latencyMs: number;
    };

export type DepartmentId = "VP" | "KT" | "VHXH" | "NNMT";
export type AssistantMode = "soan_thao" | "nghiep_vu" | "tham_dinh";
export type DocTier = "trung_uong" | "dia_phuong" | "kho_rieng";
export type SessionProcessAction = "tom_tat" | "trich_xuat" | "doi_chieu" | "tong_hop";
export type TaskStatus = "cho_xu_ly" | "dang_thuc_hien" | "sap_den_han" | "hoan_thanh";

export interface Department {
  id: DepartmentId;
  code: string;
  name: string;
  scope_summary: string;
  instruction: string;
  updated_at: string;
}

export interface CitationItem {
  doc_number: string;
  title: string;
  tier: DocTier | string;
}

export interface SessionFileItem {
  file_id: string;
  filename: string;
  size_bytes: number;
  ext: string;
  extracted_text: string;
  parse_note: string;
  uploaded_at: string;
}

export interface SessionMessageItem {
  role: "user" | "assistant";
  mode: AssistantMode | string;
  content: string;
  citations: CitationItem[];
  created_at: string;
}

export interface SessionState {
  session_id: string;
  created_at: string;
  files: SessionFileItem[];
  messages: SessionMessageItem[];
}

export interface ChatTurnResponse {
  session_id: string;
  department: Department;
  reply: SessionMessageItem;
  session: SessionState;
}

export interface ExtendedOption {
  code: string;
  title: string;
  summary: string;
  pros: string[];
  cons: string[];
  feasibility: string;
}

export interface ExtendedAnalyzeResponse {
  department: Department;
  topic: string;
  context: string;
  scope_notice: string;
  options: ExtendedOption[];
}

export interface AuditCriterion {
  id: string;
  name: string;
  status: "dat" | "can_ra_soat" | "khong_dat";
  detail: string;
}

export interface AuditReport {
  score: number;
  doc_type: string;
  department_id: DepartmentId;
  criteria: AuditCriterion[];
  summary: string;
}

export interface OfficialDoc {
  id: number;
  doc_number: string;
  title: string;
  doc_type: string;
  tier: DocTier;
  department_id: string;
  issuer: string;
  issued_date: string;
  status: string;
  summary: string;
  content: string;
  created_at: string;
}

export interface DocUpdateRequest {
  id: number;
  doc_number: string;
  title: string;
  tier: DocTier;
  department_id: DepartmentId;
  reason: string;
  requested_by: string;
  status: string;
  created_at: string;
}

export interface SessionProcessResult {
  action: SessionProcessAction;
  file_count: number;
  result_markdown: string;
  highlights: string[];
}

export interface TaskItem {
  id: number;
  title: string;
  description: string;
  department_id: DepartmentId;
  assignee: string;
  due_date: string;
  priority: "thap" | "trung_binh" | "cao" | "khan";
  status: TaskStatus;
  progress: number;
  ref_doc_number: string;
  reminder_count: number;
  created_at: string;
  updated_at: string;
}

export interface TasksOverview {
  kpis: {
    total: number;
    in_progress: number;
    due_soon: number;
    completed: number;
  };
  tasks: TaskItem[];
}

export interface RbacUser {
  id: number;
  email: string;
  full_name: string;
  position: string;
  role: "owner" | "officer";
  department_id: DepartmentId;
  private_repo_access: boolean;
  active: boolean;
  created_at: string;
}

export interface ApiConnector {
  id: number;
  name: string;
  provider: string;
  base_url: string;
  model_name: string;
  has_key: boolean;
  api_key_masked: string;
  active: boolean;
  updated_at: string;
}

export interface AuditLogEntry {
  id: number;
  actor_email: string;
  department_id: string;
  module_code: string;
  action: string;
  detail: string;
  created_at: string;
}

export interface ClonedTenant {
  id: number;
  slug: string;
  commune_name: string;
  admin_email: string;
  db_path: string;
  created_at: string;
}

export const LEGAL_DISCLAIMER_TEXT =
  "AI là công cụ hỗ trợ nghiệp vụ; cán bộ, công chức và người có thẩm quyền vẫn trực tiếp kiểm tra, quyết định và chịu trách nhiệm đối với nội dung sử dụng.";

export function resolveServerApiBase(): string {
  if (typeof process !== "undefined" && process.env?.API_BASE_URL) {
    return process.env.API_BASE_URL.replace(/\/+$/, "");
  }
  return "http://127.0.0.1:8000";
}

export function normalizeDepartmentId(raw: string | null | undefined): DepartmentId {
  const upper = (raw ?? "VP").toUpperCase();
  if (upper === "KT" || upper === "VHXH" || upper === "NNMT") {
    return upper;
  }
  return "VP";
}

export async function apiRequest<T>(
  path: string,
  options?: {
    method?: string;
    body?: unknown;
    baseUrl?: string;
    actorEmail?: string;
  },
): Promise<T> {
  const baseUrl = (options?.baseUrl ?? "").replace(/\/+$/, "");
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (options?.actorEmail) {
    headers["X-Actor-Email"] = options.actorEmail;
  }
  if (options?.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method: options?.method ?? "GET",
    headers,
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = (await response.json()) as { detail?: string };
      if (errJson?.detail) {
        detail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function uploadSessionFile(
  sessionId: string,
  file: File,
  departmentId: DepartmentId = "VP",
  actorEmail = "tsh.co@tshorg.vn",
): Promise<SessionState> {
  const form = new FormData();
  form.append("file", file);

  const response = await fetch(
    `/api/m05/sessions/${encodeURIComponent(sessionId)}/upload?department_id=${encodeURIComponent(departmentId)}`,
    {
      method: "POST",
      headers: {
        "X-Actor-Email": actorEmail,
      },
      body: form,
    },
  );

  if (!response.ok) {
    let detail = `Lỗi tải tệp (HTTP ${response.status})`;
    try {
      const errJson = (await response.json()) as { detail?: string };
      if (errJson?.detail) {
        detail = errJson.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return (await response.json()) as SessionState;
}

export async function fetchBackendHello(options?: {
  baseUrl?: string;
  name?: string;
}): Promise<HelloResult> {
  const baseUrl = (options?.baseUrl ?? "").replace(/\/+$/, "");
  const query = options?.name?.trim()
    ? `?name=${encodeURIComponent(options.name.trim())}`
    : "";
  const endpoint = `${baseUrl}/api/hello${query}`;
  const startedAt = performance.now();

  try {
    const response = await fetch(endpoint, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(4000),
    });
    const latencyMs = Math.round(performance.now() - startedAt);

    if (!response.ok) {
      return {
        connected: false,
        error: `HTTP ${response.status} ${response.statusText}`,
        latencyMs,
      };
    }

    const data = (await response.json()) as HelloPayload;
    return {
      connected: true,
      data,
      latencyMs,
    };
  } catch (err) {
    const latencyMs = Math.round(performance.now() - startedAt);
    return {
      connected: false,
      error: err instanceof Error ? err.message : "Không thể kết nối tới Backend",
      latencyMs,
    };
  }
}
