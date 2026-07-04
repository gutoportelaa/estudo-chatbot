"""Testes da tela de Consumo: agregação de tokens/custo (#37)."""

from __future__ import annotations

import asyncio

from app.database import AsyncSessionLocal
from app.models import TurnMetric


def _auth(client, username="usage_user", password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    r = client.post("/auth/signin", json={"username": username, "password": password})
    token = r.json()["access_token"]
    me = client.get("/auth/profile", headers={"Authorization": f"Bearer {token}"}).json()
    return {"Authorization": f"Bearer {token}"}, me["id"]


def _seed(user_id: str, rows: list[dict]) -> None:
    async def _go():
        async with AsyncSessionLocal() as db:
            for r in rows:
                db.add(TurnMetric(user_id=user_id, session_id="s", **r))
            await db.commit()

    asyncio.run(_go())


def test_usage_requires_auth(client):
    assert client.get("/metrics/usage").status_code in (401, 403)


def test_usage_empty_returns_zeros(client):
    headers, _ = _auth(client)
    body = client.get("/metrics/usage", headers=headers).json()
    assert body["totals"]["requests"] == 0
    assert body["totals"]["cost_usd"] == 0.0
    assert body["by_day"] == []
    assert body["by_model"] == []


def test_usage_aggregates_totals_and_by_model(client):
    headers, uid = _auth(client)
    _seed(
        uid,
        [
            {"model": "gemini-2.0-flash", "provider": "gemini", "input_tokens": 100, "output_tokens": 50, "latency_ms": 200.0, "cost_usd": 0.001},
            {"model": "gemini-2.0-flash", "provider": "gemini", "input_tokens": 200, "output_tokens": 80, "latency_ms": 400.0, "cost_usd": 0.002},
            {"model": "llama3.2:3b", "provider": "ollama", "input_tokens": 300, "output_tokens": 120, "latency_ms": 5000.0, "cost_usd": 0.0},
        ],
    )
    body = client.get("/metrics/usage", headers=headers).json()

    t = body["totals"]
    assert t["requests"] == 3
    assert t["input_tokens"] == 600
    assert t["output_tokens"] == 250
    assert round(t["cost_usd"], 6) == 0.003
    assert t["avg_latency_ms"] == round((200 + 400 + 5000) / 3, 1)

    # Quebra por modelo, ordenada por custo desc.
    models = {m["model"]: m for m in body["by_model"]}
    assert models["gemini-2.0-flash"]["requests"] == 2
    assert models["gemini-2.0-flash"]["input_tokens"] == 300
    assert models["llama3.2:3b"]["cost_usd"] == 0.0
    assert body["by_model"][0]["model"] == "gemini-2.0-flash"  # maior custo primeiro


def test_usage_isolated_per_user(client):
    a_headers, a_uid = _auth(client, username="alice_u")
    b_headers, b_uid = _auth(client, username="bob_u")
    _seed(a_uid, [{"model": "m", "provider": "p", "input_tokens": 10, "output_tokens": 5, "latency_ms": 1.0, "cost_usd": 0.01}])

    # Bob não vê o consumo da Alice.
    assert client.get("/metrics/usage", headers=b_headers).json()["totals"]["requests"] == 0
    assert client.get("/metrics/usage", headers=a_headers).json()["totals"]["requests"] == 1
