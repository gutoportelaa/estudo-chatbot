"""Rotas de documentos PDF — upload, listagem e fluxo presigned (RF-002/RF-003)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import Document, User
from ..storage import build_key, get_storage

router = APIRouter(prefix="/documents", tags=["documents"])

PDF_MAGIC = b"%PDF-"


def _validate_pdf(filename: str, content_type: str, head: bytes, size: int) -> None:
    """Valida extensão, MIME, magic bytes e tamanho (RF-002)."""
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Apenas arquivos .pdf são aceitos")
    if content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Content-Type inválido para PDF")
    if not head.startswith(PDF_MAGIC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conteúdo não é um PDF válido")
    if size > max_bytes:
        raise HTTPException(
            413,  # Content Too Large
            f"Arquivo excede o limite de {settings.max_upload_mb} MB",
        )


def _to_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "size_bytes": doc.size_bytes,
        "content_type": doc.content_type,
        "page_count": doc.page_count,
        "created_at": doc.created_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Upload multipart de um PDF (caminho usado em dev/local e como fallback).

    Em produção com S3, prefira o fluxo presigned (`/documents/presign`) para o
    binário não passar pela API.
    """
    data = await file.read()
    _validate_pdf(file.filename or "", file.content_type or "", data[:5], len(data))

    storage = get_storage()
    key = build_key(current_user.id, file.filename or "documento.pdf")
    await run_in_threadpool(storage.save, key, data)

    doc = Document(
        user_id=current_user.id,
        filename=file.filename or "documento.pdf",
        size_bytes=len(data),
        content_type="application/pdf",
        storage_backend=storage.name,
        storage_key=key,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _to_dict(doc)


@router.get("")
async def list_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """Lista os documentos do usuário autenticado (base para RF-003/C2)."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return [_to_dict(d) for d in result.scalars().all()]


# ---------------------------------------------------------------------------
# Fluxo presigned (produção S3): o browser sobe o PDF direto no bucket.
# ---------------------------------------------------------------------------


class PresignRequest(BaseModel):
    filename: str
    content_type: str = "application/pdf"
    size_bytes: int


class ConfirmRequest(BaseModel):
    storage_key: str
    filename: str
    size_bytes: int


@router.post("/presign")
async def presign_upload(
    body: PresignRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Retorna uma URL assinada de PUT para o S3. Valida nome/tamanho antes."""
    storage = get_storage()
    if not storage.supports_presign:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Backend de armazenamento atual não suporta presigned URLs (use POST /documents)",
        )
    _validate_pdf(body.filename, body.content_type, PDF_MAGIC, body.size_bytes)

    key = build_key(current_user.id, body.filename)
    url = await run_in_threadpool(storage.presigned_put_url, key, body.content_type)
    return {"upload_url": url, "storage_key": key, "method": "PUT"}


@router.post("/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_upload(
    body: ConfirmRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Persiste os metadados após o upload presigned ter sido concluído no S3."""
    storage = get_storage()
    # A chave precisa pertencer ao usuário (prefixo <user_id>/).
    if not body.storage_key.startswith(f"{current_user.id}/"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chave de armazenamento não pertence ao usuário")

    doc = Document(
        user_id=current_user.id,
        filename=body.filename,
        size_bytes=body.size_bytes,
        content_type="application/pdf",
        storage_backend=storage.name,
        storage_key=body.storage_key,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _to_dict(doc)
