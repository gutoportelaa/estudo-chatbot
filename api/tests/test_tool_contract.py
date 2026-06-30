"""Testes do contrato de contexto para ferramentas (issue #32).

Critério de aceitação central: a saída de uma ferramenta — por maior que seja o
conteúdo cru — nunca entra inteira no prompt; ela é encaixada numa cota de tokens
e o restante vira artefato recuperável (referenciado, fora do contexto).
"""

from __future__ import annotations

from app.context import estimate_tokens
from app.tools import ToolResult, collect_tool_block, fit_to_budget


def test_small_output_passes_through_untruncated():
    raw = "resumo curto da ferramenta"
    res = fit_to_budget(raw, artifact_ref="s3://bucket/key", max_tokens=2000)
    assert isinstance(res, ToolResult)
    assert res.summary_for_context == raw
    assert res.truncated is False
    assert res.tokens == estimate_tokens(raw)


def test_large_output_is_truncated_within_quota():
    """Critério: PDF de 80 páginas extraído não entra inteiro no prompt."""
    raw = "lorem ipsum " * 20_000  # muito acima da cota
    res = fit_to_budget(raw, artifact_ref="s3://bucket/doc.txt", max_tokens=500)
    assert res.truncated is True
    # Nunca excede a cota.
    assert estimate_tokens(res.summary_for_context) <= 500
    assert res.tokens == estimate_tokens(res.summary_for_context)
    # O conteúdo cru permanece recuperável fora do prompt.
    assert "s3://bucket/doc.txt" in res.summary_for_context


def test_truncation_notice_points_to_artifact():
    raw = "x" * 100_000
    res = fit_to_budget(raw, artifact_ref="vec://material/42", max_tokens=50)
    assert "vec://material/42" in res.summary_for_context
    assert estimate_tokens(res.summary_for_context) <= 50


def test_collect_tool_block_concatenates_within_total_quota():
    a = ToolResult(summary_for_context="bloco A", artifact_ref="r1", tokens=2)
    b = ToolResult(summary_for_context="bloco B", artifact_ref="r2", tokens=2)
    block = collect_tool_block([a, b], max_tokens=2000)
    assert block is not None
    assert "bloco A" in block
    assert "bloco B" in block


def test_collect_tool_block_respects_priority_and_total_quota():
    big = "palavra " * 5000  # estoura a cota sozinho
    a = ToolResult(summary_for_context="primeira tool, prioritária", artifact_ref="r1", tokens=10)
    b = ToolResult(summary_for_context=big, artifact_ref="r2", tokens=estimate_tokens(big))
    block = collect_tool_block([a, b], max_tokens=80)
    assert block is not None
    # A primeira tool (prioritária) sobrevive; o total respeita a cota.
    assert "primeira tool" in block
    assert estimate_tokens(block) <= 80


def test_collect_tool_block_empty_returns_none():
    assert collect_tool_block([], max_tokens=2000) is None
    empty = ToolResult(summary_for_context="", artifact_ref="r", tokens=0)
    assert collect_tool_block([empty], max_tokens=2000) is None
