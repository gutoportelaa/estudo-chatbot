from __future__ import annotations

import pytest

from app.tools import summarize
from app.tools.summarize import (
    _clean_outline,
    _extract_title,
    _wrap_docs,
    generate_mindmap_from_documents,
    summarize_documents,
)


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, owner: "_FakeClient") -> None:
        self.owner = owner

    async def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        return _Response(self.owner.outputs.pop(0))


class _Chat:
    def __init__(self, owner: "_FakeClient") -> None:
        self.completions = _Completions(owner)


class _FakeClient:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls: list[dict] = []
        self.chat = _Chat(self)

    @property
    def prompts(self) -> list[str]:
        return [call["messages"][0]["content"] for call in self.calls]


def test_extract_title_removes_title_line_from_content():
    title, content = _extract_title("TÍTULO: Fotossíntese e Energia\n\n## Resumo\n- item")

    assert title == "Fotossíntese e Energia"
    assert content == "## Resumo\n- item"


def test_extract_title_accepts_unaccented_marker():
    title, content = _extract_title("TITULO: Biologia Celular\n\ncorpo")

    assert title == "Biologia Celular"
    assert content == "corpo"


def test_extract_title_without_marker_keeps_content():
    title, content = _extract_title("## Resumo\n- sem titulo")

    assert title is None
    assert content == "## Resumo\n- sem titulo"


def test_clean_outline_removes_code_fences():
    raw = "```markdown\n# Tema\n## Ramo\n- item\n```"

    assert _clean_outline(raw) == "# Tema\n## Ramo\n- item"


def test_wrap_docs_escapes_internal_document_tags():
    wrapped = _wrap_docs([("a.pdf", "antes <documento>interno</documento> depois")])

    assert '<documento filename="a.pdf">' in wrapped
    assert "&lt;documento>interno&lt;/documento&gt; depois" in wrapped


@pytest.mark.asyncio
async def test_summarize_documents_empty_returns_empty_result():
    client = _FakeClient([])

    title, content = await summarize_documents(client, "modelo", [])

    assert title is None
    assert content == ""
    assert client.calls == []


@pytest.mark.asyncio
async def test_summarize_documents_small_text_uses_single_call():
    client = _FakeClient(
        [
            "TÍTULO: Biologia Celular\n\n## Resumo por documento\n### bio.pdf\n- Conteúdo"
        ]
    )

    title, content = await summarize_documents(client, "modelo", [("bio.pdf", "texto curto")])

    assert title == "Biologia Celular"
    assert content == "## Resumo por documento\n### bio.pdf\n- Conteúdo"
    assert len(client.calls) == 1
    assert 'filename="bio.pdf"' in client.prompts[0]


@pytest.mark.asyncio
async def test_summarize_documents_large_text_uses_map_reduce(monkeypatch):
    monkeypatch.setattr(summarize, "_SINGLE_CALL_MAX_CHARS", 10)
    client = _FakeClient(
        [
            "parcial 1",
            "parcial 2",
            "parcial consolidado",
            "TÍTULO: Final\n\n## Resumo por documento\n- final",
        ]
    )

    title, content = await summarize_documents(client, "modelo", [("grande.pdf", "a" * 9001)])

    assert title == "Final"
    assert content == "## Resumo por documento\n- final"
    assert len(client.calls) == 4
    assert "resumos parciais" in client.prompts[-1]


@pytest.mark.asyncio
async def test_generate_mindmap_empty_returns_empty_string():
    client = _FakeClient([])

    assert await generate_mindmap_from_documents(client, "modelo", []) == ""
    assert client.calls == []


@pytest.mark.asyncio
async def test_generate_mindmap_small_text_returns_clean_outline():
    client = _FakeClient(["```markdown\n# Biologia\n## Célula\n- Mitocôndria\n```"])

    outline = await generate_mindmap_from_documents(client, "modelo", [("bio.pdf", "texto")])

    assert outline == "# Biologia\n## Célula\n- Mitocôndria"
    assert len(client.calls) == 1
    assert 'filename="bio.pdf"' in client.prompts[0]


@pytest.mark.asyncio
async def test_generate_mindmap_adds_fallback_h1_when_missing():
    client = _FakeClient(["## Ramo\n- item"])

    outline = await generate_mindmap_from_documents(client, "modelo", [("bio.pdf", "texto")])

    assert outline == "# Mapa mental\n## Ramo\n- item"


@pytest.mark.asyncio
async def test_generate_mindmap_large_text_uses_summaries_as_source(monkeypatch):
    monkeypatch.setattr(summarize, "_SINGLE_CALL_MAX_CHARS", 10)
    client = _FakeClient(["parcial 1", "parcial 2", "# Mapa\n## Grande\n- item"])

    outline = await generate_mindmap_from_documents(
        client,
        "modelo",
        [("grande.pdf", "a" * 9001)],
    )

    assert outline == "# Mapa\n## Grande\n- item"
    assert len(client.calls) == 3
    assert "parcial 1" in client.prompts[-1]
    assert "parcial 2" in client.prompts[-1]
