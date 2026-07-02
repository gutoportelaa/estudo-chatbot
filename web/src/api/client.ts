const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_STORAGE_KEY = "thinkai.jwt";

export interface AuthUser {
  id: string;
  username: string;
  created_at: string;
}

export interface SessionSummary {
  id: string;
  title?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

interface ApiErrorPayload {
  detail?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  status: number;
  payload?: ApiErrorPayload;

  constructor(status: number, message: string, payload?: ApiErrorPayload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function readToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function getAuthToken(): string | null {
  return readToken();
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function logout(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function readErrorPayload(res: Response): Promise<ApiErrorPayload | undefined> {
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) return undefined;
  try {
    return (await res.json()) as ApiErrorPayload;
  } catch {
    return undefined;
  }
}

async function req<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers);
  const token = auth ? readToken() : null;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  // FormData (upload) precisa que o browser defina o boundary — só forçamos
  // JSON para corpos string.
  if (typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    const payload = await readErrorPayload(res);
    if (res.status === 401) logout();
    throw new ApiError(res.status, payload?.detail ?? `Erro ${res.status}`, payload);
  }

  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) return undefined as T;
  return (await res.json()) as T;
}

// ---------- Auth ----------

export async function signup(username: string, password: string): Promise<AuthUser> {
  return req<AuthUser>("/auth/signup", { method: "POST", body: JSON.stringify({ username, password }) }, false);
}

export async function signin(username: string, password: string): Promise<string> {
  const data = await req<{ access_token: string }>(
    "/auth/signin",
    { method: "POST", body: JSON.stringify({ username, password }) },
    false,
  );
  setAuthToken(data.access_token);
  return data.access_token;
}

export async function getProfile(): Promise<AuthUser> {
  return req<AuthUser>("/auth/profile");
}

// ---------- Consumo (métricas de tokens/custo) ----------

export interface UsageTotals {
  requests: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  avg_latency_ms: number;
}

export interface UsageByDay {
  date: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface UsageByModel {
  model: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface UsageSummary {
  days: number;
  totals: UsageTotals;
  by_day: UsageByDay[];
  by_model: UsageByModel[];
}

export async function getUsage(days = 30): Promise<UsageSummary> {
  return req<UsageSummary>(`/metrics/usage?days=${days}`);
}

// ---------- Sumarização do histórico (log de compactações) ----------

export interface SummaryEvent {
  id: string;
  covered_message_count: number;
  source_message_count: number;
  summary_tokens: number;
  trigger: string; // "window_overflow" | "recompaction"
  model: string;
  created_at: string;
}

export async function getSummaries(sessionId: string): Promise<SummaryEvent[]> {
  return req<SummaryEvent[]>(`/sessions/${sessionId}/summaries`);
}

// ---------- Health ----------

function formatProviderLabel(provider: string, model: string): string {
  const providerLabel =
    provider === "openrouter" ? "OpenRouter" : provider.charAt(0).toUpperCase() + provider.slice(1);
  const modelLabel = model
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
  return `${providerLabel} · ${modelLabel}`;
}

export async function fetchModelName(): Promise<string> {
  try {
    const data = await req<{ provider: string; model: string }>("/health", {}, false);
    if (!data.model) return "";
    return formatProviderLabel(data.provider ?? "", data.model);
  } catch {
    return "";
  }
}

// ---------- Sessions ----------

export async function listSessions(): Promise<SessionSummary[]> {
  const data = await req<unknown>("/sessions");
  if (Array.isArray(data)) return data as SessionSummary[];
  return [];
}

export async function createSession(documentIds: string[] = []): Promise<string> {
  const data = await req<{ id: string }>("/sessions", {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
  return data.id;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await req<void>(`/sessions/${sessionId}`, { method: "DELETE" });
}

export async function getSessionDocuments(sessionId: string): Promise<string[]> {
  const data = await req<{ document_ids: string[] }>(`/sessions/${sessionId}/documents`);
  return data.document_ids ?? [];
}

export async function attachDocuments(sessionId: string, documentIds: string[]): Promise<string[]> {
  const data = await req<{ document_ids: string[] }>(`/sessions/${sessionId}/documents`, {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
  return data.document_ids ?? [];
}

export async function renameSession(sessionId: string, title: string): Promise<SessionSummary> {
  return req<SessionSummary>(`/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

// ---------- Biblioteca (documentos) ----------

export interface DocumentItem {
  id: string;
  filename: string;
  size_bytes: number;
  page_count: number | null;
  extraction_status: "pending" | "done" | "failed";
  has_thumbnail: boolean;
  created_at: string;
}

export type DocumentSort = "recent" | "oldest" | "name" | "size";

export async function listDocuments(sort: DocumentSort = "recent"): Promise<DocumentItem[]> {
  const data = await req<unknown>(`/documents?sort=${sort}`);
  return Array.isArray(data) ? (data as DocumentItem[]) : [];
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  return req<DocumentItem>("/documents", { method: "POST", body: form });
}

export async function extractDocument(id: string): Promise<unknown> {
  return req<unknown>(`/documents/${id}/extract`, { method: "POST" });
}

export async function indexDocument(id: string): Promise<{ chunks_indexed: number }> {
  return req<{ chunks_indexed: number }>(`/documents/${id}/index`, { method: "POST" });
}

export async function deleteDocument(id: string): Promise<void> {
  await req<void>(`/documents/${id}`, { method: "DELETE" });
}

/** Baixa a capa autenticada e devolve um object URL (o <img> não envia header). */
export async function fetchThumbnail(id: string): Promise<string> {
  const token = readToken();
  const res = await fetch(`${API_URL}/documents/${id}/thumbnail`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, `Erro ${res.status}`);
  return URL.createObjectURL(await res.blob());
}

// ---------- Messages ----------

export async function fetchMessages(sessionId: string): Promise<ChatMessage[]> {
  try {
    const data = await req<unknown>(`/sessions/${sessionId}/messages`);
    if (Array.isArray(data)) return data as ChatMessage[];
    return [];
  } catch {
    return [];
  }
}

export async function sendMessage(
  sessionId: string,
  content: string,
  onToken: (chunk: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = readToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers,
    body: JSON.stringify({ content }),
    signal,
  });

  if (!res.ok || !res.body) throw new ApiError(res.status, "Falha ao enviar mensagem");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") return;
      try {
        const parsed = JSON.parse(payload) as { t?: string; error?: string };
        if (parsed.error) throw new Error(parsed.error);
        if (parsed.t) onToken(parsed.t);
      } catch {
        // chunk não-JSON ignorado (ex: eventos de controle)
      }
    }
  }
}
