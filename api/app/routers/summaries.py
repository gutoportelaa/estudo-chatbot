"""Rotas de resumos de documentos via LLM (issues #44 single / #45 consolidated)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..llm import build_chat_client
from ..models import Document, Summary, SummaryDocument, User
from ..storage import get_storage
from ..tools.summarize import consolidate_summaries, summarize_text

logger = logging.getLogger("thinkai.summaries")

router = APIRouter(tags=["summaries"])


def _to_dict(s: Summary, document_ids: list[str]) -> dict:
    return {
        "id": s.id,
        "kind": s.kind,
        "llm_model": s.llm_model,
        "content": s.content,
        "document_ids": document_ids,
        "created_at": s.created_at.isoformat(),
    }


async def _owned_extracted_docs(
    db: AsyncSession, user_id: str, document_ids: list[str]
) -> list[Document]:
    """Valida posse e extração; retorna os documentos na ordem pedida."""
    rows = (
        await db.execute(
            select(Document).where(Document.id.in_(document_ids), Document.user_id == user_id)
        )
    ).scalars().all()
    by_id = {d.id: d for d in rows}
    missing = [d for d in document_ids if d not in by_id]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Documentos não encontrados: {missing}")
    docs = [by_id[d] for d in document_ids]
    not_ready = [d.filename for d in docs if d.extraction_status != "done" or not d.extracted_key]
    if not_ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Extraia o texto antes de resumir: {not_ready}",
        )
    return docs


async def _load_text(doc: Document) -> str:
    data = await run_in_threadpool(get_storage().load, doc.extracted_key)
    return data.decode("utf-8")


async def _persist_summary(
    db: AsyncSession, user_id: str, kind: str, model: str, content: str, doc_ids: list[str]
) -> Summary:
    summary = Summary(user_id=user_id, kind=kind, llm_model=model, content=content)
    db.add(summary)
    await db.flush()
    for d in doc_ids:
        db.add(SummaryDocument(summary_id=summary.id, document_id=d))
    await db.commit()
    await db.refresh(summary)
    return summary


@router.post("/documents/{document_id}/summary")
async def create_single_summary(
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Gera (e persiste) o resumo de um único documento (#44)."""
    settings = get_settings()
    (doc,) = await _owned_extracted_docs(db, current_user.id, [document_id])
    text = await _load_text(doc)
    client, model = build_chat_client(settings)
    try:
        content = await summarize_text(client, model, text)
    except Exception as exc:  # erro do LLM — não quebra, reporta claro
        logger.exception("Falha ao resumir o documento %s", document_id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Falha ao gerar o resumo: {exc}")
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Documento sem texto para resumir")
    summary = await _persist_summary(db, current_user.id, "single", model, content, [doc.id])
    return _to_dict(summary, [doc.id])


@router.get("/documents/{document_id}/summary")
async def get_single_summary(
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict | None:
    """Retorna o resumo single mais recente do documento (ou 204 se não houver)."""
    doc = await db.get(Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    row = (
        await db.execute(
            select(Summary)
            .join(SummaryDocument, SummaryDocument.summary_id == Summary.id)
            .where(SummaryDocument.document_id == document_id, Summary.kind == "single")
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return _to_dict(row, [document_id])


class ConsolidatedBody(BaseModel):
    document_ids: list[str]


@router.post("/summaries/consolidated")
async def create_consolidated_summary(
    body: ConsolidatedBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Resumo consolidado de múltiplos documentos (#45): resumo por doc + síntese."""
    ids = list(dict.fromkeys(body.document_ids))
    if len(ids) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selecione ao menos 2 documentos")
    settings = get_settings()
    docs = await _owned_extracted_docs(db, current_user.id, ids)
    client, model = build_chat_client(settings)

    try:
        per_doc: list[tuple[str, str]] = []
        for doc in docs:
            # Reaproveita o resumo single mais recente, se existir; senão gera.
            existing = (
                await db.execute(
                    select(Summary.content)
                    .join(SummaryDocument, SummaryDocument.summary_id == Summary.id)
                    .where(SummaryDocument.document_id == doc.id, Summary.kind == "single")
                    .order_by(Summary.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            summary = existing or await summarize_text(client, model, await _load_text(doc))
            per_doc.append((doc.filename, summary))
        content = await consolidate_summaries(client, model, per_doc)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Falha ao consolidar resumos")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Falha ao gerar o resumo consolidado: {exc}")

    summary = await _persist_summary(db, current_user.id, "consolidated", model, content, ids)
    return _to_dict(summary, ids)


@router.get("/summaries")
async def list_summaries(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """Lista os resumos do usuário (mais recentes primeiro), com os docs de origem."""
    rows = (
        await db.execute(
            select(Summary).where(Summary.user_id == current_user.id).order_by(Summary.created_at.desc())
        )
    ).scalars().all()
    out = []
    for s in rows:
        doc_ids = (
            await db.execute(
                select(SummaryDocument.document_id).where(SummaryDocument.summary_id == s.id)
            )
        ).scalars().all()
        out.append(_to_dict(s, list(doc_ids)))
    return out
