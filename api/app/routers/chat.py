from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..config import get_settings
from ..database import AsyncSessionLocal, get_db
from ..models import Message, Session, User

router = APIRouter(prefix="/sessions", tags=["chat"])


class SessionOut(BaseModel):
    id: str
    title: str | None
    created_at: str
    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj: Session) -> "SessionOut":
        return cls(
            id=obj.id,
            title=obj.title,
            created_at=obj.created_at.isoformat(),
        )


class MessageOut(BaseModel):
    id: str
    role: str
    content: str


class SendMessageBody(BaseModel):
    content: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    session = Session(user_id=current_user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "title": session.title, "created_at": session.created_at.isoformat()}


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
    return [{"id": m.id, "role": m.role, "content": m.content} for m in result.scalars().all()]


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

    history_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    history = history_result.scalars().all()

    user_msg = Message(session_id=session_id, role="user", content=body.content)
    db.add(user_msg)
    if not session.title:
        session.title = body.content[:60]
    await db.commit()

    contents = [
        {"role": "user" if m.role == "user" else "model", "parts": [{"text": m.content}]}
        for m in history
    ]
    contents.append({"role": "user", "parts": [{"text": body.content}]})

    return StreamingResponse(
        _stream_gemini(session_id, contents),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_gemini(session_id: str, contents: list) -> AsyncGenerator[str, None]:
    from google import genai

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    full_text = ""
    async for chunk in client.aio.models.generate_content_stream(
        model=settings.gemini_model,
        contents=contents,
        config={"system_instruction": settings.system_prompt},
    ):
        if chunk.text:
            full_text += chunk.text
            yield f"data: {chunk.text.replace(chr(10), chr(92) + 'n')}\n\n"

    yield "data: [DONE]\n\n"

    async with AsyncSessionLocal() as save_db:
        save_db.add(Message(session_id=session_id, role="assistant", content=full_text))
        await save_db.commit()
