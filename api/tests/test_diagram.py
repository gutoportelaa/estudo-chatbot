"""Testes do diagrama Mermaid (Diagramas e mapas mentais).

Cobre: detecção de intenção por heurística (mesmo padrão do RAG), validação
estrutural leve, o fallback que garante que o frontend nunca recebe Mermaid
quebrado, e o cache que garante "mesma entrada -> mesma saída". `fit_to_budget`
já tem cobertura própria em test_tool_contract.py; aqui só verificamos que
`generate_diagram` o invoca corretamente.
"""

from __future__ import annotations

import pytest

import app.tools.diagram as diagram_module
from app.context import estimate_tokens
from app.tools.diagram import (
    DiagramArtifact,
    _fallback_mermaid,
    _strip_code_fence,
    detect_diagram_intent,
    generate_diagram,
    validate_mermaid,
)


@pytest.fixture(autouse=True)
def _clear_diagram_cache():
    """O cache é um dict de módulo (compartilhado entre chamadas); isola os testes."""
    diagram_module._cache.clear()
    yield
    diagram_module._cache.clear()


# ---------------------------------------------------------------------------
# detect_diagram_intent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("faça um fluxograma do processo de matrícula", "flowchart"),
        ("gere um flowchart do login", "flowchart"),
        ("quero um diagrama de fluxo da API", "flowchart"),
        ("crie um mapa mental sobre biologia celular", "mindmap"),
        ("mind map do capítulo 3", "mindmap"),
        ("monte um diagrama de sequência do login", "sequence"),
        ("sequence diagram da autenticação", "sequence"),
    ],
)
def test_detect_diagram_intent_reconhece_palavras_chave(text, expected):
    assert detect_diagram_intent(text) == expected


def test_detect_diagram_intent_retorna_none_sem_palavra_chave():
    assert detect_diagram_intent("qual a capital da França?") is None


# ---------------------------------------------------------------------------
# validate_mermaid
# ---------------------------------------------------------------------------


def test_validate_mermaid_aceita_flowchart_valido():
    ok, reason = validate_mermaid("flowchart TD\n  A[Início] --> B[Fim]", "flowchart")
    assert ok is True
    assert reason is None


def test_validate_mermaid_rejeita_prosa():
    ok, reason = validate_mermaid("Claro! Aqui está o diagrama que você pediu:", "flowchart")
    assert ok is False
    assert reason is not None


def test_validate_mermaid_rejeita_colchetes_desbalanceados():
    ok, _ = validate_mermaid("flowchart TD\n  A[Início --> B[Fim]", "flowchart")
    assert ok is False


def test_validate_mermaid_rejeita_saida_vazia():
    ok, reason = validate_mermaid("   ", "mindmap")
    assert ok is False
    assert reason == "saída vazia"


def test_validate_mermaid_aceita_mindmap_e_sequence():
    assert validate_mermaid("mindmap\n  root((Tema))", "mindmap")[0] is True
    assert validate_mermaid("sequenceDiagram\n  A->>B: oi", "sequence")[0] is True


# ---------------------------------------------------------------------------
# _strip_code_fence / _fallback_mermaid
# ---------------------------------------------------------------------------


def test_strip_code_fence_remove_cercas_mermaid():
    raw = "```mermaid\nflowchart TD\n  A --> B\n```"
    assert _strip_code_fence(raw) == "flowchart TD\n  A --> B"


def test_strip_code_fence_texto_sem_cerca_fica_igual():
    assert _strip_code_fence("flowchart TD\n  A --> B") == "flowchart TD\n  A --> B"


@pytest.mark.parametrize("tipo", ["flowchart", "mindmap", "sequence"])
def test_fallback_mermaid_sempre_valido(tipo):
    fallback = _fallback_mermaid(tipo, "motivo qualquer com (parênteses) e [colchetes]")
    ok, _ = validate_mermaid(fallback, tipo)
    assert ok is True


# ---------------------------------------------------------------------------
# generate_diagram — cache + resiliência (client LLM stub, sem rede)
# ---------------------------------------------------------------------------


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)
        self.chat = _FakeChat(self.completions)


async def test_generate_diagram_valida_e_devolve_tool_result():
    client = _FakeClient("flowchart TD\n  A[Início] --> B[Fim]")
    artifact, result = await generate_diagram(
        "flowchart", "processo qualquer", client=client, model="m", max_tokens=500
    )
    assert isinstance(artifact, DiagramArtifact)
    assert artifact.cached is False
    assert artifact.mermaid.startswith("flowchart TD")
    assert result.summary_for_context == artifact.mermaid
    assert client.completions.calls == 1


async def test_generate_diagram_cache_hit_nao_chama_llm_de_novo():
    client = _FakeClient("mindmap\n  root((Tema))")
    tipo, conteudo = "mindmap", "estrutura de um sistema operacional único para este teste"

    first, _ = await generate_diagram(tipo, conteudo, client=client, model="m", max_tokens=500)
    second, _ = await generate_diagram(tipo, conteudo, client=client, model="m", max_tokens=500)

    assert client.completions.calls == 1  # só a 1ª chamada bateu no LLM
    assert first.cached is False
    assert second.cached is True
    assert second.mermaid == first.mermaid  # mesma entrada -> mesma saída


async def test_generate_diagram_saida_invalida_usa_fallback():
    client = _FakeClient("Claro! Vou te ajudar com isso.")
    artifact, _ = await generate_diagram(
        "sequence", "conteúdo qualquer para o teste de fallback", client=client, model="m", max_tokens=500
    )
    ok, _ = validate_mermaid(artifact.mermaid, "sequence")
    assert ok is True  # fallback é sempre válido


async def test_generate_diagram_respeita_max_tokens_via_fit_to_budget():
    client = _FakeClient("flowchart TD\n  " + "A[nó] --> B[nó]\n  " * 2000)
    _, result = await generate_diagram(
        "flowchart",
        "conteúdo grande e único para não bater no cache de outro teste",
        client=client,
        model="m",
        max_tokens=50,
    )
    assert estimate_tokens(result.summary_for_context) <= 50
