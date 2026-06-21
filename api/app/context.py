"""Context Assembler — gestão de histórico com janela deslizante + sumarização.

Estratégia híbrida (issue #31):

    mensagens antigas (fora da janela) ── LLM resumidor ──► resumo persistido
    últimas N mensagens ───────────────────────────────────► entram verbatim

O montador final entrega: ``system + [memória/resumo] + recentes``.

A lógica de planejamento (`plan_history`) é **pura** — sem I/O — para ser
testável de forma determinística. A orquestração (`assemble_messages`) cuida do
banco, dispara a sumarização e persiste cada compactação como linha de
auditoria em ``conversation_summaries``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .models import ConversationSummary, Message

logger = logging.getLogger("thinkai.context")

# Resumidor: recebe (resumo_anterior | None, mensagens_a_condensar) -> novo_resumo.
Summarizer = Callable[[str | None, list[dict[str, str]]], Awaitable[str]]

# Rótulo do bloco de "memória" injetado como contexto do sistema.
MEMORY_HEADER = "[Memória da conversa — resumo do histórico anterior]"


def estimate_tokens(text: str) -> int:
    """Estimativa barata de tokens (~4 caracteres por token).

    Evita uma dependência de tokenizer; suficiente para decidir limiares.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class HistoryPlan:
    """Resultado do planejamento de histórico de um turno."""

    # Resumo vigente ANTES de uma eventual nova compactação deste turno.
    prior_summary: str | None
    # Quantas mensagens (do início) já estão cobertas pelo resumo vigente.
    covered_count: int
    # Mensagens que devem ser condensadas agora (saíram da janela).
    to_summarize: list[Message] = field(default_factory=list)
    # Mensagens recentes mantidas verbatim.
    recent: list[Message] = field(default_factory=list)

    @property
    def should_summarize(self) -> bool:
        return len(self.to_summarize) > 0


def plan_history(
    messages: list[Message],
    *,
    covered_count: int,
    prior_summary: str | None,
    settings: Settings,
) -> HistoryPlan:
    """Decide, de forma pura, o que condensar e o que manter verbatim.

    - ``messages``: todas as mensagens da sessão, em ordem cronológica.
    - ``covered_count``: quantas mensagens iniciais já estão no resumo vigente.

    Mantém as últimas ``history_window_messages`` verbatim. As mensagens que
    saem da janela só são condensadas quando acumulam pelo menos
    ``history_summarize_after_messages`` — assim os tokens verbatim oscilam num
    intervalo limitado (janela .. janela + limiar) em vez de crescer linearmente.
    """
    window = max(1, settings.history_window_messages)
    threshold = max(1, settings.history_summarize_after_messages)

    uncovered = messages[covered_count:]

    if settings.history_strategy == "off":
        return HistoryPlan(prior_summary=None, covered_count=0, recent=messages)

    if settings.history_strategy == "window":
        # Só janela deslizante: descarta o passado, sem resumo.
        return HistoryPlan(
            prior_summary=None,
            covered_count=covered_count,
            recent=uncovered[-window:],
        )

    # ----- hybrid -----
    if len(uncovered) <= window:
        # Tudo cabe na janela; nada a condensar ainda.
        return HistoryPlan(
            prior_summary=prior_summary,
            covered_count=covered_count,
            recent=uncovered,
        )

    overflow = uncovered[:-window]
    recent = uncovered[-window:]

    if len(overflow) < threshold:
        # Saíram da janela, mas ainda não atingiram o limiar de compactação:
        # mantém verbatim para não perder informação até valer a chamada ao LLM.
        return HistoryPlan(
            prior_summary=prior_summary,
            covered_count=covered_count,
            recent=uncovered,
        )

    return HistoryPlan(
        prior_summary=prior_summary,
        covered_count=covered_count,
        to_summarize=overflow,
        recent=recent,
    )


def build_messages(
    *,
    system_prompt: str,
    summary: str | None,
    recent: list[Message],
) -> list[dict[str, str]]:
    """Monta a lista final: system + bloco de memória (resumo) + recentes."""
    out: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if summary:
        out.append({"role": "system", "content": f"{MEMORY_HEADER}\n{summary}"})
    out.extend({"role": m.role, "content": m.content} for m in recent)
    return out


async def _latest_summary(db: AsyncSession, session_id: str) -> ConversationSummary | None:
    return await db.scalar(
        select(ConversationSummary)
        .where(ConversationSummary.session_id == session_id)
        .order_by(ConversationSummary.created_at.desc(), ConversationSummary.covered_message_count.desc())
        .limit(1)
    )


