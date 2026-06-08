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
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

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

// ---------- Sessions ----------

export async function listSessions(): Promise<SessionSummary[]> {
  const data = await req<unknown>("/sessions");
  if (Array.isArray(data)) return data as SessionSummary[];
  return [];
}

export async function createSession(): Promise<string> {
  const data = await req<{ id: string }>("/sessions", { method: "POST" });
  return data.id;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await req<void>(`/sessions/${sessionId}`, { method: "DELETE" });
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
      onToken(payload.replace(/\\n/g, "\n"));
    }
  }
}
