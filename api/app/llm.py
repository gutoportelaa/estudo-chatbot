"""Streaming OpenAI-compatível para provedores Groq, OpenRouter e Ollama."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import select

from . import context
from .config import get_settings
from .database import AsyncSessionLocal
from .models import Message
from .models import Session as SessionRow
from .models import SessionDocument, TurnMetric
from .tools.websearch import needs_web_search, web_search as web_search_tool
from .observability import TurnMetrics, estimate_cost, log_turn

logger = logging.getLogger("thinkai.llm")

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
        "api_key_field": "groq_api_key",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "api_key_field": "openrouter_api_key",
    },
    "ollama": {
        "base_url": "",  # preenchido dinamicamente de ollama_base_url
        "model": "",     # preenchido dinamicamente de ollama_model
        "api_key_field": "",
    },
}


def active_model() -> str:
    """Retorna o nome do modelo em uso (para o /health)."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if settings.llm_model:
        return settings.llm_model
    if provider == "ollama":
        return settings.ollama_model
    if provider in _PROVIDER_DEFAULTS:
        return _PROVIDER_DEFAULTS[provider]["model"]
    return settings.gemini_model


def build_chat_client(settings) -> tuple[AsyncOpenAI, str]:
    """Constrói um client OpenAI-compatível para o provedor de chat ativo e o
    modelo a usar. Reutilizado por ferramentas que precisam do LLM fora do fluxo
    de streaming (ex.: geração de resumos #44/#45). Cobre groq/openrouter/ollama
    e gemini (via endpoint OpenAI-compat)."""
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        base_url = settings.gemini_openai_base_url
        model = settings.llm_model or settings.gemini_model
        api_key = settings.gemini_api_key or "no-key"
    elif provider == "ollama":
        base_url = settings.ollama_base_url
        model = settings.llm_model or settings.ollama_model
        api_key = "ollama"
    else:
        cfg = _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["groq"])
        base_url = cfg["base_url"]
        model = settings.llm_model or cfg["model"]
        api_key = getattr(settings, cfg["api_key_field"], "") or "no-key"
    return AsyncOpenAI(base_url=base_url, api_key=api_key), model


def _sse(payload: str) -> str:
    """Emite um evento SSE com payload JSON: data: {"t": "..."}\n\n"""
    return f"data: {json.dumps({'t': payload})}\n\n"


_MINDMAP_TRIGGERS = re.compile(
    r"\b(mapa mental|mapa\s+mentais|mindmap|mind-map|esquema visual|diagrama)\b",
    re.IGNORECASE,
)
# Padrão A — ```markdown|md ... ``` (linguagem errada)
_MARKDOWN_FENCE = re.compile(r"```(markdown|md)\b(.*?)```", re.DOTALL)
# Padrão B — ``` sem linguagem, com "markmap" como 1ª linha do conteúdo
_BARE_FENCE_MARKMAP = re.compile(
    r"```[ \t]*\n[ \t]*markmap[ \t]*\n(.*?)```", re.DOTALL
)


def _has_outline(body: str) -> bool:
    return bool(
        re.search(r"^\s*#\s+\S", body, re.MULTILINE)
        and re.search(r"^(##\s+\S|-\s+\S)", body, re.MULTILINE)
    )


def _fix_markmap_fence(response: str, user_request: str) -> str:
    """Normaliza fences de mapa mental para ```markmap.

    Modelos pequenos (llama-3.1-8b) escrevem o rótulo errado (`markdown`, `md`)
    ou colocam `markmap` como primeira linha do conteúdo em vez de linguagem
    do fence. Aqui a gente corrige os dois padrões — apenas quando o usuário
    pediu mapa mental e o bloco parece um outline (evita mexer em código
    markdown legítimo).
    """
    if not _MINDMAP_TRIGGERS.search(user_request or ""):
        return response

    def _repl_lang(m: re.Match[str]) -> str:
        body = m.group(2)
        return f"```markmap{body}```" if _has_outline(body) else m.group(0)

    def _repl_bare(m: re.Match[str]) -> str:
        body = m.group(1)
        return f"```markmap\n{body}```" if _has_outline(body) else m.group(0)

    response = _MARKDOWN_FENCE.sub(_repl_lang, response)
    response = _BARE_FENCE_MARKMAP.sub(_repl_bare, response)
    return response