async def list_summaries(db: AsyncSession, session_id: str) -> list[ConversationSummary]:
    """Log de auditoria: todas as compactações da sessão, em ordem cronológica."""
    rows = await db.scalars(
        select(ConversationSummary)
        .where(ConversationSummary.session_id == session_id)
        .order_by(ConversationSummary.created_at.asc())
    )
    return list(rows.all())


async def assemble_messages(
    db: AsyncSession,
    *,
    session_id: str,
    system_prompt: str,
    settings: Settings,
    summarizer: Summarizer | None = None,
    summarizer_model: str = "",
) -> list[dict[str, str]]:
    """Carrega o histórico, aplica a estratégia e devolve as mensagens do prompt.

    Quando há mensagens fora da janela acima do limiar e um ``summarizer`` é
    fornecido, gera/atualiza o resumo e persiste a compactação (auditoria).
    """
    rows = list(
        (
            await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
        ).scalars()
    )

    latest = await _latest_summary(db, session_id)
    covered = latest.covered_message_count if latest else 0
    prior_summary = latest.summary if latest else None

    plan = plan_history(
        rows,
        covered_count=covered,
        prior_summary=prior_summary,
        settings=settings,
    )

    summary_text = plan.prior_summary

    if plan.should_summarize and summarizer is not None:
        condensed = [{"role": m.role, "content": m.content} for m in plan.to_summarize]
        try:
            new_summary = (await summarizer(prior_summary, condensed)).strip()
        except Exception:  # pragma: no cover - resiliência: não quebra o chat
            logger.exception("Falha ao sumarizar histórico da sessão %s", session_id)
            # Sem resumo novo: mantém as mensagens verbatim para não perder contexto.
            return build_messages(
                system_prompt=system_prompt,
                summary=prior_summary,
                recent=plan.to_summarize + plan.recent,
            )

        if new_summary:
            # Recompactação (resumo-de-resumo) quando o resumo anterior já estava
            # acima do limiar de tokens — registrado para auditoria.
            over_threshold = (
                prior_summary is not None
                and estimate_tokens(prior_summary) >= settings.history_summary_max_tokens
            )
            trigger = "recompaction" if over_threshold else "window_overflow"
            new_covered = covered + len(plan.to_summarize)
            tokens = estimate_tokens(new_summary)

            db.add(
                ConversationSummary(
                    session_id=session_id,
                    summary=new_summary,
                    covered_message_count=new_covered,
                    source_message_count=len(plan.to_summarize),
                    summary_tokens=tokens,
                    trigger=trigger,
                    model=summarizer_model,
                    created_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

            logger.info(
                "Compactação de histórico sessão=%s gatilho=%s condensadas=%d "
                "cobertas=%d tokens_resumo=%d modelo=%s",
                session_id,
                trigger,
                len(plan.to_summarize),
                new_covered,
                tokens,
                summarizer_model or "(chat)",
            )
            summary_text = new_summary

    return build_messages(
        system_prompt=system_prompt,
        summary=summary_text,
        recent=plan.recent,
    )


def build_summarizer(
    *,
    client,
    model: str,
    max_tokens: int,
) -> Summarizer:
    """Cria um resumidor baseado em chat completion (OpenAI-compatível).

    Reescreve o resumo vigente incorporando as novas mensagens (sumarização
    incremental); quando o resultado tende a crescer, o próprio prompt instrui a
    comprimir partes antigas (recompactação resumo-de-resumo).
    """
    target_words = max(80, max_tokens // 2)

    async def _summarize(prior_summary: str | None, condensed: list[dict[str, str]]) -> str:
        transcript = "\n".join(
            f"{'Usuário' if m['role'] == 'user' else 'Assistente'}: {m['content']}"
            for m in condensed
        )
        base = (
            "Você condensa o histórico de uma conversa para servir de memória de "
            "longo prazo a um assistente. Reescreva o RESUMO existente incorporando "
            "as NOVAS MENSAGENS, preservando fatos, decisões, preferências, nomes, "
            "números e pendências. Seja factual e conciso, não invente, escreva em "
            f"português, em no máximo ~{target_words} palavras. Se o resumo crescer "
            "demais, comprima as partes mais antigas mantendo o essencial."
        )
        user = (
            f"RESUMO ATUAL:\n{prior_summary or '(vazio)'}\n\n"
            f"NOVAS MENSAGENS:\n{transcript}\n\n"
            "RESUMO ATUALIZADO:"
        )
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": base},
                {"role": "user", "content": user},
            ],
            stream=False,
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    return _summarize
