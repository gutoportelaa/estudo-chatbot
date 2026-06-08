const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// --- Helpers de Autenticação ---
export function getToken(): string | null {
  return localStorage.getItem("thinkai.token");
}

function getHeaders(): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// --- Autenticação ---
export async function login(username: string, password: string): Promise<string> {
  const res = await fetch(`${API_URL}/auth/signin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Falha ao fazer login");
  const data = await res.json();
  return data.access_token;
}

export async function signup(username: string, password: string): Promise<void> {
  const res = await fetch(`${API_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Falha ao criar conta");
}

// --- Sessões ---
export interface SessionItem {
  id: string;
  title?: string;
  created_at: string;
}

export async function fetchSessions(): Promise<SessionItem[]> {
  const res = await fetch(`${API_URL}/sessions`, { headers: getHeaders() });
  if (!res.ok) {
    // Se o backend ainda não tiver /sessions implementado (fallback vazio)
    if (res.status === 404) return [];
    throw new Error("Falha ao buscar sessões");
  }
  return await res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_URL}/sessions/${sessionId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Falha ao deletar sessão");
}

// O método createSession foi mantido para retrocompatibilidade
// caso seja usado em algum lugar (ex: forçar criação).
export async function createSession(): Promise<string> {
  let res = await fetch(`${API_URL}/sessions`, { method: "POST", headers: getHeaders() });
  if (res.status === 404) {
      res = await fetch(`${API_URL}/session`, { method: "POST", headers: getHeaders() });
  }
  if (!res.ok) throw new Error("Falha ao criar sessão");
  const data = (await res.json()) as { session_id: string };
  return data.session_id;
}

// --- Chat ---
export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export async function fetchHistory(
  sessionId: string,
): Promise<HistoryMessage[]> {
  const res = await fetch(`${API_URL}/history/${sessionId}`, { headers: getHeaders() });
  if (!res.ok) return [];
  const data = (await res.json()) as { messages: HistoryMessage[] } | HistoryMessage[];
  // Adaptação para suportar diferentes retornos do backend ({messages: []} ou [])
  if (Array.isArray(data)) return data;
  return data.messages || [];
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
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error("Falha ao enviar mensagem");

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