async def _retrieve_rag_hits(db, *, user_id, query, settings, document_ids=None):
    """Recupera trechos do material do usuário para o turno (RAG, issue #34).

    Só embeda a pergunta se o usuário tiver algum chunk indexado (evita custo à
    toa). Quando a conversa tem documentos selecionados (Biblioteca), restringe a
    busca a eles. Limita os hits pela cota ``rag_max_tokens``. Nunca quebra o
    chat: se o RAG falhar (embedder indisponível etc.), segue sem hits.
    """
    from sqlalchemy import select

    from .models import Chunk, Document
    from .tools.rag import build_rag_hits, get_embedder, retrieve

    if not user_id or not document_ids:
        # Isolamento: sem documentos escopados à conversa, não há RAG. Nunca
        # recupera sobre toda a biblioteca do usuário (vazaria entre conversas).
        return None, []
    try:
        has_chunks = await db.scalar(
            select(Chunk.id)
            .where(Chunk.user_id == user_id, Chunk.document_id.in_(document_ids))
            .limit(1)
        )
        if not has_chunks:
            return None, []

        chunks = await retrieve(
            db,
            get_embedder(settings),
            user_id=user_id,
            query=query,
            k=settings.rag_top_k,
            document_ids=document_ids,
        )
        hits = await build_rag_hits(db, chunks)

        # Cota de tokens do bloco de RAG: mantém os mais relevantes primeiro.
        capped: list[dict[str, str]] = []
        used = 0
        for h in hits:
            cost = context.estimate_tokens(h["content"])
            if used + cost > settings.rag_max_tokens:
                break
            capped.append(h)
            used += cost

        # Fontes estruturadas (#34) para citação linkável — alinhadas aos hits
        # que efetivamente entraram (mesma ordem). Abrem o documento no chunk.
        used_chunks = chunks[: len(capped)]
        names = {}
        if used_chunks:
            doc_ids = {c.document_id for c in used_chunks}
            rows = await db.execute(select(Document.id, Document.filename).where(Document.id.in_(doc_ids)))
            names = dict(rows.all())
        rag_sources = [
            {
                "kind": "rag",
                "title": names.get(c.document_id, "documento"),
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page": c.page,
                "snippet": " ".join(c.text.split())[:300],
            }
            for c in used_chunks
        ]
        return (capped or None), rag_sources
    except Exception:  # pragma: no cover - resiliência: RAG nunca quebra o chat
        logger.exception("Falha ao recuperar RAG para o usuário %s", user_id)
        return None, []


