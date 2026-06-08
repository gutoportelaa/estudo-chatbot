from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from google.adk.errors.already_exists_error import AlreadyExistsError
from google.adk.events.event import Event
from google.adk.sessions.base_session_service import (
    BaseSessionService,
    GetSessionConfig,
    ListSessionsResponse,
)
from google.adk.sessions.session import Session
from google.genai import types as genai_types
from sqlalchemy import delete, select
from typing_extensions import override

from .database import AsyncSessionLocal
from .models import Message
from .models import Session as SessionRow
from .runner import APP_NAME


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event_text(event: Event) -> str:
    content = getattr(event, "content", None)
    if not content or not getattr(content, "parts", None):
        return ""
    return "".join(p.text for p in content.parts if getattr(p, "text", None)).strip()


def _title_from(text: str) -> str | None:
    compact = " ".join(text.split())
    return compact[:120] if compact else None


class DatabaseSessionService(BaseSessionService):
    async def _get_row(self, db, *, user_id: str, session_id: str) -> SessionRow | None:
        return await db.scalar(
            select(SessionRow).where(
                SessionRow.user_id == user_id,
                SessionRow.id == session_id,
            )
        )

    async def _ensure_row(self, db, session: Session) -> SessionRow:
        row = await self._get_row(db, user_id=session.user_id, session_id=session.id)
        if row is not None:
            return row
        now = _utc_now()
        row = SessionRow(id=session.id, user_id=session.user_id, created_at=now, updated_at=now)
        db.add(row)
        await db.flush()
        return row

    async def _load_events(
        self,
        db,
        *,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> list[Event]:
        stmt = select(Message).where(Message.session_id == session_id).order_by(
            Message.created_at.asc(), Message.id.asc()
        )
        rows = list((await db.scalars(stmt)).all())

        if config and config.after_timestamp is not None:
            cutoff = datetime.fromtimestamp(config.after_timestamp, tz=timezone.utc)
            rows = [r for r in rows if r.created_at >= cutoff]

        if config and config.num_recent_events is not None:
            rows = rows[-config.num_recent_events:] if config.num_recent_events else []

        events: list[Event] = []
        for row in rows:
            role = "user" if row.role == "user" else "model"
            author = "user" if row.role == "user" else APP_NAME
            content = genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=row.content)],
            )
            events.append(Event(author=author, content=content, partial=False))
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
        session_id = (session_id or "").strip() or str(uuid.uuid4())
        now = _utc_now()
        async with AsyncSessionLocal() as db:
            existing = await self._get_row(db, user_id=user_id, session_id=session_id)
            if existing is not None:
                raise AlreadyExistsError(f"Session {session_id} already exists.")
            db.add(SessionRow(id=session_id, user_id=user_id, created_at=now, updated_at=now))
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
        async with AsyncSessionLocal() as db:
            row = await self._get_row(db, user_id=user_id, session_id=session_id)
            if row is None:
                return None
            events = await self._load_events(db, session_id=session_id, config=config)
            return self._row_to_session(row, events=events)

    @override
    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        async with AsyncSessionLocal() as db:
            stmt = select(SessionRow).order_by(SessionRow.updated_at.desc())
            if user_id is not None:
                stmt = stmt.where(SessionRow.user_id == user_id)
            rows = list((await db.scalars(stmt)).all())
            return ListSessionsResponse(
                sessions=[self._row_to_session(r, events=[]) for r in rows]
            )

    @override
    async def delete_session(self, *, app_name: str, user_id: str, session_id: str) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Message).where(Message.session_id == session_id))
            await db.execute(
                delete(SessionRow).where(
                    SessionRow.user_id == user_id, SessionRow.id == session_id
                )
            )
            await db.commit()

    @override
    async def get_user_state(self, *, app_name: str, user_id: str) -> dict[str, Any]:
        return {}

    @override
    async def append_event(self, session: Session, event: Event) -> Event:
        if event.partial:
            return event

        text = _event_text(event)
        if not text:
            return await super().append_event(session=session, event=event)

        await super().append_event(session=session, event=event)

        ts_value = getattr(event, "timestamp", None) or _utc_now().timestamp()
        ts = datetime.fromtimestamp(ts_value, tz=timezone.utc)
        role = "user" if getattr(event, "author", None) == "user" else "assistant"

        async with AsyncSessionLocal() as db:
            row = await self._ensure_row(db, session)
            row.updated_at = ts
            if row.title is None and role == "user":
                row.title = _title_from(text)
            db.add(Message(session_id=session.id, role=role, content=text, created_at=ts))
            await db.commit()

        session.last_update_time = ts_value
        return event
