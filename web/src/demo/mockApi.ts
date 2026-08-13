/**
 * API simulada do modo demo (GitHub Pages).
 * ---------------------------------------------------------------------------
 * O front publicado no Pages é estático: não há FastAPI, Postgres nem LLM.
 * Este módulo intercepta `fetch` (e o `XMLHttpRequest` do upload) e devolve as
 * fixtures de `./fixtures`, inclusive um stream SSE falso para o chat, de modo
 * que a interface real possa ser navegada sem backend.
 *
 * Só é carregado quando `VITE_DEMO=1` — o build de produção não o importa.
 */

import {
  DEMO_CONTEXT,
  DEMO_DOCUMENTS,
  DEMO_DOC_SUMMARY,
  DEMO_FALLBACK_REPLY,
  DEMO_MESSAGES,
  DEMO_MINDMAP,
  DEMO_SESSIONS,
  DEMO_SUMMARIES,
  DEMO_SUMMARY_EVENTS,
  DEMO_USAGE,
  DEMO_USER,
} from "./fixtures";
import type { ChatMessage, DocumentItem, SessionSummary } from "../api/client";

const API_URL = import.meta.env.VITE_API_URL ?? "";
const TOKEN_KEY = "thinkai.jwt";

// Estado mutável da sessão de demonstração (vive só na aba do visitante).
const sessions: SessionSummary[] = [...DEMO_SESSIONS];
const messages: Record<string, ChatMessage[]> = structuredClone(DEMO_MESSAGES);
const documents: DocumentItem[] = [...DEMO_DOCUMENTS];
const sessionDocs: Record<string, string[]> = { s1: ["d5", "d1"], s2: ["d2"] };

let seq = 0;
const uid = (p: string) => `${p}-${Date.now().toString(36)}-${seq++}`;

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Divide o texto em pedaços curtos para imitar o streaming token a token. */
function chunkText(text: string): string[] {
  return text.match(/\s*\S+/g) ?? [text];
}

