from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from google.adk.errors.already_exists_error import AlreadyExistsError
from google.genai import types as genai_types
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..context import list_summaries
from ..database import get_db
from ..models import Document, Message, Session, SessionDocument, User
from ..runner import APP_NAME, get_runner

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SendMessageBody(BaseModel):
    content: str
    web_search: bool = False  # toggle 🔎 do chat (#35)


class RenameSessionBody(BaseModel):
    title: str


class CreateSessionBody(BaseModel):
    # Documentos selecionados na Biblioteca para escopar o RAG desta conversa.
    document_ids: list[str] = []


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: CreateSessionBody | None = None,
) -> dict:
    session = Session(user_id=current_user.id)
    db.add(session)
    await db.flush()

    # Escopo de documentos (Biblioteca): valida posse e associa à sessão.
    doc_ids = list(dict.fromkeys(body.document_ids)) if body else []
    if doc_ids:
        owned = set(
            (
                await db.execute(
                    select(Document.id).where(
                        Document.id.in_(doc_ids), Document.user_id == current_user.id
                    )
                )
            ).scalars()
        )
        missing = [d for d in doc_ids if d not in owned]
        if missing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Documentos não encontrados: {missing}")
        for d in doc_ids:
            db.add(SessionDocument(session_id=session.id, document_id=d))

    await db.commit()
    await db.refresh(session)

    runner = get_runner()
    try:
        await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=current_user.id,
            session_id=session.id,
        )
    except AlreadyExistsError:
        pass

    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "document_ids": doc_ids,
    }


@router.get("")
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    result = await db.execute(
        select(Session)
        .where(Session.user_id == current_user.id)
        .order_by(Session.updated_at.desc())
    )
    return [
        {"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()}
        for s in result.scalars().all()
    ]


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return [
        {"id": m.id, "role": m.role, "content": m.content, "sources": m.sources}
        for m in result.scalars().all()
    ]


@router.get("/{session_id}/summaries")
async def get_summaries(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """Log de auditoria: histórico de compactações/sumarizações da sessão."""
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")

    summaries = await list_summaries(db, session_id)
    return [
        {
            "id": s.id,
            "summary": s.summary,
            "covered_message_count": s.covered_message_count,
            "source_message_count": s.source_message_count,
            "summary_tokens": s.summary_tokens,
            "trigger": s.trigger,
            "model": s.model,
            "created_at": s.created_at.isoformat(),
        }
        for s in summaries
    ]


class AttachDocumentsBody(BaseModel):
    document_ids: list[str]


async def _session_document_ids(db: AsyncSession, session_id: str) -> list[str]:
    return list(
        (
            await db.execute(
                select(SessionDocument.document_id).where(SessionDocument.session_id == session_id)
            )
        ).scalars()
    )


@router.get("/{session_id}/documents")
async def get_session_documents(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Documentos escopados à conversa (Biblioteca / clipe do chat)."""
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessão não encontrada")
    return {"document_ids": await _session_document_ids(db, session_id)}


@router.post("/{session_id}/documents")
async def attach_session_documents(
    session_id: str,
    body: AttachDocumentsBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Anexa documentos a uma conversa existente (clipe do chat) — RAG passa a
    considerá-los. Valida posse e ignora os já anexados."""
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessão não encontrada")

    doc_ids = list(dict.fromkeys(body.document_ids))
    owned = set(
        (
            await db.execute(
                select(Document.id).where(
                    Document.id.in_(doc_ids), Document.user_id == current_user.id
                )
            )
        ).scalars()
    )
    missing = [d for d in doc_ids if d not in owned]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Documentos não encontrados: {missing}")

    existing = set(await _session_document_ids(db, session_id))
    for d in doc_ids:
        if d not in existing:
            db.add(SessionDocument(session_id=session_id, document_id=d))
    await db.commit()
    return {"document_ids": await _session_document_ids(db, session_id)}


@router.delete("/{session_id}/documents/{document_id}")
async def detach_session_document(
    session_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Remove um documento do escopo da conversa. O RAG deixa de considerá-lo;
    o histórico já trocado permanece intacto."""
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessão não encontrada")
    await db.execute(
        delete(SessionDocument).where(
            SessionDocument.session_id == session_id,
            SessionDocument.document_id == document_id,
        )
    )
    await db.commit()
    return {"document_ids": await _session_document_ids(db, session_id)}


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")
    await db.delete(session)
    await db.commit()

    runner = get_runner()
    adk_session = await runner.session_service.get_session(
        app_name=APP_NAME, user_id=current_user.id, session_id=session_id
    )
    if adk_session:
        await runner.session_service.delete_session(
            app_name=APP_NAME, user_id=current_user.id, session_id=session_id
        )


@router.patch("/{session_id}")
async def rename_session(
    session_id: str,
    body: RenameSessionBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")

    title = body.title.strip()
    session.title = title or None
    await db.commit()
    await db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
    }


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    body: SendMessageBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    session = await db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada")

    from ..config import get_settings
    from ..llm import stream_openai_compatible

    settings = get_settings()
    if settings.llm_provider.lower() in ("groq", "openrouter", "ollama"):
        generator = stream_openai_compatible(
            session_id=session_id, content=body.content, web_search=body.web_search
        )
    else:
        generator = _stream_adk(user_id=current_user.id, session_id=session_id, content=body.content)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_adk(
    user_id: str, session_id: str, content: str
) -> AsyncGenerator[str, None]:
    runner = get_runner()

    adk_session = await runner.session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if adk_session is None:
        try:
            adk_session = await runner.session_service.create_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
        except AlreadyExistsError:
            adk_session = await runner.session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )

    new_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=content)],
    )

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                if getattr(part, "text", None):
                    escaped = part.text.replace(chr(10), chr(92) + "n")
                    yield f"data: {escaped}\n\n"

        yield "data: [DONE]\n\n"
    except Exception as exc:
        msg = str(exc).replace("\n", " ")
        yield f"data: [ERROR] {msg}\n\n"
