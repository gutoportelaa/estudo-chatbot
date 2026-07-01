"""Modelos SQLAlchemy: User, Session e Message."""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Coluna de embedding: ``vector`` (dimensionless) no Postgres/pgvector; cai para
# JSON em SQLite (testes). Sem dimensão fixa para aceitar qualquer provedor de
# embeddings (Ollama 3072, Bedrock Titan 1536, Gemini 768) — issue #34.
_EmbeddingType = Vector().with_variant(JSON, "sqlite")


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
    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    summaries: Mapped[list["Summary"]] = relationship(
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


# --------------------------------------------------------------------------
# Entrega final — documentos PDF e resumos (issue A1 / RF-TEC-002)
# --------------------------------------------------------------------------


class Document(Base):
    """Metadados de um PDF enviado pelo usuário.

    O binário **não** fica no banco: é armazenado no S3 (produção) ou no
    filesystem (dev). Aqui guardamos só a referência (`storage_backend` +
    `storage_key`) e os metadados.
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nome original do arquivo enviado.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/pdf")
    # Onde o binário vive: "s3" | "local".
    storage_backend: Mapped[str] = mapped_column(String(16), nullable=False, default="s3")
    # Chave no S3 ou caminho no filesystem.
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # Páginas do PDF (preenchido na extração; pode ser nulo até processar).
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Extração de texto (issue #33): "pending" | "done" | "failed".
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # Chave do artefato de texto extraído (storage); nulo até extrair.
    extracted_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="documents")
    summaries: Mapped[list["Summary"]] = relationship(
        secondary="summary_documents", back_populates="documents"
    )


class Summary(Base):
    """Resumo gerado por LLM — individual (1 doc) ou consolidado (N docs)."""

    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "single" (RF-004) | "consolidated" (RF-005).
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="single")
    # Modelo/provedor que gerou o resumo (auditoria).
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="summaries")
    documents: Mapped[list["Document"]] = relationship(
        secondary="summary_documents", back_populates="summaries"
    )


class SummaryDocument(Base):
    """Associação N:N entre resumos e documentos.

    Um resumo consolidado liga-se a vários documentos; um documento pode
    aparecer em vários resumos.
    """

    __tablename__ = "summary_documents"

    summary_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("summaries.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )


class Chunk(Base):
    """Trecho (chunk) de um documento, vetorizado para recuperação (RAG, #34).

    O texto extraído (#33) é dividido em chunks com overlap; cada um guarda seu
    ``embedding`` em pgvector. A busca por similaridade recupera os top-k trechos
    relevantes a uma pergunta, que entram no bloco de RAG do Context Assembler.
    """

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(_EmbeddingType, nullable=False)
    # Proveniência do embedding: embeddings de modelos diferentes vivem em
    # espaços incompatíveis. Guardamos provider/modelo para (a) filtrar a busca
    # ao modelo vigente e (b) detectar chunks obsoletos a re-vetorizar.
    embedding_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
