from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.errors.already_exists_error import AlreadyExistsError
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.sessions.base_session_service import BaseSessionService
from google.adk.sessions.base_session_service import GetSessionConfig
from google.adk.sessions.base_session_service import ListSessionsResponse
from google.adk.sessions.session import Session
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from .config import get_settings
from .database import AsyncSessionLocal
from .models import Message
from .models import Session as SessionRow

APP_NAME = "thinkai"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event_text(event: Event) -> str:
    output = getattr(event, "output", None)
    if isinstance(output, str) and output.strip():
        return output.strip()

    content = getattr(event, "content", None)
    if not content or not getattr(content, "parts", None):
        return ""

    texts: list[str] = []
    for part in content.parts:
        text = getattr(part, "text", None)
        if text:
            texts.append(text)
    return "".join(texts).strip()


def _title_from_message_text(text: str) -> str | None:
    compact = " ".join(text.split())
    if not compact:
        return None
    return compact[:120]


def _event_to_history_message(event: Event) -> dict[str, str] | None:
    role = getattr(event, "author", None)
    if role == "user":
        normalized_role = "user"
    else:
        normalized_role = "assistant"

    text = _event_text(event)
    if not text:
        return None

    return {"role": normalized_role, "content": text}


class DatabaseSessionService(BaseSessionService):
    async def _get_session_row(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_id: str,
    ) -> SessionRow | None:
        return await db.scalar(
            select(SessionRow).where(
                SessionRow.user_id == user_id,
                SessionRow.id == session_id,
            )
        )

    async def _ensure_session_row(self, db: AsyncSession, session: Session) -> SessionRow:
        row = await self._get_session_row(
            db, user_id=session.user_id, session_id=session.id
        )
        if row is not None:
            return row

        row = SessionRow(
            id=session.id,
            user_id=session.user_id,
            title=None,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        db.add(row)
        await db.flush()
        return row

    async def _load_events(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> list[Event]:
        stmt = select(Message).where(Message.session_id == session_id)
        stmt = stmt.order_by(Message.created_at.asc(), Message.id.asc())
        rows = list((await db.scalars(stmt)).all())

        if config and config.after_timestamp is not None:
            after_dt = datetime.fromtimestamp(config.after_timestamp, tz=timezone.utc)
            rows = [row for row in rows if row.created_at >= after_dt]

        if config and config.num_recent_events is not None:
            if config.num_recent_events == 0:
                rows = []
            else:
                rows = rows[-config.num_recent_events :]

        events: list[Event] = []
        for row in rows:
            try:
                events.append(Event.model_validate_json(row.content))
            except Exception:
                try:
                    payload = json.loads(row.content)
                except json.JSONDecodeError:
                    continue
                events.append(Event.model_validate(payload))
        return events

    def _row_to_session(self, row: SessionRow, *, events: list[Event]) -> Session:
        return Session(
            app_name=APP_NAME,
            user_id=row.user_id,
            id=row.id,
            state={},
            events=events,
            last_update_time=row.updated_at.replace(tzinfo=timezone.utc).timestamp(),
        )

    @override
    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        del app_name
        session_id = session_id.strip() if session_id else ""
        if not session_id:
            session_id = str(uuid.uuid4())

        now = _utc_now()
        async with AsyncSessionLocal() as db:
            existing = await self._get_session_row(db, user_id=user_id, session_id=session_id)
            if existing is not None:
                raise AlreadyExistsError(f"Session with id {session_id} already exists.")

            db.add(
                SessionRow(
                    id=session_id,
                    user_id=user_id,
                    title=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            await db.commit()

        return Session(
            app_name=APP_NAME,
            user_id=user_id,
            id=session_id,
            state=dict(state or {}),
            events=[],
            last_update_time=now.timestamp(),
        )

    @override
    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        del app_name
        async with AsyncSessionLocal() as db:
            row = await self._get_session_row(db, user_id=user_id, session_id=session_id)
            if row is None:
                return None
            events = await self._load_events(db, session_id=session_id, config=config)
            return self._row_to_session(row, events=events)

    @override
    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        del app_name
        async with AsyncSessionLocal() as db:
            stmt = select(SessionRow).order_by(
                SessionRow.updated_at.desc(), SessionRow.created_at.desc()
            )
            if user_id is not None:
                stmt = stmt.where(SessionRow.user_id == user_id)
            rows = list((await db.scalars(stmt)).all())
            return ListSessionsResponse(
                sessions=[self._row_to_session(row, events=[]) for row in rows]
            )

    @override
    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        del app_name
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Message).where(Message.session_id == session_id))
            await db.execute(
                delete(SessionRow).where(
                    SessionRow.user_id == user_id,
                    SessionRow.id == session_id,
                )
            )
            await db.commit()

    @override
    async def get_user_state(self, *, app_name: str, user_id: str) -> dict[str, Any]:
        del app_name, user_id
        return {}

    @override
    async def append_event(self, session: Session, event: Event) -> Event:
        if event.partial:
            return event

        await super().append_event(session=session, event=event)
        event_timestamp_value = getattr(event, "timestamp", None) or _utc_now().timestamp()
        event_timestamp = datetime.fromtimestamp(event_timestamp_value, tz=timezone.utc)

        async with AsyncSessionLocal() as db:
            row = await self._ensure_session_row(db, session)
            row.updated_at = event_timestamp

            if row.title is None:
                text = _event_text(event)
                if text:
                    row.title = _title_from_message_text(text)

            db.add(
                Message(
                    session_id=session.id,
                    role="user" if getattr(event, "author", None) == "user" else "assistant",
                    content=event.model_dump_json(exclude_none=True),
                    created_at=event_timestamp,
                )
            )
            await db.commit()

        session.last_update_time = event_timestamp_value
        return event


@dataclass(frozen=True)
class ChatRuntime:
    runner: Runner
    session_service: DatabaseSessionService


@lru_cache(maxsize=1)
def get_runtime() -> ChatRuntime:
    settings = get_settings()
    if settings.gemini_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.gemini_api_key)
        os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)

    agent = LlmAgent(
        name="thinkai",
        model=settings.gemini_model,
        instruction=settings.system_prompt,
    )
    session_service = DatabaseSessionService()
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    return ChatRuntime(runner=runner, session_service=session_service)


async def get_or_create_session(*, user_id: str, session_id: str) -> Session:
    runtime = get_runtime()
    session = await runtime.session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if session is not None:
        return session
    return await runtime.session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )


async def list_sessions_for_user(user_id: str) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        stmt = select(SessionRow).where(SessionRow.user_id == user_id).order_by(
            SessionRow.updated_at.desc(), SessionRow.created_at.desc()
        )
        rows = list((await db.scalars(stmt)).all())
        if not rows:
            return []

        session_ids = [row.id for row in rows]
        count_stmt = (
            select(Message.session_id, func.count(Message.id))
            .where(Message.session_id.in_(session_ids))
            .group_by(Message.session_id)
        )
        counts = {session_id: int(count or 0) for session_id, count in (await db.execute(count_stmt)).all()}

        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "title": row.title,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "message_count": counts.get(row.id, 0),
            }
            for row in rows
        ]


async def load_history_for_session(*, user_id: str, session_id: str) -> list[dict[str, str]]:
    runtime = get_runtime()
    session = await runtime.session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        return []

    history: list[dict[str, str]] = []
    for event in session.events:
        message = _event_to_history_message(event)
        if message is not None:
            history.append(message)
    return history
