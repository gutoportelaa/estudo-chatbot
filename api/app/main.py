"""Aplicação FastAPI: inicialização do banco e montagem das rotas."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 — registra os modelos antes do create_all
from .config import get_settings
from .database import Base, engine
from .routers import auth as auth_router
from .routers import chat as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="ThinkAI API", version="0.2.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router.router)
app.include_router(chat_router.router)


@app.get("/health")
async def health() -> dict:
    from .llm import active_model
    return {"status": "ok", "provider": _settings.llm_provider, "model": active_model()}