async def stream_openai_compatible(
    *,
    session_id: str,
    content: str,
    web_search: bool = False,
) -> AsyncGenerator[str, None]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        base_url = settings.ollama_base_url
        model = settings.llm_model or settings.ollama_model
        api_key = "ollama"
    else:
        cfg = _PROVIDER_DEFAULTS[provider]
        base_url = cfg["base_url"]
        model = settings.llm_model or cfg["model"]
        api_key = getattr(settings, cfg["api_key_field"], "") or "no-key"

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    # Persiste a mensagem do usuário e monta o contexto com gestão de histórico
    # (janela deslizante + resumo). A sumarização usa o mesmo provedor/cliente.
    now = datetime.now(timezone.utc)
    summarizer_model = settings.summarizer_model or model
    summarizer = context.build_summarizer(
        client=client,
        model=summarizer_model,
        max_tokens=settings.history_summary_max_tokens,
    )

    async with AsyncSessionLocal() as db:
        session_row = await db.get(SessionRow, session_id)
        user_id = session_row.user_id if session_row else None
        if session_row and session_row.title is None:
            compact = " ".join(content.split())
            session_row.title = compact[:120] or None

        db.add(Message(session_id=session_id, role="user", content=content, created_at=now))
        await db.commit()

        # Documentos escopados a ESTA conversa (Biblioteca / clipe). O RAG só
        # recupera dentro deles — isolamento por conversa. Sem documentos
        # anexados, não há RAG (evita vazar material de outras conversas).
        scoped_docs = list(
            (
                await db.execute(
                    select(SessionDocument.document_id).where(
                        SessionDocument.session_id == session_id
                    )
                )
            ).scalars()
        )
        if scoped_docs:
            rag_hits, rag_sources = await _retrieve_rag_hits(
                db,
                user_id=user_id,
                query=content,
                settings=settings,
                document_ids=scoped_docs,
            )
        else:
            rag_hits, rag_sources = None, []

        # Busca web (#35): acionada pelo toggle ou pela heurística. O resumo
        # rankeado entra na cota de ferramentas; as fontes são anexadas à
        # resposta de forma determinística (não dependem de o modelo citar).
        tool_output: str | None = None
        web_answer: str | None = None
        sources: list[dict] = list(rag_sources)
        if web_search or needs_web_search(content, settings):
            yield f"data: {json.dumps({'stage': 'searching'})}\n\n"
            result = await web_search_tool(content, settings)
            if result:
                tool_output = result.tool.summary_for_context
                web_answer = result.answer
                sources = [
                    {"kind": "web", **s.as_dict()} for s in result.sources
                ] + sources
                yield f"data: {json.dumps({'stage': 'reading', 'count': len(result.sources)})}\n\n"
            else:
                yield f"data: {json.dumps({'stage': 'search_empty'})}\n\n"

        messages, breakdown = await context.assemble_messages(
            db,
            session_id=session_id,
            system_prompt=settings.system_prompt,
            settings=settings,
            summarizer=summarizer,
            summarizer_model=summarizer_model,
            model=model,
            rag_hits=rag_hits,
            tool_output=tool_output,
        )

    if tool_output:
        yield f"data: {json.dumps({'stage': 'generating'})}\n\n"

    full_text = ""
    error_text: str | None = None
    started = time.monotonic()

    try:
        async for chunk in await client.chat.completions.create(
            model=model, messages=messages, stream=True
        ):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                full_text += delta
                yield _sse(delta)
    except Exception as exc:
        error_text = str(exc)[:300]
        yield f"data: {json.dumps({'error': error_text})}\n\n"
    else:
        # Fallback: se o modelo (pequeno) redigiu muito pouco mas a busca web
        # trouxe uma síntese, entrega a síntese para o usuário não ficar sem
        # resposta útil. As fontes continuam anexadas.
        if web_answer and len(full_text.strip()) < 40:
            fallback = ("\n\n" if full_text.strip() else "") + web_answer
            full_text += fallback
            yield _sse(fallback)
        if sources:
            yield f"data: {json.dumps({'sources': sources})}\n\n"
        yield "data: [DONE]\n\n"

    # Observabilidade do turno (issue #37): quebra de tokens por bloco + saída,
    # latência e custo estimado. Emitido como log estruturado (JSON) e persistido
    # para a tela de Consumo. Falhas também são registradas (status="error").
    output_tokens = context.estimate_tokens(full_text)
    latency_ms = round((time.monotonic() - started) * 1000, 1)
    metrics = TurnMetrics(
        session_id=session_id,
        model=model,
        provider=provider,
        user_id=user_id,
        tokens_system=breakdown.system,
        tokens_summary=breakdown.summary,
        tokens_rag=breakdown.rag,
        tokens_recent=breakdown.recent,
        tokens_tool=breakdown.tool,
        input_tokens=breakdown.total,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=estimate_cost(model, breakdown.total, output_tokens),
    )
    log_turn(metrics)

    async with AsyncSessionLocal() as db:
        session_row = await db.get(SessionRow, session_id)
        if session_row:
            session_row.updated_at = datetime.now(timezone.utc)
        # Só grava a resposta do assistente quando houve texto (turnos que falharam
        # antes de qualquer token não poluem o histórico).
        if full_text:
            persisted = _fix_markmap_fence(full_text, content)
            db.add(
                Message(
                    session_id=session_id,
                    role="assistant",
                    content=persisted,
                    sources=sources or None,
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.add(
            TurnMetric(
                user_id=user_id,
                session_id=session_id,
                model=metrics.model,
                provider=metrics.provider,
                input_tokens=metrics.input_tokens,
                output_tokens=metrics.output_tokens,
                latency_ms=metrics.latency_ms,
                cost_usd=metrics.cost_usd,
                status="error" if error_text else "ok",
                error=error_text,
                rag_tokens=breakdown.rag,
                tokens_system=breakdown.system,
                tokens_summary=breakdown.summary,
                tokens_recent=breakdown.recent,
                tokens_tool=breakdown.tool,
            )
        )
        await db.commit()
