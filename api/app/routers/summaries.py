"""Rotas de resumos assíncronos (Arq worker).

O fluxo é: front chama ``POST /summaries`` com uma lista de ``document_ids``.
A rota cria um Summary em ``status='pending'`` e enfileira o job. O worker
processa e atualiza o registro. O front acompanha com ``POST /summaries/status``
(poll) até virar ``done`` ou ``failed``, então abre a view de detalhamento
via ``GET /summaries/{id}``.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..jobs import enqueue_summary
from ..models import Document, Summary, SummaryDocument, User

logger = logging.getLogger("thinkai.summaries")

router = APIRouter(tags=["summaries"])


def _to_dict(s: Summary, document_ids: list[str]) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "status": s.status,
        "error": s.error,
        "llm_model": s.llm_model,
        "content": s.content,
        "mindmap": s.mindmap,
        "document_ids": document_ids,
        "created_at": s.created_at.isoformat(),
    }


async def _document_ids_of(db: AsyncSession, summary_id: str) -> list[str]:
    return list(
        (
            await db.execute(
                select(SummaryDocument.document_id).where(
                    SummaryDocument.summary_id == summary_id
                )
            )
        ).scalars()
    )


class CreateSummaryBody(BaseModel):
    document_ids: list[str]


@router.post("/summaries", status_code=status.HTTP_202_ACCEPTED)
async def create_summary(
    body: CreateSummaryBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Cria um Summary em ``pending`` e enfileira o job.

    Valida posse e exige extração de texto de cada documento (retorna 409 se
    algum ainda estiver ``pending``/``failed`` na extração).
    """
    doc_ids = list(dict.fromkeys(body.document_ids))
    if not doc_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selecione pelo menos 1 documento")

    docs = list(
        (
            await db.execute(
                select(Document).where(
                    Document.id.in_(doc_ids), Document.user_id == current_user.id
                )
            )
        ).scalars()
    )
    owned = {d.id for d in docs}
    missing = [d for d in doc_ids if d not in owned]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Documentos não encontrados: {missing}")
    not_ready = [d.filename for d in docs if d.extraction_status != "done" or not d.extracted_key]
    if not_ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Extraia o texto antes de resumir: {not_ready}",
        )

    summary = Summary(user_id=current_user.id, status="pending")
    db.add(summary)
    await db.flush()
    for d in doc_ids:
        db.add(SummaryDocument(summary_id=summary.id, document_id=d))
    await db.commit()
    await db.refresh(summary)

    try:
        await enqueue_summary(summary.id)
    except Exception:
        # Se a fila estiver indisponível, marca já como failed pra não deixar o
        # front no polling infinito. Um retry manual (delete + recreate) resolve.
        logger.exception("Falha ao enfileirar summary %s", summary.id)
        summary.status = "failed"
        summary.error = "Fila indisponível — tente novamente."
        await db.commit()

    return _to_dict(summary, doc_ids)


class PollSummariesBody(BaseModel):
    ids: list[str]


@router.post("/summaries/status")
async def poll_summaries(
    body: PollSummariesBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """Status atual dos summaries pedidos (poll do front, a cada 3s)."""
    ids = list(dict.fromkeys(body.ids))
    if not ids:
        return []
    rows = (
        await db.execute(
            select(Summary).where(
                Summary.id.in_(ids), Summary.user_id == current_user.id
            )
        )
    ).scalars().all()
    return [
        {"id": s.id, "status": s.status, "error": s.error, "title": s.title}
        for s in rows
    ]


@router.get("/summaries")
async def list_summaries(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """Lista os resumos do usuário, mais recentes primeiro."""
    rows = (
        await db.execute(
            select(Summary)
            .where(Summary.user_id == current_user.id)
            .order_by(Summary.created_at.desc())
        )
    ).scalars().all()
    out = []
    for s in rows:
        doc_ids = await _document_ids_of(db, s.id)
        out.append(_to_dict(s, doc_ids))
    return out


@router.get("/summaries/{summary_id}")
async def get_summary(
    summary_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Detalhe completo de um resumo (view de detalhamento).

    Inclui ``documents = [{id, filename}]`` pra UI renderizar os chips sem
    outra requisição.
    """
    summary = await db.get(Summary, summary_id)
    if not summary or summary.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resumo não encontrado")
    doc_ids = await _document_ids_of(db, summary_id)
    by_id: dict[str, str] = {}
    if doc_ids:
        rows = await db.execute(
            select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
        )
        by_id = dict(rows.all())
    payload = _to_dict(summary, doc_ids)
    payload["documents"] = [
        {"id": d, "filename": by_id.get(d, "documento")} for d in doc_ids
    ]
    return payload


@router.delete("/summaries/{summary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_summary(
    summary_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    summary = await db.get(Summary, summary_id)
    if not summary or summary.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resumo não encontrado")
    await db.delete(summary)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
