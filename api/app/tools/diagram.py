"""Diagramas e mapas mentais como texto Mermaid — não como imagem.

Texto Mermaid é determinístico (mesma entrada → mesmo diagrama), cacheável,
versionável e barato em contexto — ao contrário de gerar uma imagem, que não é
reproduzível e não cabe no orçamento de tokens do turno. A ativação segue o
mesmo padrão do RAG (#34): detecção de intenção por heurística, execução
determinística no backend, sem function-calling nativo do LLM.

    detect_diagram_intent(mensagem) → tipo | None
    generate_diagram(tipo, conteudo) → (DiagramArtifact, ToolResult)

A garantia de "mesma entrada → mesma saída" vem do **cache** por
``sha256(tipo + conteúdo normalizado)`` — a chamada ao LLM em si não é
estritamente determinística, mas a mesma chave sempre devolve o mesmo Mermaid
já validado. Cache em processo (sem Redis no projeto); não sobrevive a restart
nem é compartilhado entre instâncias — mesmo trade-off dos singletons
``lru_cache`` já usados (config/storage/runner).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Literal

from openai import AsyncOpenAI

from .contract import ToolResult, fit_to_budget

logger = logging.getLogger("thinkai.diagram")

DiagramType = Literal["flowchart", "mindmap", "sequence"]

_INTENT_PATTERNS: list[tuple[re.Pattern[str], DiagramType]] = [
    (re.compile(r"mapa\s+mental|mind\s*map", re.IGNORECASE), "mindmap"),
    (
        re.compile(r"diagrama\s+de\s+sequ[eê]ncia|sequence\s+diagram", re.IGNORECASE),
        "sequence",
    ),
    (
        re.compile(r"fluxograma|flowchart|diagrama\s+de\s+fluxo", re.IGNORECASE),
        "flowchart",
    ),
]

_EXPECTED_HEADER: dict[DiagramType, tuple[str, ...]] = {
    "flowchart": ("flowchart", "graph"),
    "mindmap": ("mindmap",),
    "sequence": ("sequencediagram",),
}

_FENCE_RE = re.compile(r"^```(?:mermaid)?\s*\n?|```\s*$", re.IGNORECASE | re.MULTILINE)

_SYSTEM_PROMPT = (
    "Você é um gerador de diagramas Mermaid. Dado um tipo de diagrama e um "
    "conteúdo, devolva **apenas** o texto Mermaid correspondente — sem "
    "explicações, sem cercas de código (```), começando diretamente pelo "
    "cabeçalho do diagrama (`flowchart TD`, `mindmap` ou `sequenceDiagram`)."
)

_FEW_SHOT: dict[DiagramType, tuple[str, str]] = {
    "flowchart": (
        "Tipo: flowchart. Conteúdo: matrícula de um aluno novo",
        "flowchart TD\n"
        "    A[Aluno preenche formulário] --> B{Documentos completos?}\n"
        "    B -- Sim --> C[Matrícula aprovada]\n"
        "    B -- Não --> D[Solicita documentos faltantes]\n"
        "    D --> A",
    ),
    "mindmap": (
        "Tipo: mindmap. Conteúdo: estrutura de um sistema operacional",
        "mindmap\n"
        "  root((Sistema Operacional))\n"
        "    Gerência de processos\n"
        "      Escalonamento\n"
        "      Sincronização\n"
        "    Gerência de memória\n"
        "      Paginação\n"
        "    Gerência de arquivos",
    ),
    "sequence": (
        "Tipo: sequence. Conteúdo: login de usuário",
        "sequenceDiagram\n"
        "    participant U as Usuário\n"
        "    participant A as API\n"
        "    participant B as Banco\n"
        "    U->>A: POST /auth/signin\n"
        "    A->>B: valida credenciais\n"
        "    B-->>A: usuário encontrado\n"
        "    A-->>U: token JWT",
    ),
}


def detect_diagram_intent(text: str) -> DiagramType | None:
    """Detecta, por palavras-chave (pt/en), se o usuário pediu um diagrama.

    Mesmo padrão do RAG: heurística de texto, sem o LLM decidir nada. A ordem
    importa só para "diagrama de sequência" vs. o "diagrama de fluxo" mais
    genérico — mindmap e sequência são checados antes do fluxograma.
    """
    for pattern, tipo in _INTENT_PATTERNS:
        if pattern.search(text):
            return tipo
    return None


@dataclass
class DiagramArtifact:
    """Diagrama Mermaid já validado, pronto para o frontend renderizar."""

    tipo: DiagramType
    mermaid: str
    cached: bool


def _cache_key(tipo: str, conteudo: str) -> str:
    normalized = " ".join(conteudo.split()).strip().lower()
    return hashlib.sha256(f"{tipo}::{normalized}".encode()).hexdigest()


_cache: dict[str, DiagramArtifact] = {}


def _strip_code_fence(text: str) -> str:
    """Remove cercas ```mermaid ... ``` que o LLM eventualmente inclua."""
    return _FENCE_RE.sub("", text).strip()


def validate_mermaid(text: str, tipo: DiagramType) -> tuple[bool, str | None]:
    """Validação estrutural leve — não é um parser Mermaid completo.

    Não existe binding Python oficial robusto para o parser real (que roda em
    JS no navegador); esta checagem pega os erros mais comuns: o modelo
    devolvendo prosa em vez de Mermaid, cabeçalho errado para o tipo pedido, ou
    colchetes/parênteses desbalanceados.
    """
    body = text.strip()
    if not body:
        return False, "saída vazia"

    first_line = body.splitlines()[0].strip().lower()
    expected = _EXPECTED_HEADER[tipo]
    if not any(first_line.startswith(h) for h in expected):
        return False, f"cabeçalho esperado {expected!r}, recebido {first_line!r}"

    for open_ch, close_ch in (("[", "]"), ("(", ")"), ("{", "}")):
        if body.count(open_ch) != body.count(close_ch):
            return False, f"'{open_ch}'/'{close_ch}' desbalanceados"

    return True, None


def _sanitize_label(reason: str) -> str:
    return re.sub(r"[^\w\s]", "", reason)[:80] or "motivo desconhecido"


def _fallback_mermaid(tipo: DiagramType, reason: str) -> str:
    """Diagrama mínimo, sempre válido — o frontend nunca recebe Mermaid quebrado."""
    label = _sanitize_label(reason)
    if tipo == "mindmap":
        return f"mindmap\n  root((Não foi possível gerar o mapa mental: {label}))"
    if tipo == "sequence":
        return (
            "sequenceDiagram\n"
            "    participant Sistema\n"
            f"    Sistema-->>Sistema: Não foi possível gerar o diagrama ({label})"
        )
    return f"flowchart TD\n    A[Não foi possível gerar o diagrama: {label}]"


def _build_prompt(tipo: DiagramType, conteudo: str) -> list[dict[str, str]]:
    example_user, example_assistant = _FEW_SHOT[tipo]
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": example_user},
        {"role": "assistant", "content": example_assistant},
        {"role": "user", "content": f"Tipo: {tipo}. Conteúdo: {conteudo}"},
    ]


async def generate_diagram(
    tipo: DiagramType,
    conteudo: str,
    *,
    client: AsyncOpenAI,
    model: str,
    max_tokens: int,
) -> tuple[DiagramArtifact, ToolResult]:
    """Gera (ou recupera do cache) um diagrama Mermaid válido para ``(tipo, conteudo)``.

    Cache hit: devolve o Mermaid já validado, sem chamar o LLM (determinismo +
    custo zero na repetição). Cache miss: pede ao LLM o Mermaid, valida a
    sintaxe; se inválida, tenta reparo determinístico (remover cercas de
    código) e revalida; se ainda inválida, usa um diagrama de fallback — nunca
    propaga um Mermaid quebrado ao frontend.
    """
    key = _cache_key(tipo, conteudo)

    cached = _cache.get(key)
    if cached is not None:
        result = fit_to_budget(cached.mermaid, artifact_ref=key, max_tokens=max_tokens)
        return DiagramArtifact(tipo=tipo, mermaid=cached.mermaid, cached=True), result

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=_build_prompt(tipo, conteudo),
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
    except Exception:  # pragma: no cover - resiliência: nunca quebra o chat
        logger.exception("Falha ao chamar o LLM para gerar diagrama tipo=%s", tipo)
        raw = ""

    candidate = _strip_code_fence(raw)
    ok, reason = validate_mermaid(candidate, tipo)
    if not ok:
        logger.info("Diagrama tipo=%s inválido (%s); usando fallback", tipo, reason)
        candidate = _fallback_mermaid(tipo, reason or "saída inválida")

    artifact = DiagramArtifact(tipo=tipo, mermaid=candidate, cached=False)
    _cache[key] = artifact
    result = fit_to_budget(candidate, artifact_ref=key, max_tokens=max_tokens)
    return artifact, result
