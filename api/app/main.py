"""Aplicação FastAPI: inicialização do banco e rotas base.

As rotas de autenticação, sessões e chat serão adicionadas nas issues seguintes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 — registra os modelos antes do create_all
from .config import get_settings
from .database import Base, engine
from .routers import auth as auth_router


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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": _settings.gemini_model}
