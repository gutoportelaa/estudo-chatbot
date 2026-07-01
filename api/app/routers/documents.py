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
from ..tools import fit_to_budget
from ..tools.extraction import extract_pdf, get_ocr_engine
from ..tools.rag import get_embedder, index_document

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
        "extraction_status": doc.extraction_status,
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


@router.post("/{document_id}/extract")
async def extract_document(
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Extrai o texto de um documento (PyMuPDF nativo, OCR se escaneado — #33).

    O texto completo é persistido como artefato recuperável (storage); só um
    resumo dentro da cota entra no contexto (contrato de ferramentas, #32). A
    extração roda em threadpool por ser CPU-bound/bloqueante.
    """
    settings = get_settings()
    doc = await db.get(Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")

    storage = get_storage()
    try:
        data = await run_in_threadpool(storage.load, doc.storage_key)
        ocr = get_ocr_engine(settings)
        result = await run_in_threadpool(
            extract_pdf,
            data,
            ocr=ocr,
            ocr_min_chars_per_page=settings.extraction_ocr_min_chars_per_page,
        )
    except Exception as exc:  # extração falhou: registra e sinaliza sem quebrar
        doc.extraction_status = "failed"
        await db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Falha na extração: {exc}")

    # Persiste o texto completo como artefato (nunca vai cru ao contexto).
    text_key = doc.storage_key.rsplit(".", 1)[0] + ".txt"
    await run_in_threadpool(storage.save, text_key, result.text.encode("utf-8"))

    doc.page_count = result.page_count
    doc.extracted_key = text_key
    doc.extraction_status = "done"
    await db.commit()
    await db.refresh(doc)

    # Resumo dentro da cota da ferramenta; o texto completo fica no artefato.
    tool = fit_to_budget(
        result.text,
        artifact_ref=doc.id,
        max_tokens=settings.tool_output_max_tokens,
    )
    return {
        "document_id": doc.id,
        "page_count": result.page_count,
        "engine": result.engine,
        "ocr_used": result.ocr_used,
        "chars": len(result.text),
        "extraction_status": doc.extraction_status,
        "summary_for_context": tool.summary_for_context,
        "artifact_ref": tool.artifact_ref,
        "tokens": tool.tokens,
        "truncated": tool.truncated,
    }


@router.post("/{document_id}/index")
async def index_document_endpoint(
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Indexa o texto extraído para RAG: chunks + embeddings em pgvector (#34).

    Requer extração prévia (``POST /documents/{id}/extract``). Reindexa de forma
    idempotente (substitui os chunks anteriores do documento).
    """
    settings = get_settings()
    doc = await db.get(Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    if doc.extraction_status != "done" or not doc.extracted_key:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Documento ainda não foi extraído (rode POST /documents/{id}/extract antes)",
        )

    storage = get_storage()
    text = (await run_in_threadpool(storage.load, doc.extracted_key)).decode("utf-8")
    n_chunks = await index_document(
        db,
        get_embedder(settings),
        document_id=doc.id,
        user_id=current_user.id,
        text=text,
        settings=settings,
    )
    return {"document_id": doc.id, "chunks_indexed": n_chunks}


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
