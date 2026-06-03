"""Aplicação FastAPI: cria sessões, conversa (SSE) e expõe histórico/health.

Multiusuário: o app é assíncrono e cada requisição carrega seu `session_id`.
O checkpointer SQLite do LangGraph isola o histórico por `thread_id`, garantindo
que cada resposta volte apenas para a sessão/usuário correto.
"""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .chat import get_history, stream_chat
from .config import get_settings
from .graph import build_graph
from .schemas import ChatRequest, HistoryResponse, SessionResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Mantém o checkpointer aberto durante todo o ciclo de vida do app.
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(title="ThinkAI API", version="0.1.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": _settings.ollama_model}


@app.post("/session", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    """Gera um ID único para uma nova sessão de usuário."""
    return SessionResponse(session_id=str(uuid.uuid4()))


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """Recebe uma mensagem e devolve a resposta em streaming (SSE)."""
    if not req.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id é obrigatório")

    generator = stream_chat(app.state.graph, req.session_id, req.message)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/history/{session_id}", response_model=HistoryResponse)
async def history(session_id: str) -> HistoryResponse:
    """Retorna o histórico persistido de uma sessão."""
    messages = await get_history(app.state.graph, session_id)
    return HistoryResponse(session_id=session_id, messages=messages)
