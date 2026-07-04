"""Rotas de resumo de documentos — individual e consolidado (issues #44/#45, EPIC C).

O usuário seleciona 1 ou mais documentos na Biblioteca; 1 documento gera um
resumo ``single``, 2+ geram um resumo ``consolidated`` (síntese integrando
todos). O texto usado é o já extraído (``POST /documents/{id}/extract``) —
nunca o PDF cru.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..llm import resolve_client
from ..models import Document, Summary, User
from ..storage import get_storage
from ..tools.document_summary import generate_summary

logger = logging.getLogger("thinkai.summaries")

router = APIRouter(prefix="/summaries", tags=["summaries"])


def _to_dict(summary: Summary) -> dict:
    return {
        "id": summary.id,
        "kind": summary.kind,
        "llm_model": summary.llm_model,
        "content": summary.content,
        "document_ids": [d.id for d in summary.documents],
        "created_at": summary.created_at.isoformat(),
    }


class CreateSummaryRequest(BaseModel):
    document_ids: list[str]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_summary(
    body: CreateSummaryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Gera um resumo a partir de 1+ documentos do usuário (kind inferido pela quantidade)."""
    doc_ids = list(dict.fromkeys(body.document_ids))  # dedup preservando ordem
    if not doc_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe ao menos um documento")

    result = await db.execute(
        select(Document).where(Document.id.in_(doc_ids), Document.user_id == current_user.id)
    )
    docs = list(result.scalars().all())
    if len(docs) != len(doc_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Um ou mais documentos não encontrados")

    not_extracted = [d.filename for d in docs if d.extraction_status != "done" or not d.extracted_key]
    if not_extracted:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Documentos ainda não extraídos: {', '.join(not_extracted)}",
        )

    settings = get_settings()
    client, model, _ = resolve_client(settings)
    storage = get_storage()

    documents_text: list[tuple[str, str]] = []
    for doc in docs:
        data = await run_in_threadpool(storage.load, doc.extracted_key)
        documents_text.append((doc.filename, data.decode("utf-8")))

    kind: Literal["single", "consolidated"] = "single" if len(docs) == 1 else "consolidated"
    try:
        content = await generate_summary(
            client=client,
            model=model,
            kind=kind,
            documents=documents_text,
            max_input_tokens=settings.tool_output_max_tokens,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Falha ao gerar resumo: {exc}")

    summary = Summary(user_id=current_user.id, kind=kind, llm_model=model, content=content)
    summary.documents = docs
    db.add(summary)
    await db.commit()
    return _to_dict(summary)


@router.get("")
async def list_summaries_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: Literal["single", "consolidated"] | None = None,
) -> list[dict]:
    """Resumos do usuário, mais recentes primeiro; filtra por ``kind`` se informado."""
    stmt = (
        select(Summary)
        .where(Summary.user_id == current_user.id)
        .options(selectinload(Summary.documents))
        .order_by(Summary.created_at.desc())
    )
    if kind:
        stmt = stmt.where(Summary.kind == kind)
    result = await db.execute(stmt)
    return [_to_dict(s) for s in result.scalars().all()]


@router.get("/{summary_id}")
async def get_summary(
    summary_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(Summary).where(Summary.id == summary_id).options(selectinload(Summary.documents))
    )
    summary = result.scalar_one_or_none()
    if not summary or summary.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resumo não encontrado")
    return _to_dict(summary)
