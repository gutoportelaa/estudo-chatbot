"""Testes da gestão de histórico (janela deslizante + sumarização híbrida).

Focam na lógica pura `plan_history` — onde mora o critério de aceitação:
os tokens de histórico estabilizam em vez de crescer linearmente com os turnos.
"""

from __future__ import annotations

from app.config import Settings
from app.context import (
    MEMORY_HEADER,
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
