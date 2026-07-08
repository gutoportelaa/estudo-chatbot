"""Geração de resumos e mapas mentais multi-documento (worker assíncrono).

Todas as funções recebem uma lista de documentos ``[(filename, text)]`` e
os injetam no prompt com delimitação XML ``<documento filename="...">…</documento>``
para que a LLM trate cada um como contexto próprio (não mistura fatos entre docs).

Se a soma dos textos estourar o teto ``_SINGLE_CALL_MAX_CHARS``, cai no fallback
**map-reduce**: cada doc vira um resumo parcial (map) e depois um único
prompt sintetiza a saída final (reduce). Assim o pipeline aguenta docs grandes
sem estourar a janela de nenhum provedor.

O chamador (worker) trata exceções — aqui, tudo sobe.
"""

from __future__ import annotations

import logging
import re

from openai import AsyncOpenAI

logger = logging.getLogger("thinkai.summarize")

# Teto para tentar uma única chamada com todos os docs concatenados. Acima disso,
# entra o map-reduce por documento (evita estourar janela e mantém latência ok).
_SINGLE_CALL_MAX_CHARS = 30_000
# Fatiamento de map-reduce por documento longo — cada fatia vira um resumo parcial.
_MAP_CHUNK_CHARS = 9_000


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


_TITLE_MARKER = "TÍTULO:"

_SUMMARY_INSTRUCTIONS = (
    "Você receberá {n_docs} documento(s) delimitados por tags "
    "<documento filename=\"...\">…</documento>. Trate cada um como contexto "
    "próprio: NÃO misture fatos entre documentos. Escreva em português.\n\n"
    "Responda EXATAMENTE neste formato:\n"
    f"{_TITLE_MARKER} <título curto, 5 a 8 palavras, sem aspas>\n\n"
    "## Resumo por documento\n"
    "### <filename do doc 1>\n"
    "<frase-síntese em **negrito** + tópicos em `- `>\n"
    "### <filename do doc 2>\n"
    "…\n\n"
    "## Síntese integrada\n"
    "<parágrafo curto conectando os documentos; destaque convergências e "
    "divergências entre eles usando [filename] entre colchetes ao citar>\n\n"
    "Se houver apenas 1 documento, omita a seção 'Síntese integrada'."
)

_MAP_INSTRUCTIONS = (
    "Resuma objetivamente o trecho abaixo em português, preservando fatos, "
    "termos e números importantes. Não invente. Trecho:"
)

_REDUCE_INSTRUCTIONS = (
    "A seguir estão resumos parciais de {n_docs} documento(s) diferentes, "
    "identificados por <documento filename=\"...\">. Produza a saída final "
    "EXATAMENTE no formato abaixo (português):\n\n"
    f"{_TITLE_MARKER} <título curto, 5 a 8 palavras, sem aspas>\n\n"
    "## Resumo por documento\n"
    "### <filename>\n"
    "<frase-síntese em **negrito** + tópicos em `- `>\n\n"
    "## Síntese integrada\n"
    "<parágrafo curto com convergências/divergências, citando [filename]>\n\n"
    "Se houver apenas 1 documento, omita a 'Síntese integrada'."
)

