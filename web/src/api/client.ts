const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function createSession(): Promise<string> {
  const res = await fetch(`${API_URL}/session`, { method: "POST" });
  if (!res.ok) throw new Error("Falha ao criar sessão");
  const data = (await res.json()) as { session_id: string };
  return data.session_id;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export async function fetchHistory(
  sessionId: string,
): Promise<HistoryMessage[]> {
  const res = await fetch(`${API_URL}/history/${sessionId}`);
  if (!res.ok) return [];
  const data = (await res.json()) as { messages: HistoryMessage[] };
  return data.messages;
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
    headers: { "Content-Type": "application/json" },
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