/** Monta um corpo SSE equivalente ao que a API real emite em /messages. */
function sseStream(content: string, sources?: ChatMessage["sources"]): Response {
  const encoder = new TextEncoder();
  const send = (obj: unknown) => encoder.encode(`data: ${JSON.stringify(obj)}\n\n`);

  const stream = new ReadableStream({
    async start(controller) {
      if (sources?.length) {
        controller.enqueue(send({ stage: "rag", count: sources.length }));
        await sleep(500);
      }
      controller.enqueue(send({ stage: "generating" }));
      await sleep(250);

      for (const piece of chunkText(content)) {
        controller.enqueue(send({ t: piece }));
        await sleep(18);
      }
      if (sources?.length) controller.enqueue(send({ sources }));
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function newDocument(filename: string, size: number): DocumentItem {
  return {
    id: uid("doc"),
    filename,
    size_bytes: size,
    page_count: Math.max(1, Math.round(size / 90_000)),
    extraction_status: "done",
    has_thumbnail: false,
    created_at: new Date().toISOString(),
  };
}

async function handle(path: string, method: string, body: unknown): Promise<Response> {
  const seg = path.split("/").filter(Boolean);

  // ---------- health / auth ----------
  if (path === "/health") return json({ provider: "gemini", model: "gemini-2.0-flash" });
  if (path === "/auth/signin" || path === "/auth/signup")
    return json({ access_token: "demo-token" });
  if (path === "/auth/profile") {
    if (method === "PATCH") return json({ ...DEMO_USER, ...(body as object) });
    return json(DEMO_USER);
  }
  if (path === "/auth/avatar") return json({ detail: "sem avatar" }, 404);

  // ---------- sessions ----------
  if (path === "/sessions") {
    if (method === "POST") {
      const ids = (body as { document_ids?: string[] })?.document_ids ?? [];
      const s: SessionSummary = {
        id: uid("s"),
        title: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      sessions.unshift(s);
      messages[s.id] = [];
      sessionDocs[s.id] = ids;
      return json({ id: s.id });
    }
    return json(sessions);
  }

  if (seg[0] === "sessions" && seg[1]) {
    const id = seg[1];
    const rest = seg[2];

    if (!rest) {
      if (method === "DELETE") {
        const i = sessions.findIndex((s) => s.id === id);
        if (i >= 0) sessions.splice(i, 1);
        delete messages[id];
        return new Response(null, { status: 204 });
      }
      if (method === "PATCH") {
        const s = sessions.find((x) => x.id === id);
        if (s) s.title = (body as { title?: string })?.title ?? s.title;
        return json(s ?? {});
      }
    }

    if (rest === "messages") {
      if (method === "POST") {
        const content = (body as { content?: string })?.content ?? "";
        const list = (messages[id] ??= []);
        list.push({ id: uid("m"), role: "user", content });

        const s = sessions.find((x) => x.id === id);
        if (s && !s.title?.trim()) s.title = content.slice(0, 40) || "Nova conversa";

        const reply = DEMO_FALLBACK_REPLY;
        list.push({ id: uid("m"), role: "assistant", content: reply, sources: null });
        return sseStream(reply);
      }
      return json(messages[id] ?? []);
    }

    if (rest === "documents") {
      const current = (sessionDocs[id] ??= []);
      if (method === "POST") {
        const ids = (body as { document_ids?: string[] })?.document_ids ?? [];
        sessionDocs[id] = [...new Set([...current, ...ids])];
        return json({ document_ids: sessionDocs[id] });
      }
      if (method === "DELETE") {
        sessionDocs[id] = current.filter((d) => d !== seg[3]);
        return json({ document_ids: sessionDocs[id] });
      }
      return json({ document_ids: current });
    }

    if (rest === "summaries") return json(id === "s1" ? DEMO_SUMMARY_EVENTS : []);
    if (rest === "context") return json(DEMO_CONTEXT);
  }

  // ---------- documentos ----------
  if (path === "/documents") {
    if (method === "POST") {
      const doc = newDocument("documento-enviado.pdf", 1_200_000);
      documents.unshift(doc);
      return json(doc);
    }
    return json(documents);
  }

  if (seg[0] === "documents" && seg[1]) {
    const id = seg[1];
    const rest = seg[2];
    if (!rest && method === "DELETE") {
      const i = documents.findIndex((d) => d.id === id);
      if (i >= 0) documents.splice(i, 1);
      return new Response(null, { status: 204 });
    }
    if (rest === "summary") return json({ ...DEMO_DOC_SUMMARY, document_ids: [id] });
    if (rest === "mindmap") return json({ ...DEMO_MINDMAP, document_ids: [id] });
    if (rest === "index") return json({ chunks_indexed: 128 });
    if (rest === "extract") return json({ status: "done" });
    // Capa e PDF bruto não existem na demo: a UI já tem fallback para ambos.
    if (rest === "thumbnail" || rest === "raw") return json({ detail: "indisponível na demo" }, 404);
  }

  // ---------- resumos e métricas ----------
  if (path === "/summaries") return json(DEMO_SUMMARIES);
  if (path === "/summaries/consolidated") {
    const ids = (body as { document_ids?: string[] })?.document_ids ?? [];
    return json({
      id: uid("cs"),
      kind: "consolidated",
      llm_model: "gemini-2.0-flash",
      document_ids: ids,
      created_at: new Date().toISOString(),
      content: `### Resumo consolidado (demo)\n\nNa aplicação real, os **${ids.length} documentos** selecionados seriam lidos e comparados por um LLM, produzindo um texto único que aponta convergências, divergências e lacunas entre eles.`,
    });
  }
  if (path.startsWith("/metrics/usage")) return json(DEMO_USAGE);

  return json({ detail: "Rota não simulada na demo" }, 404);
}

/** Instala os interceptadores. Idempotente. */
export function installDemoApi(): void {
  // Já entra autenticado: não há o que proteger numa vitrine estática.
  localStorage.setItem(TOKEN_KEY, "demo-token");

  const realFetch = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;

    if (!url.startsWith(API_URL) && !url.startsWith(new URL(API_URL, location.href).href)) {
      return realFetch(input as RequestInfo, init);
    }

    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const path = new URL(url, location.href).pathname.slice(new URL(API_URL, location.href).pathname.replace(/\/$/, "").length) || "/";

    let body: unknown;
    const raw = init?.body;
    if (typeof raw === "string") {
      try {
        body = JSON.parse(raw);
      } catch {
        body = raw;
      }
    }

    await sleep(120); // latência simulada, para a UI mostrar seus estados de carga
    return handle(path, method, body);
  };

  // O upload usa XMLHttpRequest (para ter progresso real); simulamos o mínimo.
  const RealXHR = window.XMLHttpRequest;
  class DemoXHR extends RealXHR {
    private _demo = false;

    open(method: string, url: string | URL, ...rest: unknown[]): void {
      this._demo = String(url).includes("/documents");
      if (this._demo) {
        // Aponta para um recurso estático inofensivo; a resposta é sintetizada.
        super.open(method, `${import.meta.env.BASE_URL}vite.svg`, true);
        return;
      }
      // @ts-expect-error repasse da assinatura original
      super.open(method, url, ...rest);
    }

    send(data?: Document | XMLHttpRequestBodyInit | null): void {
      if (!this._demo) return super.send(data);

      const file = data instanceof FormData ? (data.get("file") as File | null) : null;
      const doc = newDocument(file?.name ?? "documento.pdf", file?.size ?? 800_000);

      let pct = 0;
      const tick = setInterval(() => {
        pct = Math.min(100, pct + 12);
        this.upload?.dispatchEvent(
          Object.assign(new ProgressEvent("progress"), {
            lengthComputable: true,
            loaded: pct,
            total: 100,
          }),
        );
        if (pct >= 100) {
          clearInterval(tick);
          documents.unshift(doc);
          Object.defineProperty(this, "status", { value: 201, configurable: true });
          Object.defineProperty(this, "responseText", {
            value: JSON.stringify(doc),
            configurable: true,
          });
          this.dispatchEvent(new ProgressEvent("load"));
        }
      }, 90);
    }
  }
  window.XMLHttpRequest = DemoXHR as unknown as typeof XMLHttpRequest;
}
