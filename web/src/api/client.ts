const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_STORAGE_KEY = "thinkai.jwt";

export interface AuthUser {
  id: string;
  username: string;
  created_at: string;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SessionSummary {
  id: string;
  title?: string | null;
  created_at?: string;
  updated_at?: string;
  user_id?: string;
}

interface ApiErrorPayload {
  detail?: string;
  [key: string]: unknown;
}

class ApiError extends Error {
  status: number;
  payload?: ApiErrorPayload;

  constructor(status: number, message: string, payload?: ApiErrorPayload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function readStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

function storeToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function getAuthToken(): string | null {
  return readStoredToken();
}

export function setAuthToken(token: string): void {
  storeToken(token);
}

export function authHeaders(token: string | null = readStoredToken()): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function logout(): void {
  clearStoredToken();
}

function mergeHeaders(...sources: Array<HeadersInit | undefined>): Headers {
  const headers = new Headers();

  for (const source of sources) {
    if (!source) continue;
    const current = new Headers(source);
    current.forEach((value, key) => {
      headers.set(key, value);
    });
  }

  return headers;
}

async function readErrorPayload(res: Response): Promise<ApiErrorPayload | undefined> {
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return undefined;

  try {
    return (await res.json()) as ApiErrorPayload;
  } catch {
    return undefined;
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  options: { useAuth?: boolean } = {},
): Promise<T> {
  const headers = mergeHeaders(init.headers);
  const useAuth = options.useAuth !== false;
  const token = useAuth ? readStoredToken() : null;

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });

  if (!res.ok) {
    const payload = await readErrorPayload(res);
    if (res.status === 401) {
      clearStoredToken();
    }
    throw new ApiError(res.status, payload?.detail ?? `Request failed (${res.status})`, payload);
  }

  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

function extractSessionId(payload: unknown): string {
  if (typeof payload === "string") return payload;

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const sessionId = record.session_id ?? record.id;
    if (typeof sessionId === "string") return sessionId;
  }

  throw new Error("Resposta inválida ao criar sessão");
}

function extractHistoryMessages(payload: unknown): HistoryMessage[] {
  if (Array.isArray(payload)) {
    return payload.filter((item): item is HistoryMessage => {
      return Boolean(
        item &&
          typeof item === "object" &&
          typeof (item as HistoryMessage).role === "string" &&
          typeof (item as HistoryMessage).content === "string",
      );
    });
  }

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const messages = record.messages;
    if (Array.isArray(messages)) {
      return messages.filter((item): item is HistoryMessage => {
        return Boolean(
          item &&
            typeof item === "object" &&
            typeof (item as HistoryMessage).role === "string" &&
            typeof (item as HistoryMessage).content === "string",
        );
      });
    }
  }

  return [];
}

function extractSessionList(payload: unknown): SessionSummary[] {
  const isSessionSummary = (item: unknown): item is SessionSummary => {
    return Boolean(
      item &&
        typeof item === "object" &&
        typeof (item as SessionSummary).id === "string",
    );
  };

  if (Array.isArray(payload)) {
    return payload.filter(isSessionSummary);
  }

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const sessions = record.sessions ?? record.items ?? record.data;
    if (Array.isArray(sessions)) {
      return sessions.filter(isSessionSummary);
    }
  }

  return [];
}

export async function signup(username: string, password: string): Promise<AuthUser> {
  return requestJson<AuthUser>(
    "/auth/signup",
    {
      method: "POST",
      body: JSON.stringify({ username, password }),
    },
    { useAuth: false },
  );
}

export async function signin(username: string, password: string): Promise<string> {
  const data = await requestJson<{ access_token: string; token_type?: string }>(
    "/auth/signin",
    {
      method: "POST",
      body: JSON.stringify({ username, password }),
    },
    { useAuth: false },
  );

  storeToken(data.access_token);
  return data.access_token;
}

export async function getProfile(): Promise<AuthUser> {
  return requestJson<AuthUser>("/auth/profile");
}

export async function listSessions(): Promise<SessionSummary[]> {
  return extractSessionList(await requestJson<unknown>("/sessions"));
}

export async function createSession(): Promise<string> {
  try {
    const data = await requestJson<unknown>("/sessions", { method: "POST" });
    return extractSessionId(data);
  } catch (error) {
    if (!(error instanceof ApiError) || (error.status !== 404 && error.status !== 405)) {
      throw error;
    }

    const legacy = await requestJson<unknown>("/session", { method: "POST" }, { useAuth: false });
    return extractSessionId(legacy);
  }
}

export async function deleteSession(sessionId: string): Promise<void> {
  await requestJson<void>(`/sessions/${sessionId}`, { method: "DELETE" });
}

export async function fetchHistory(sessionId: string): Promise<HistoryMessage[]> {
  try {
    return extractHistoryMessages(await requestJson<unknown>(`/history/${sessionId}`));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return [];
    }

    if (error instanceof ApiError && (error.status === 404 || error.status === 405)) {
      return [];
    }

    throw error;
  }
}

/**
 * Envia uma mensagem e consome a resposta em streaming (SSE).
 * `onToken` é chamado a cada pedaço de texto recebido.
 */
export async function streamChat(
  sessionId: string,
  message: string,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = mergeHeaders({ "Content-Type": "application/json" }, authHeaders());
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  });

  if (!res.ok || !res.body) {
    const payload = await readErrorPayload(res);
    if (res.status === 401) {
      clearStoredToken();
    }
    throw new ApiError(res.status, payload?.detail ?? "Falha ao enviar mensagem", payload);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Eventos SSE são separados por linha em branco.
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") return;
      // Desfaz o escape de quebras de linha feito no backend.
      onToken(payload.replace(/\\n/g, "\n"));
    }
  }
}

export { ApiError };
