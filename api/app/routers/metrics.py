"""Tela de Consumo: agregação de tokens/custo por usuário (#37).

Lê a tabela ``turn_metrics`` (persistida a cada turno) e devolve os agregados que
a UI plota — inspirado no painel de uso do Google AI Studio: totais, série por
dia e quebra por modelo.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import TurnMetric, User

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/usage")
async def usage(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """Consumo do usuário nos últimos ``days`` dias: totais, por dia e por modelo."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base = select(TurnMetric).where(
        TurnMetric.user_id == current_user.id, TurnMetric.created_at >= since
    ).subquery()

    is_error = case((base.c.status == "error", 1), else_=0)
    used_rag = case((base.c.rag_tokens > 0, 1), else_=0)

    # Totais.
    totals_row = (
        await db.execute(
            select(
                func.count().label("requests"),
                func.coalesce(func.sum(base.c.input_tokens), 0),
                func.coalesce(func.sum(base.c.output_tokens), 0),
                func.coalesce(func.sum(base.c.cost_usd), 0.0),
                func.coalesce(func.avg(base.c.latency_ms), 0.0),
                func.coalesce(func.sum(is_error), 0),
                func.coalesce(func.sum(used_rag), 0),
            )
        )
    ).one()
    requests = int(totals_row[0])
    errors = int(totals_row[5])
    totals = {
        "requests": requests,
        "input_tokens": int(totals_row[1]),
        "output_tokens": int(totals_row[2]),
        "cost_usd": round(float(totals_row[3]), 6),
        "avg_latency_ms": round(float(totals_row[4]), 1),
        "errors": errors,
        "success_rate": round((requests - errors) / requests, 4) if requests else 1.0,
        "rag_requests": int(totals_row[6]),
    }

    # Série por dia.
    day = func.date(base.c.created_at)
    by_day_rows = (
        await db.execute(
            select(
                day.label("day"),
                func.count(),
                func.coalesce(func.sum(base.c.input_tokens), 0),
                func.coalesce(func.sum(base.c.output_tokens), 0),
                func.coalesce(func.sum(base.c.cost_usd), 0.0),
                func.coalesce(func.sum(is_error), 0),
            )
            .group_by(day)
            .order_by(day)
        )
    ).all()
    by_day = [
        {
            "date": str(r[0]),
            "requests": int(r[1]),
            "input_tokens": int(r[2]),
            "output_tokens": int(r[3]),
            "cost_usd": round(float(r[4]), 6),
            "errors": int(r[5]),
        }
        for r in by_day_rows
    ]

    # Quebra por modelo.
    by_model_rows = (
        await db.execute(
            select(
                base.c.model,
                func.count(),
                func.coalesce(func.sum(base.c.input_tokens), 0),
                func.coalesce(func.sum(base.c.output_tokens), 0),
                func.coalesce(func.sum(base.c.cost_usd), 0.0),
            )
            .group_by(base.c.model)
            .order_by(func.sum(base.c.cost_usd).desc())
        )
    ).all()
    by_model = [
        {
            "model": r[0],
            "requests": int(r[1]),
            "input_tokens": int(r[2]),
            "output_tokens": int(r[3]),
            "cost_usd": round(float(r[4]), 6),
        }
        for r in by_model_rows
    ]

    # Falhas recentes (para inspeção no dashboard).
    recent_error_rows = (
        await db.execute(
            select(base.c.created_at, base.c.model, base.c.error)
            .where(base.c.status == "error")
            .order_by(base.c.created_at.desc())
            .limit(10)
        )
    ).all()
    recent_errors = [
        {"created_at": str(r[0]), "model": r[1], "error": r[2] or "erro desconhecido"}
        for r in recent_error_rows
    ]

    return {
        "days": days,
        "totals": totals,
        "by_day": by_day,
        "by_model": by_model,
        "recent_errors": recent_errors,
    }
