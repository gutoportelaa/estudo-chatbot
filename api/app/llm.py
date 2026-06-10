"""Streaming OpenAI-compatível para provedores Groq e OpenRouter."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import select

from .config import get_settings
from .database import AsyncSessionLocal
from .models import Message
from .models import Session as SessionRow

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
    },
}


def active_model() -> str:
    """Retorna o nome do modelo em uso (para o /health)."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if settings.llm_model:
        return settings.llm_model
    if provider in _PROVIDER_DEFAULTS:
        return _PROVIDER_DEFAULTS[provider]["model"]
    return settings.gemini_model


async def stream_openai_compatible(
    *,
    session_id: str,
    content: str,
) -> AsyncGenerator[str, None]:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    cfg = _PROVIDER_DEFAULTS[provider]

    api_key = settings.groq_api_key if provider == "groq" else settings.openrouter_api_key
    model = settings.llm_model or cfg["model"]

    # Carrega histórico e salva mensagem do usuário
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rows = list(
            (
                await db.execute(
                    select(Message)
                    .where(Message.session_id == session_id)
                    .order_by(Message.created_at)
                )
            ).scalars()
        )
        history = [{"role": m.role, "content": m.content} for m in rows]

        session_row = await db.get(SessionRow, session_id)
        if session_row and session_row.title is None:
            compact = " ".join(content.split())
            session_row.title = compact[:120] or None

        db.add(Message(session_id=session_id, role="user", content=content, created_at=now))
        await db.commit()

    messages = (
        [{"role": "system", "content": settings.system_prompt}]
        + history
        + [{"role": "user", "content": content}]
    )

    client = AsyncOpenAI(base_url=cfg["base_url"], api_key=api_key)
    full_text = ""

    try:
        async for chunk in await client.chat.completions.create(
            model=model, messages=messages, stream=True
        ):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                full_text += delta
                yield f"data: {delta.replace(chr(10), chr(92) + 'n')}\n\n"
    except Exception as exc:
        yield f"data: [ERROR] {str(exc)[:300]}\n\n"
        return

    yield "data: [DONE]\n\n"

    async with AsyncSessionLocal() as db:
        session_row = await db.get(SessionRow, session_id)
        if session_row:
            session_row.updated_at = datetime.now(timezone.utc)
        db.add(
            Message(
                session_id=session_id,
                role="assistant",
                content=full_text,
                created_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