_MINDMAP_INSTRUCTIONS = (
    "Você receberá {n_docs} documento(s) delimitados por tags "
    "<documento filename=\"...\">…</documento>. Gere UM ÚNICO mapa mental como "
    "outline em Markdown puro (sem cercas de código, sem texto fora do outline).\n\n"
    "Regras estritas:\n"
    "- Uma única linha de nível 1 (# Título central).\n"
    "- Nível 2 (## Ramo) para cada documento OU para cada tema principal.\n"
    "- Folhas em '- item' (podem aninhar com indentação).\n"
    "- Rótulos curtos, em português, sem markdown extra.\n"
    "- Trate cada documento como contexto próprio: NÃO misture fatos entre eles.\n"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape(text: str) -> str:
    """Neutraliza tags <documento> internas no texto do PDF pra não confundir o parser da LLM."""
    return (text or "").replace("<documento", "&lt;documento").replace("</documento>", "&lt;/documento&gt;")


def _wrap_docs(docs: list[tuple[str, str]]) -> str:
    """Junta os docs no formato ``<documento filename="X">...</documento>``."""
    return "\n\n".join(
        f'<documento filename="{filename}">\n{_escape(text)}\n</documento>'
        for filename, text in docs
        if text and text.strip()
    )


def _split(text: str, size: int = _MAP_CHUNK_CHARS) -> list[str]:
    """Fatias de ~``size`` chars quebrando em parágrafo/espaço quando possível."""
    text = (text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    out, i = [], 0
    while i < len(text):
        end = min(i + size, len(text))
        if end < len(text):
            brk = text.rfind("\n", i, end)
            if brk == -1:
                brk = text.rfind(" ", i, end)
            if brk > i:
                end = brk
        out.append(text[i:end].strip())
        i = end
    return [c for c in out if c]


async def _complete(client: AsyncOpenAI, model: str, prompt: str, *, max_tokens: int = 1200) -> str:
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()


def _extract_title(content: str) -> tuple[str | None, str]:
    """Extrai a linha ``TÍTULO: ...`` (se houver) e devolve (título, resto).

    Case-insensitive porque alguns modelos escrevem ``Titulo:`` sem acento.
    """
    pattern = re.compile(rf"^\s*T[ÍI]TULO:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    m = pattern.search(content)
    if not m:
        return None, content.strip()
    title = m.group(1).strip().strip('"').strip("'")
    remainder = (content[: m.start()] + content[m.end():]).strip()
    return (title or None), remainder


def _clean_outline(text: str) -> str:
    """Remove cercas de código que o modelo às vezes coloca em torno do outline."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = [ln for ln in t.splitlines() if not ln.strip().startswith("```")]
        t = "\n".join(lines).strip()
    return t


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


async def summarize_documents(
    client: AsyncOpenAI, model: str, docs: list[tuple[str, str]]
) -> tuple[str | None, str]:
    """Resumo multi-documento com contextos separados.

    Retorna ``(title, content_markdown)``. Estratégia:
      - se ``sum(len(text)) <= _SINGLE_CALL_MAX_CHARS``: 1 chamada só,
        com todos os docs delimitados por ``<documento>``.
      - senão: map-reduce por documento (cada um vira um resumo parcial;
        depois uma chamada final sintetiza tudo).
    """
    usable = [(f, t) for f, t in docs if t and t.strip()]
    if not usable:
        return None, ""

    total = sum(len(t) for _, t in usable)
    if total <= _SINGLE_CALL_MAX_CHARS:
        prompt = _SUMMARY_INSTRUCTIONS.format(n_docs=len(usable)) + "\n\n" + _wrap_docs(usable)
        raw = await _complete(client, model, prompt, max_tokens=1500)
        return _extract_title(raw)

    # Map: um resumo por documento (partindo cada doc grande em blocos).
    partials: list[tuple[str, str]] = []
    for filename, text in usable:
        chunks = _split(text)
        if len(chunks) == 1:
            partial = await _complete(client, model, f"{_MAP_INSTRUCTIONS}\n\n{chunks[0]}", max_tokens=700)
        else:
            pieces: list[str] = []
            for i, ch in enumerate(chunks, 1):
                logger.info("map %s bloco %d/%d", filename, i, len(chunks))
                pieces.append(await _complete(client, model, f"{_MAP_INSTRUCTIONS}\n\n{ch}", max_tokens=500))
            joined = "\n\n".join(f"[Parte {i}] {p}" for i, p in enumerate(pieces, 1))
            partial = await _complete(
                client, model, f"{_MAP_INSTRUCTIONS}\n\n{joined}", max_tokens=700
            )
        partials.append((filename, partial))

    # Reduce: síntese final com o mesmo formato canônico.
    prompt = _REDUCE_INSTRUCTIONS.format(n_docs=len(partials)) + "\n\n" + _wrap_docs(partials)
    raw = await _complete(client, model, prompt, max_tokens=1500)
    return _extract_title(raw)


async def generate_mindmap_from_documents(
    client: AsyncOpenAI, model: str, docs: list[tuple[str, str]]
) -> str:
    """Mapa mental (outline markdown) multi-documento.

    Para textos muito longos, usa como fonte os resumos parciais (map) do
    passo de resumo, evitando estourar a janela.
    """
    usable = [(f, t) for f, t in docs if t and t.strip()]
    if not usable:
        return ""

    total = sum(len(t) for _, t in usable)
    if total <= _SINGLE_CALL_MAX_CHARS:
        source = usable
    else:
        source = []
        for filename, text in usable:
            chunks = _split(text)
            if len(chunks) == 1:
                summary = await _complete(client, model, f"{_MAP_INSTRUCTIONS}\n\n{chunks[0]}", max_tokens=600)
            else:
                pieces = []
                for i, ch in enumerate(chunks, 1):
                    pieces.append(await _complete(client, model, f"{_MAP_INSTRUCTIONS}\n\n{ch}", max_tokens=400))
                summary = "\n\n".join(pieces)
            source.append((filename, summary))

    prompt = _MINDMAP_INSTRUCTIONS.format(n_docs=len(source)) + "\n\n" + _wrap_docs(source)
    outline = _clean_outline(await _complete(client, model, prompt, max_tokens=1200))
    if not any(ln.lstrip().startswith("# ") for ln in outline.splitlines()):
        outline = f"# Mapa mental\n{outline}"
    return outline
