"""Observabilidade de tokens e custo por turno (issue #37).

Para qualquer turno, responder **"onde foram os tokens?"**: a quebra por bloco
(system, resumo, RAG, histórico, tool), os totais de entrada/saída, a latência e
o custo estimado por usuário/sessão. Emite um log estruturado (JSON) por turno —
insumo direto para um dashboard (CloudWatch na entrega AWS).

Os tokens de entrada vêm do ``TokenBreakdown`` do Context Assembler (#30); a
saída e a latência são medidas na orquestração (``app/llm.py``). O custo é uma
estimativa a partir de uma tabela de preços por modelo.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

logger = logging.getLogger("thinkai.observability")

# Preço por 1M de tokens em USD: (entrada, saída). Estimativa para o custo por
# turno; valores de tabelas públicas dos provedores (atualizar quando mudarem).
# Modelos locais (Ollama) e desconhecidos assumem custo zero.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Google Gemini
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    # Groq / Meta Llama
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama3-8b-8192": (0.05, 0.08),
    # Ollama (local) — sem custo
    "llama3.2": (0.0, 0.0),
    "llama3.2:3b": (0.0, 0.0),
    "mistral": (0.0, 0.0),
    "qwen2.5": (0.0, 0.0),
}
_DEFAULT_PRICING = (0.0, 0.0)  # desconhecido: assume local/sem custo


def price_for(model: str) -> tuple[float, float]:
    """Preço (entrada, saída) por 1M de tokens, com match exato ou por prefixo."""
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    base = model.split(":")[0]
    for key, val in MODEL_PRICING.items():
        if key.startswith(base) or base.startswith(key):
            return val
    return _DEFAULT_PRICING


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Custo estimado do turno em USD a partir da tabela de preços por modelo."""
    price_in, price_out = price_for(model)
    cost = (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    return round(cost, 6)


@dataclass
class TurnMetrics:
    """Métricas de um turno do chat (uma resposta do assistente).

    Os campos ``tokens_*`` são a quebra do prompt por bloco (entrada); somados,
    compõem ``input_tokens``. ``output_tokens`` é a resposta gerada.
    """

    session_id: str
    model: str
    provider: str = ""
    user_id: str | None = None
    # Quebra do prompt por bloco (tokens de entrada).
    tokens_system: int = 0
    tokens_summary: int = 0
    tokens_rag: int = 0
    tokens_recent: int = 0
    tokens_tool: int = 0
    # Totais e métricas do turno.
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def log_turn(metrics: TurnMetrics) -> None:
    """Emite um log estruturado (JSON numa linha) com a quebra do turno.

    O prefixo ``turn_metrics`` facilita o filtro/parsing num coletor (CloudWatch
    Logs Insights, Grafana/Loki) para montar o dashboard de crescimento de
    contexto e custo por usuário.
    """
    logger.info("turn_metrics %s", json.dumps(metrics.to_dict(), ensure_ascii=False))


def configure_logging(level: int = logging.INFO) -> None:
    """Configura o logging dos loggers ``thinkai.*``.

    Sem isso, o nível default (WARNING) engoliria os logs de tokens/turno e a
    quebra por bloco do Context Assembler. Idempotente: não duplica handlers.
    """
    root = logging.getLogger("thinkai")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
