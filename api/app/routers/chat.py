from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from google.adk.errors.already_exists_error import AlreadyExistsError
from google.genai import types as genai_types
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import Message, Session, User
from ..runner import APP_NAME, get_runner

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SendMessageBody(BaseModel):
    content: str


class RenameSessionBody(BaseModel):
    title: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    session = Session(user_id=current_user.id)
    db.add(session)
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

    return StreamingResponse(
        _stream_adk(user_id=current_user.id, session_id=session_id, content=body.content),
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
