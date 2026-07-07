"""Geração de resumos de documentos via LLM (issues #44 single / #45 consolidated).

Estratégia **map-reduce** para caber em qualquer janela de contexto:
- *map*: divide o texto em blocos grandes e resume cada um;
- *reduce*: sintetiza os resumos parciais num resumo final coeso.

Textos curtos são resumidos em uma única passada. Reusa o client OpenAI-compat do
provedor de chat ativo (``build_chat_client``). Tratamento de erro fica no chamador
(router): aqui as exceções sobem para virar HTTP 502/500 com mensagem clara.
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

logger = logging.getLogger("thinkai.summarize")

# ~limite de caracteres por bloco no *map* (folga sobre a janela do modelo).
_MAP_CHUNK_CHARS = 9000

_SINGLE_PROMPT = (
    "Resuma o documento a seguir em português, de forma clara e estruturada: "
    "comece com uma frase-síntese, depois os pontos principais em tópicos. "
    "Seja fiel ao conteúdo, sem inventar. Documento:\n\n{content}"
)
_MAP_PROMPT = (
    "Resuma objetivamente este trecho de um documento, preservando fatos, termos "
    "e números importantes (em português):\n\n{content}"
)
_REDUCE_PROMPT = (
    "A seguir estão resumos parciais de um mesmo documento, em ordem. Sintetize-os "
    "num único resumo coeso em português: uma frase-síntese seguida dos pontos "
    "principais em tópicos, sem repetições. Resumos parciais:\n\n{content}"
)
_CONSOLIDATED_PROMPT = (
    "A seguir estão resumos de documentos diferentes sobre um tema. Produza um "
    "**resumo consolidado** em português que integre as informações, destaque "
    "convergências e divergências e organize por tópicos. Indique entre colchetes "
    "o número do documento ao citar algo específico. Resumos:\n\n{content}"
)


def _split(text: str, size: int = _MAP_CHUNK_CHARS) -> list[str]:
    text = (text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    out, i = [], 0
    while i < len(text):
        end = min(i + size, len(text))
        # tenta quebrar num parágrafo/espaço próximo para não cortar no meio
        if end < len(text):
            brk = text.rfind("\n", i, end)
            if brk == -1:
                brk = text.rfind(" ", i, end)
            if brk > i:
                end = brk
        out.append(text[i:end].strip())
        i = end
    return [c for c in out if c]


async def _complete(client: AsyncOpenAI, model: str, prompt: str, *, max_tokens: int = 800) -> str:
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()


def _single_prompt() -> str:
    """Prompt de resumo único: usa o configurável se válido (contém {content})."""
    from ..config import get_settings

    p = get_settings().summary_prompt
    return p if p and "{content}" in p else _SINGLE_PROMPT


async def summarize_text(client: AsyncOpenAI, model: str, text: str) -> str:
    """Resumo de um documento (map-reduce quando longo)."""
    chunks = _split(text)
    if not chunks:
        return ""
    if len(chunks) == 1:
        return await _complete(client, model, _single_prompt().format(content=chunks[0]))
    partials = []
    for i, ch in enumerate(chunks, 1):
        logger.info("Resumo map: bloco %d/%d", i, len(chunks))
        partials.append(await _complete(client, model, _MAP_PROMPT.format(content=ch)))
    joined = "\n\n".join(f"[Parte {i}] {p}" for i, p in enumerate(partials, 1))
    return await _complete(client, model, _REDUCE_PROMPT.format(content=joined), max_tokens=1000)


_MINDMAP_PROMPT = (
    "Gere um **mapa mental** do documento a seguir como um OUTLINE em Markdown, "
    "e responda APENAS com o outline (sem texto extra, sem cercas de código). "
    "Formato: um único título de nível 1 (# Tópico central), tópicos principais "
    "em nível 2 (## Ramo) e folhas como itens de lista (- item), aninháveis com "
    "indentação. Rótulos curtos, em português. Documento:\n\n{content}"
)


def _clean_outline(text: str) -> str:
    """Remove cercas de código que o modelo às vezes adiciona ao outline."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = [ln for ln in t.splitlines() if not ln.strip().startswith("```")]
        t = "\n".join(lines).strip()
    return t


async def generate_mindmap(client: AsyncOpenAI, model: str, text: str) -> str:
    """Gera o outline (Markdown) de um mapa mental do documento (#36).

    Determinístico do ponto de vista do produto: é uma chamada dedicada, não
    depende de o modelo de chat espontaneamente emitir o bloco. Para textos
    longos, resume antes (map-reduce) para caber e destacar a estrutura.
    """
    from ..config import get_settings

    source = text
    if len(text) > _MAP_CHUNK_CHARS:
        source = await summarize_text(client, model, text)
    cfg = get_settings().mindmap_prompt
    prompt = cfg if cfg and "{content}" in cfg else _MINDMAP_PROMPT
    outline = await _complete(client, model, prompt.format(content=source), max_tokens=900)
    outline = _clean_outline(outline)
    # Garante um título de nível 1 para o Markmap ancorar a raiz.
    if not any(ln.lstrip().startswith("# ") for ln in outline.splitlines()):
        outline = f"# Mapa mental\n{outline}"
    return outline


async def consolidate_summaries(
    client: AsyncOpenAI, model: str, per_doc: list[tuple[str, str]]
) -> str:
    """Resumo consolidado (#45): recebe [(nome, resumo), ...] e sintetiza um único."""
    if not per_doc:
        return ""
    joined = "\n\n".join(
        f"[Documento {i}: {name}]\n{summary}" for i, (name, summary) in enumerate(per_doc, 1)
    )
    return await _complete(client, model, _CONSOLIDATED_PROMPT.format(content=joined), max_tokens=1200)
