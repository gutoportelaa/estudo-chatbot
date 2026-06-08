from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..adk_runtime import APP_NAME
from ..adk_runtime import get_runtime
from ..adk_runtime import list_sessions_for_user
from ..adk_runtime import load_history_for_session
from ..auth import get_current_user
from ..models import User

router = APIRouter(tags=["sessions"])


class SessionCreateResponse(BaseModel):
    session_id: str


class SessionSummary(BaseModel):
    id: str
    user_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("/session", response_model=SessionCreateResponse)
@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    current_user: User = Depends(get_current_user),
) -> SessionCreateResponse:
    session = await get_runtime().session_service.create_session(
        app_name=APP_NAME,
        user_id=current_user.id,
        session_id=str(uuid.uuid4()),
    )
    return SessionCreateResponse(session_id=session.id)


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    current_user: User = Depends(get_current_user),
) -> list[SessionSummary]:
    summaries = await list_sessions_for_user(current_user.id)
    return [SessionSummary(**summary) for summary in summaries]


@router.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
) -> HistoryResponse:
    session = await get_runtime().session_service.get_session(
        app_name=APP_NAME,
        user_id=current_user.id,
        session_id=session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    messages = await load_history_for_session(user_id=current_user.id, session_id=session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[HistoryMessage(**message) for message in messages],
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    runtime = get_runtime()
    existing = await runtime.session_service.get_session(
        app_name=APP_NAME,
        user_id=current_user.id,
        session_id=session_id,
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    await runtime.session_service.delete_session(
        app_name=APP_NAME,
        user_id=current_user.id,
        session_id=session_id,
    )


@router.post("/chat")
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    runtime = get_runtime()
    session = await get_or_create_session(user_id=current_user.id, session_id=body.session_id)

    async def event_stream():
        try:
            from google.genai import types

            user_message = types.Content(
                role="user",
                parts=[types.Part.from_text(text=body.message)],
            )

            async for event in runtime.runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=user_message,
            ):
                content = getattr(event, "content", None)
                if not content or not getattr(content, "parts", None):
                    continue

                chunks: list[str] = []
                for part in content.parts:
                    text = getattr(part, "text", None)
                    if text:
                        chunks.append(text)
                if not chunks:
                    continue

                payload = "".join(chunks).replace("\r", "").replace("\n", "\\n")
                yield f"data: {payload}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as exc:  # pragma: no cover - streamed error path
            message = str(exc).replace("\r", " ").replace("\n", " ")
            yield f"data: [ERROR] {message}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
