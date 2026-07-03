/**
 * Store de chat por sessão — vive fora do ciclo de vida dos componentes.
 * ---------------------------------------------------------------------------
 * Motivação: quando o estado de streaming morava dentro de `useChat(sessionId)`,
 * navegar entre páginas ou trocar de sessão disparava um reset (`setMessages([])`)
 * e a geração em andamento escrevia num estado já descartado — a resposta "sumia".
 *
 * Aqui a geração roda desacoplada da UI: cada sessão tem seu próprio slice num
 * `Map` de módulo. Componentes apenas assinam (via `useSyncExternalStore`) o
 * slice da sessão ativa. Trocar de sessão ou de página não interrompe nada —
 * ao voltar, o slice ainda está lá, continuando ou já concluído.
 */

import { fetchMessages, sendMessage, type ChatMessage } from "../api/client";

export type { ChatMessage };

interface SessionState {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  loaded: boolean; // histórico já buscado do backend?
  buffer: string; // acumula tokens sem re-render por token
  assistantId: string | null;
  raf: number | null;
}

function emptyState(): SessionState {
  return {
    messages: [],
    isStreaming: false,
    error: null,
    loaded: false,
    buffer: "",
    assistantId: null,
    raf: null,
  };
}

const store = new Map<string, SessionState>();
const listeners = new Map<string, Set<() => void>>();

function uuid(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function getState(sessionId: string): SessionState {
  let s = store.get(sessionId);
  if (!s) {
    s = emptyState();
    store.set(sessionId, s);
  }
  return s;
}

function emit(sessionId: string): void {
  listeners.get(sessionId)?.forEach((fn) => fn());
}

/** Substitui o slice (imutável para o snapshot) e notifica os assinantes. */
function patch(sessionId: string, partial: Partial<SessionState>): void {
  const next = { ...getState(sessionId), ...partial };
  store.set(sessionId, next);
  emit(sessionId);
}

export function subscribe(sessionId: string, listener: () => void): () => void {
  let set = listeners.get(sessionId);
  if (!set) {
    set = new Set();
    listeners.set(sessionId, set);
  }
  set.add(listener);
  return () => {
    set!.delete(listener);
  };
}

export function getSnapshot(sessionId: string): SessionState {
  return getState(sessionId);
}

/** Carrega o histórico do backend uma vez por sessão (não sobrescreve stream ativo). */
export async function loadHistory(sessionId: string): Promise<void> {
  const s = getState(sessionId);
  if (s.loaded || s.isStreaming) return;
  patch(sessionId, { loaded: true });
  try {
    const history = await fetchMessages(sessionId);
    // Evita corrida: só aplica se ninguém começou a streamar nesse meio-tempo.
    if (!getState(sessionId).isStreaming) patch(sessionId, { messages: history });
  } catch {
    patch(sessionId, { messages: [] });
  }
}

export async function send(sessionId: string, text: string): Promise<void> {
  const current = getState(sessionId);
  if (!text.trim() || current.isStreaming) return;

  const userMsg: ChatMessage = { id: uuid(), role: "user", content: text.trim() };
  const assistantId = uuid();

  patch(sessionId, {
    error: null,
    isStreaming: true,
    buffer: "",
    assistantId,
    messages: [
      ...current.messages,
      userMsg,
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ],
  });

  // Loop de render a ~60fps: reflete o buffer acumulado na mensagem do assistente.
  const flush = () => {
    const s = getState(sessionId);
    patch(sessionId, {
      messages: s.messages.map((m) =>
        m.id === s.assistantId ? { ...m, content: s.buffer } : m,
      ),
      raf: requestAnimationFrame(flush),
    });
  };
  patch(sessionId, { raf: requestAnimationFrame(flush) });

  try {
    await sendMessage(sessionId, text.trim(), (chunk) => {
      patch(sessionId, { buffer: getState(sessionId).buffer + chunk });
    });
  } catch {
    const s = getState(sessionId);
    patch(sessionId, {
      error: "Não foi possível obter resposta. Verifique se a API está ativa.",
      messages: s.messages.map((m) =>
        m.id === assistantId && m.content === ""
          ? { ...m, content: "⚠️ Erro ao gerar resposta." }
          : m,
      ),
    });
  } finally {
    const s = getState(sessionId);
    if (s.raf !== null) cancelAnimationFrame(s.raf);
    patch(sessionId, {
      raf: null,
      isStreaming: false,
      assistantId: null,
      messages: s.messages.map((m) =>
        m.id === assistantId ? { ...m, content: s.buffer, streaming: false } : m,
      ),
    });
  }
}

/** Descarta o slice em memória (ex.: ao apagar a sessão). */
export function dropSession(sessionId: string): void {
  const s = store.get(sessionId);
  if (s?.raf != null) cancelAnimationFrame(s.raf);
  store.delete(sessionId);
}
