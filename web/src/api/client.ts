const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function authHeader(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

// ---------- Auth ----------

export async function signin(username: string, password: string): Promise<string> {
  const res = await fetch(`${API_URL}/auth/signin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Usuário ou senha inválidos");
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

export async function signup(username: string, password: string): Promise<void> {
  const res = await fetch(`${API_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? "Erro ao criar conta");
  }
}

// ---------- Sessions ----------

export interface SessionInfo {
  id: string;
  title: string | null;
  created_at: string;
}

export async function createSession(token: string): Promise<SessionInfo> {
  const res = await fetch(`${API_URL}/sessions`, {
    method: "POST",
    headers: authHeader(token),
  });
  if (!res.ok) throw new Error("Falha ao criar sessão");
  return res.json() as Promise<SessionInfo>;
}

export async function listSessions(token: string): Promise<SessionInfo[]> {
  const res = await fetch(`${API_URL}/sessions`, { headers: authHeader(token) });
  if (!res.ok) return [];
  return res.json() as Promise<SessionInfo[]>;
}

// ---------- Messages ----------

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export async function fetchMessages(token: string, sessionId: string): Promise<HistoryMessage[]> {
  const res = await fetch(`${API_URL}/sessions/${sessionId}/messages`, {
    headers: authHeader(token),
  });
  if (!res.ok) return [];
  return res.json() as Promise<HistoryMessage[]>;
}

export async function sendMessage(
  token: string,
  sessionId: string,
  content: string,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: authHeader(token),
    body: JSON.stringify({ content }),
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
