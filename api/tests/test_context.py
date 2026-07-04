"""Testes da gestão de histórico (janela deslizante + sumarização híbrida).

Focam na lógica pura `plan_history` — onde mora o critério de aceitação:
os tokens de histórico estabilizam em vez de crescer linearmente com os turnos.
"""

from __future__ import annotations

from app.config import Settings
from app.context import (
    MEMORY_HEADER,
    ContextBudget,
    build_messages,
    estimate_tokens,
    plan_history,
)
from app.models import Message


def _msg(i: int, role: str = "user") -> Message:
    return Message(session_id="s", role=role, content=f"mensagem número {i} " * 4)


def _settings(**over) -> Settings:
    base = dict(
        history_strategy="hybrid",
        history_window_messages=4,
        history_summarize_after_messages=2,
        history_summary_max_tokens=600,
    )
    base.update(over)
    return Settings(**base)


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100


def test_strategy_off_keeps_everything_verbatim():
    msgs = [_msg(i) for i in range(10)]
    plan = plan_history(msgs, covered_count=0, prior_summary=None, settings=_settings(history_strategy="off"))
    assert plan.recent == msgs
    assert plan.prior_summary is None
    assert not plan.should_summarize


def test_strategy_window_drops_past_without_summary():
    msgs = [_msg(i) for i in range(10)]
    plan = plan_history(msgs, covered_count=0, prior_summary=None, settings=_settings(history_strategy="window"))
    assert len(plan.recent) == 4
    assert plan.recent == msgs[-4:]
    assert not plan.should_summarize


def test_hybrid_below_window_keeps_all():
    msgs = [_msg(i) for i in range(3)]
    plan = plan_history(msgs, covered_count=0, prior_summary=None, settings=_settings())
    assert plan.recent == msgs
    assert not plan.should_summarize


def test_hybrid_overflow_below_threshold_keeps_verbatim():
    # window=4, threshold=2: 5 mensagens -> overflow=1 < 2 -> mantém verbatim.
    msgs = [_msg(i) for i in range(5)]
    plan = plan_history(msgs, covered_count=0, prior_summary=None, settings=_settings())
    assert not plan.should_summarize
    assert plan.recent == msgs


def test_hybrid_triggers_summary_above_threshold():
    # window=4, threshold=2: 6 mensagens -> overflow=2 -> sumariza.
    msgs = [_msg(i) for i in range(6)]
    plan = plan_history(msgs, covered_count=0, prior_summary=None, settings=_settings())
    assert plan.should_summarize
    assert plan.to_summarize == msgs[:2]
    assert plan.recent == msgs[-4:]


def test_hybrid_respects_already_covered():
    msgs = [_msg(i) for i in range(10)]
    # 4 já cobertas; restam 6 -> overflow=2 -> sumariza as mensagens 4 e 5.
    plan = plan_history(msgs, covered_count=4, prior_summary="resumo antigo", settings=_settings())
    assert plan.should_summarize
    assert plan.to_summarize == msgs[4:6]
    assert plan.recent == msgs[-4:]


def test_build_messages_includes_memory_block():
    msgs = [_msg(0, "user"), _msg(1, "assistant")]
    out = build_messages(system_prompt="SYS", summary="resumo X", recent=msgs)
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[1]["role"] == "system"
    assert MEMORY_HEADER in out[1]["content"]
    assert "resumo X" in out[1]["content"]
    assert out[2]["content"] == msgs[0].content


def test_build_messages_without_summary():
    out = build_messages(system_prompt="SYS", summary=None, recent=[_msg(0)])
    assert len(out) == 2
    assert all(MEMORY_HEADER not in m["content"] for m in out)


def test_token_stabilization_over_100_turns():
    """Critério de aceitação: o histórico verbatim não cresce com os turnos."""
    settings = _settings(history_window_messages=12, history_summarize_after_messages=6)
    msgs: list[Message] = []
    covered = 0
    summary = None
    max_recent_tokens = 0

    for turn in range(100):
        msgs.append(_msg(turn, "user"))
        msgs.append(_msg(turn, "assistant"))
        plan = plan_history(msgs, covered_count=covered, prior_summary=summary, settings=settings)

        if plan.should_summarize:
            # Simula o resumidor: resumo de tamanho limitado (não cresce sem fim).
            summary = ("resumo consolidado " * 20).strip()
            covered += len(plan.to_summarize)

        recent_tokens = sum(estimate_tokens(m.content) for m in plan.recent)
        max_recent_tokens = max(max_recent_tokens, recent_tokens)
        # A janela verbatim nunca passa de window + threshold mensagens.
        assert len(plan.recent) <= settings.history_window_messages + settings.history_summarize_after_messages

    # Após 200 mensagens, o passado foi majoritariamente condensado.
    assert covered >= 180
    # E o custo de tokens verbatim ficou limitado (não cresceu com 200 mensagens).
    assert max_recent_tokens < 400


# ---------------------------------------------------------------------------
# ContextBudget — issue #30
# ---------------------------------------------------------------------------


def test_context_window_resolves_by_exact_and_prefix_match():
    # Match exato na tabela.
    assert ContextBudget(model="gemini-2.5-flash").context_window == 1_048_576
    # Match por prefixo (variante de tag não listada cai no modelo base).
    assert ContextBudget(model="llama3.2:1b").context_window == 131_072
    # Modelo desconhecido usa o default conservador.
    assert ContextBudget(model="modelo-inexistente").context_window == 32_768


def test_budget_reserves_output_margin():
    budget = ContextBudget(model="llama3-8b-8192", reserve_output=1024)
    # budget = janela - reserva de resposta.
    assert budget.budget == 8_192 - 1024


def test_assemble_orders_blocks_stable_to_dynamic():
    budget = ContextBudget(model="gemini-2.5-flash")
    out = budget.assemble(
        system="SYS",
        summary="memória",
        rag_hits=[{"role": "system", "content": "trecho RAG"}],
        recent=[{"role": "user", "content": "oi"}],
        tool_output="saída da tool",
    )
    assert out[0] == {"role": "system", "content": "SYS"}
    assert MEMORY_HEADER in out[1]["content"]
    assert "trecho RAG" in out[2]["content"]
    assert out[3] == {"role": "user", "content": "oi"}
    assert "saída da tool" in out[-1]["content"]


def test_assemble_never_exceeds_budget():
    """Critério de aceitação: nenhum turno passa de context_window − reserva."""
    budget = ContextBudget(model="llama3-8b-8192", reserve_output=1024)
    big = "palavra " * 5000  # ~estoura sozinho a janela de 8k tokens
    out = budget.assemble(
        system="SYS",
        summary=big,
        rag_hits=[{"role": "system", "content": big}],
        recent=[{"role": "user", "content": big}, {"role": "assistant", "content": big}],
        tool_output=big,
    )
    total = sum(estimate_tokens(m["content"]) for m in out)
    assert total <= budget.budget


def test_cut_policy_drops_tool_then_rag_before_summary_and_system():
    """A política de corte sacrifica tool → rag → recentes antes do resumo/system."""
    budget = ContextBudget(model="llama3-8b-8192", reserve_output=1024)
    big = "palavra " * 5000
    out = budget.assemble(
        system="SYS",
        summary="memória curta",
        rag_hits=[{"role": "system", "content": big}],
        recent=[{"role": "user", "content": "pergunta recente"}],
        tool_output=big,
    )
    contents = " ".join(m["content"] for m in out)
    # system e resumo (estáveis) sobrevivem; tool e o RAG gigante cedem primeiro.
    assert "SYS" in contents
    assert "memória curta" in contents
    assert "[Saída de ferramenta]" not in contents
