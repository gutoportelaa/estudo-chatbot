"""Testes da observabilidade de tokens e custo por turno (issue #37).

Critério de aceitação: para qualquer turno, é possível responder "onde foram os
tokens?" — a quebra por bloco, os totais e o custo saem num log estruturado.
"""

from __future__ import annotations

import json
import logging

from app.context import ContextBudget
from app.observability import (
    MODEL_PRICING,
    TurnMetrics,
    estimate_cost,
    log_turn,
    price_for,
)


def test_price_for_exact_and_prefix_and_default():
    assert price_for("gemini-2.5-flash") == MODEL_PRICING["gemini-2.5-flash"]
    # Variante de tag não listada cai no modelo base por prefixo.
    assert price_for("llama3.2:1b") == MODEL_PRICING["llama3.2"]
    # Modelo desconhecido: custo zero (assume local).
    assert price_for("modelo-inexistente") == (0.0, 0.0)


def test_estimate_cost_uses_per_million_pricing():
    # gemini-2.5-flash: 0.30 entrada / 2.50 saída por 1M de tokens.
    cost = estimate_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
    assert cost == round(0.30 + 2.50, 6)
    # Modelo local não custa nada.
    assert estimate_cost("llama3.2", 10_000, 10_000) == 0.0


def test_turn_metrics_serializes_all_fields():
    m = TurnMetrics(
        session_id="s1",
        model="gemini-2.0-flash",
        provider="gemini",
        user_id="u1",
        tokens_system=10,
        tokens_recent=20,
        input_tokens=30,
        output_tokens=15,
        latency_ms=123.4,
        cost_usd=0.0001,
    )
    d = m.to_dict()
    assert d["session_id"] == "s1"
    assert d["user_id"] == "u1"
    assert d["input_tokens"] == 30
    assert d["output_tokens"] == 15
    # Serializável em JSON (vai para o log estruturado).
    assert json.loads(json.dumps(d))["model"] == "gemini-2.0-flash"


def test_log_turn_emits_structured_json():
    # Captura via handler próprio no logger — independe de propagação (a app
    # desliga propagate em configure_logging, o que cega o caplog padrão).
    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    obs_logger = logging.getLogger("thinkai.observability")
    handler = _Capture()
    obs_logger.addHandler(handler)
    prev_level = obs_logger.level
    obs_logger.setLevel(logging.INFO)
    try:
        log_turn(TurnMetrics(session_id="s1", model="gemini-2.0-flash", input_tokens=42, output_tokens=7))
    finally:
        obs_logger.removeHandler(handler)
        obs_logger.setLevel(prev_level)

    message = next(r.getMessage() for r in captured if r.getMessage().startswith("turn_metrics"))
    payload = json.loads(message[len("turn_metrics ") :])
    assert payload["session_id"] == "s1"
    assert payload["input_tokens"] == 42
    assert payload["output_tokens"] == 7


def test_context_budget_exposes_breakdown_summing_to_total():
    """A quebra por bloco é o insumo de entrada da observabilidade."""
    budget = ContextBudget(model="gemini-2.5-flash")
    budget.assemble(
        system="prompt do sistema",
        summary="memória da conversa",
        rag_hits=[{"role": "system", "content": "trecho recuperado"}],
        recent=[{"role": "user", "content": "minha pergunta"}],
        tool_output="saída de ferramenta",
    )
    b = budget.breakdown
    assert b is not None
    # Cada bloco contribui e a soma fecha com o total.
    assert b.system > 0 and b.summary > 0 and b.rag > 0 and b.recent > 0 and b.tool > 0
    assert b.total == b.system + b.summary + b.rag + b.recent + b.tool
