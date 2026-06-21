"""Modelos SQLAlchemy: User, Session e Message."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="messages")


class ConversationSummary(Base):
    """Resumo incremental do histórico de uma sessão.

    Cada linha é uma compactação: o resumo vigente é o registro mais recente
    da sessão. O conjunto de linhas funciona como **log de auditoria** —
    permite visualizar a evolução das sumarizações (janela deslizante,
    sumarização incremental e recompactação resumo-de-resumo).
    """

    __tablename__ = "conversation_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Texto do resumo vigente após esta compactação.
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Quantas mensagens (do início) já estão condensadas neste resumo.
    covered_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Quantas mensagens novas foram dobradas no resumo nesta compactação.
    source_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Estimativa de tokens do resumo resultante (para o disparo de recompactação).
    summary_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Gatilho desta compactação: "window_overflow" | "recompaction".
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="window_overflow")
    # Modelo/provedor que gerou o resumo (auditoria).
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship()
