"""Ferramenta de busca web com citações (issue #35).

Segue o contrato de contexto (#32): a busca devolve **(a)** as fontes completas
(título/URL/snippet/score) para renderização determinística das citações e **(b)**
um ``summary_for_context`` curto (snippets rankeados) que entra no prompt dentro
de uma cota de tokens. O conteúdo bruto das páginas nunca vai ao contexto.

Provedores:
- **Tavily** (principal): API de busca feita para LLMs — snippets já rankeados.
- **DuckDuckGo** (fallback de dev, sem chave): Instant Answer API; resultados
  mais pobres, suficiente para desenvolvimento sem custo.

A decisão de *quando* buscar é do chamador (toggle explícito ou heurística —
``needs_web_search``), não do modelo, para funcionar com modelos sem tool-calling.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from ..config import Settings
from .contract import ToolResult, fit_to_budget

logger = logging.getLogger("thinkai.websearch")


@dataclass
class WebSource:
    title: str
    url: str
    snippet: str
    score: float = 0.0

    def as_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet, "score": self.score}


@dataclass
class WebSearchResult:
    query: str
    sources: list[WebSource]
    tool: ToolResult
    answer: str | None = None  # resposta sintetizada pela Tavily (quando disponível)


# Gatilhos da heurística (quando o toggle está desligado): frescor/atualidade,
# pedido explícito de pesquisa, ou presença de URL.
_HEURISTIC = re.compile(
    r"\b(hoje|agora|atual(?:mente)?|recente|últim[ao]s?|notícias?|"
    r"preço|cotação|202\d|pesquis\w+|busqu\w+|na internet|no google)\b|https?://",
    re.IGNORECASE,
)


def needs_web_search(query: str, settings: Settings) -> bool:
    """Heurística barata: decide buscar sem depender do modelo (small model-safe)."""
    if not settings.web_search_heuristic:
        return False
    return bool(_HEURISTIC.search(query or ""))


def _resolve_provider(settings: Settings) -> str:
    choice = (settings.web_search_provider or "auto").lower()
    if choice == "auto":
        return "tavily" if settings.tavily_api_key else "duckduckgo"
    return choice


async def _tavily(query: str, settings: Settings) -> tuple[list[WebSource], str | None]:
    """Busca via Tavily trazendo **conteúdo** (não só links): `search_depth=advanced`
    e `include_answer` (resposta sintetizada que serve de base para o modelo)."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": settings.web_search_max_results,
                "search_depth": "advanced",
                "include_answer": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    sources = [
        WebSource(
            title=r.get("title") or r.get("url", ""),
            url=r.get("url", ""),
            snippet=(r.get("content") or "").strip(),
            score=float(r.get("score") or 0.0),
        )
        for r in data.get("results", [])
    ]
    answer = (data.get("answer") or "").strip() or None
    return sources, answer


async def _duckduckgo(query: str, settings: Settings) -> tuple[list[WebSource], str | None]:
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "no_redirect": "1"},
            headers={"User-Agent": "ThinkAI/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()

    sources: list[WebSource] = []
    if data.get("AbstractText"):
        sources.append(
            WebSource(
                title=data.get("Heading") or query,
                url=data.get("AbstractURL", ""),
                snippet=data["AbstractText"],
                score=1.0,
            )
        )
    for topic in data.get("RelatedTopics", []):
        if len(sources) >= settings.web_search_max_results:
            break
        if "Text" in topic and topic.get("FirstURL"):
            sources.append(
                WebSource(
                    title=topic["Text"][:80],
                    url=topic["FirstURL"],
                    snippet=topic["Text"],
                    score=0.5,
                )
            )
    answer = (data.get("AbstractText") or "").strip() or None
    return sources, answer


def _build_summary(query: str, sources: list[WebSource], answer: str | None) -> str:
    lines = [f'Resultados de busca web para "{query}":', ""]
    if answer:
        lines += ["Síntese da busca:", answer, ""]
    lines.append("Trechos das fontes:")
    for i, s in enumerate(sources, 1):
        snippet = " ".join(s.snippet.split())[:700]
        lines.append(f"[{i}] {s.title}: {snippet} ({s.url})")
    lines += [
        "",
        "Instruções: redija uma resposta completa em português, com base nas "
        "informações acima, sintetizando o conteúdo (não apenas listando links). "
        "Cite as fontes pelo número [n] ao usá-las. Se forem insuficientes, "
        "diga claramente o que não foi possível confirmar.",
    ]
    return "\n".join(lines)


async def web_search(query: str, settings: Settings) -> WebSearchResult | None:
    """Executa a busca e monta o ``ToolResult`` dentro da cota. ``None`` em falha."""
    provider = _resolve_provider(settings)
    try:
        if provider == "tavily" and settings.tavily_api_key:
            sources, answer = await _tavily(query, settings)
        else:
            if provider == "tavily":
                logger.warning("Tavily selecionado sem chave; caindo para DuckDuckGo")
            sources, answer = await _duckduckgo(query, settings)
    except Exception:
        logger.exception("Falha na busca web (%s)", provider)
        return None

    if not sources and not answer:
        return None

    tool = fit_to_budget(
        _build_summary(query, sources, answer),
        artifact_ref=f"web:{query[:60]}",
        max_tokens=settings.web_search_max_tokens,
    )
    return WebSearchResult(query=query, sources=sources, tool=tool, answer=answer)
