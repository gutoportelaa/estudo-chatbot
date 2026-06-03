"""Modelos de entrada/saída da API."""

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID único da sessão do usuário")
    message: str = Field(..., min_length=1, description="Mensagem do usuário")


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[Message]
