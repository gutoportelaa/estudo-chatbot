"""Enfileiramento e execução de jobs assíncronos (Arq/Redis).

Ponte entre a API (que enfileira) e o worker (que executa). Único job: geração
de resumo + mindmap dos documentos selecionados, fora do request HTTP.
"""

from __future__ import annotations

import logging

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from .config import get_settings

logger = logging.getLogger("thinkai.jobs")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def enqueue_summary(summary_id: str) -> None:
    """Enfileira o processamento de um Summary já criado (status='pending')."""
    redis: ArqRedis = await create_pool(_redis_settings())
    try:
        await redis.enqueue_job("process_summary", summary_id)
    finally:
        await redis.close()


async def process_summary(ctx: dict, summary_id: str) -> dict:
    """Executa a geração de resumo + mindmap para um Summary.

    Fluxo:
      1. Marca ``status='processing'``.
      2. Carrega os documentos-fonte e seus textos extraídos (storage).
      3. LLM 1 → título + resumo (multi-documento com delimitação).
      4. LLM 2 → mapa mental (outline markdown).
      5. Persiste tudo com ``status='done'`` (ou ``'failed'`` + ``error`` em falha).

    Idempotente: só (re)processa se o Summary estiver em ``pending`` ou
    ``failed``. Estados terminais (``done``) ou em curso (``processing``)
    passam batido.
    """
    from sqlalchemy import select
    from starlette.concurrency import run_in_threadpool

    from .config import get_settings
    from .database import AsyncSessionLocal
    from .llm import build_chat_client
    from .models import Document, Summary, SummaryDocument
    from .storage import get_storage
    from .tools.summarize import generate_mindmap_from_documents, summarize_documents

    logger.info("process_summary iniciado summary_id=%s", summary_id)
    settings = get_settings()
    storage = get_storage()

    async with AsyncSessionLocal() as db:
        summary = await db.get(Summary, summary_id)
        if not summary:
            logger.warning("Summary %s não encontrado — job descartado", summary_id)
            return {"summary_id": summary_id, "status": "not_found"}
        if summary.status not in ("pending", "failed"):
            logger.info("Summary %s já está em %s — ignorado", summary_id, summary.status)
            return {"summary_id": summary_id, "status": summary.status}

        summary.status = "processing"
        summary.error = None
        await db.commit()

        # Carrega documentos-fonte na ordem em que foram anexados.
        doc_ids = list(
            (
                await db.execute(
                    select(SummaryDocument.document_id).where(
                        SummaryDocument.summary_id == summary_id
                    )
                )
            ).scalars()
        )
        rows = list(
            (
                await db.execute(select(Document).where(Document.id.in_(doc_ids)))
            ).scalars()
        )
        by_id = {d.id: d for d in rows}
        ordered = [by_id[d] for d in doc_ids if d in by_id]

        try:
            payload: list[tuple[str, str]] = []
            for doc in ordered:
                if doc.extraction_status != "done" or not doc.extracted_key:
                    raise RuntimeError(f"Documento '{doc.filename}' sem texto extraído")
                raw = await run_in_threadpool(storage.load, doc.extracted_key)
                payload.append((doc.filename, raw.decode("utf-8", errors="replace")))
            if not payload:
                raise RuntimeError("Nenhum documento válido para resumir")

            client, model = build_chat_client(settings)
            title, content = await summarize_documents(client, model, payload)
            mindmap = await generate_mindmap_from_documents(client, model, payload)

            summary.title = title
            summary.content = content
            summary.mindmap = mindmap
            summary.llm_model = model
            summary.status = "done"
            summary.error = None
            await db.commit()
            logger.info("process_summary concluído summary_id=%s", summary_id)
            return {"summary_id": summary_id, "status": "done"}
        except Exception as exc:
            logger.exception("Falha em process_summary %s", summary_id)
            summary.status = "failed"
            summary.error = str(exc)[:500]
            await db.commit()
            return {"summary_id": summary_id, "status": "failed", "error": summary.error}
