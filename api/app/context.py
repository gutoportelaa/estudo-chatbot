"""Context Assembler — gestão de histórico com janela deslizante + sumarização.

Estratégia híbrida (issue #31):

    mensagens antigas (fora da janela) ── LLM resumidor ──► resumo persistido
    últimas N mensagens ───────────────────────────────────► entram verbatim

O montador final entrega: ``system + [memória/resumo] + recentes``

ContextBudget (issue #30):

    Garante que o prompt total respeite o limite do modelo. Blocos ordenados
    do mais estável ao mais dinâmico (prefixo estável ↔ prefix caching).
    Política de corte: tool → rag → recentes → resumo (system nunca é cortado).

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

# Janelas de contexto por modelo (tokens). Usado pelo ContextBudget.
_CONTEXT_WINDOWS: dict[str, int] = {
    # Google Gemini
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    "gemini-1.5-flash": 1_048_576,
    "gemini-1.5-pro": 2_097_152,
    # Groq / Meta Llama
    "llama-3.1-8b-instant": 131_072,
    "llama-3.3-70b-versatile": 131_072,
    "llama3-8b-8192": 8_192,
    # Ollama (modelos locais comuns)
    "llama3.2": 131_072,
    "llama3.2:3b": 131_072,
    "mistral": 32_768,
    "qwen2.5": 131_072,
}
_DEFAULT_CONTEXT_WINDOW = 32_768


def estimate_tokens(text: str) -> int:
    """Estimativa barata de tokens (~4 caracteres por token).

    Evita uma dependência de tokenizer; suficiente para decidir limiares.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _messages_tokens(messages: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(m.get("content", "")) for m in messages)


@dataclass
class TokenBreakdown:
    """Quebra de tokens do prompt por bloco (após a política de corte).

    Insumo da observabilidade (issue #37): permite responder, por turno, "onde
    foram os tokens?". Os campos somam ``total`` (os tokens de entrada).
    """

    system: int = 0
    summary: int = 0
    rag: int = 0
    recent: int = 0
    tool: int = 0
    total: int = 0


# ---------------------------------------------------------------------------
# ContextBudget — issue #30
# ---------------------------------------------------------------------------


@dataclass
class ContextBudget:
    """Gerencia o orçamento de tokens do prompt.

    Garante que ``tokens(prompt) <= context_window - reserve_output``.
    Blocos montados na ordem estável→dinâmico (friendly para prefix caching):

        system → resumo/memória → hits de RAG → últimas N mensagens → tool output

    Política de corte (quando o orçamento estoura):
        1. tool_output é truncado
        2. rag_hits são removidos (do último para o primeiro)
        3. recent é encurtado (remove as mais antigas da janela)
        4. resumo é truncado em último caso
        (system nunca é cortado)
    """

    model: str = ""
    reserve_output: int = 1024  # tokens reservados para a resposta do LLM
    # Preenchido a cada ``assemble`` com a quebra final por bloco (issue #37).
    breakdown: TokenBreakdown | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def context_window(self) -> int:
        """Janela de contexto do modelo em tokens."""
        if self.model in _CONTEXT_WINDOWS:
            return _CONTEXT_WINDOWS[self.model]
        # Tenta match por prefixo (ex: "llama3.2:3b" → "llama3.2")
        base = self.model.split(":")[0]
        for key, val in _CONTEXT_WINDOWS.items():
            if key.startswith(base) or base.startswith(key):
                return val
        return _DEFAULT_CONTEXT_WINDOW

    @property
    def budget(self) -> int:
        return max(1, self.context_window - self.reserve_output)

    def assemble(
        self,
        *,
        system: str,
        summary: str | None = None,
        rag_hits: list[dict[str, str]] | None = None,
        recent: list[dict[str, str]],
        tool_output: str | None = None,
    ) -> list[dict[str, str]]:
        """Monta os blocos do prompt respeitando o orçamento.

        Retorna a lista final de mensagens prontas para o LLM.
        Emite um log estruturado com a quebra de tokens por bloco.
        """
        rag_hits = list(rag_hits or [])
        recent = list(recent)

        # Os blocos rotulados ganham um cabeçalho em `_build_blocks`; contamos o
        # overhead do rótulo aqui para que a garantia valha sobre o que de fato
        # é emitido, não só sobre o conteúdo cru.
        tokens_system = estimate_tokens(system)
        t_summary = estimate_tokens(summary or "")
        if summary:
            t_summary += estimate_tokens(f"{MEMORY_HEADER}\n")
        t_rag = _messages_tokens(rag_hits)
        if rag_hits:
            t_rag += estimate_tokens("[Trechos relevantes do material]\n")
        t_recent = _messages_tokens(recent)
        t_tool = estimate_tokens(tool_output or "")
        if tool_output:
            t_tool += estimate_tokens("[Saída de ferramenta]\n")

        def _over() -> int:
            return (tokens_system + t_summary + t_rag + t_recent + t_tool) - self.budget

        # --- Política de corte ---
        # 1. Truncar tool_output
        if _over() > 0 and tool_output:
            keep_chars = max(0, len(tool_output) - _over() * 4)
            tool_output = tool_output[:keep_chars] if keep_chars else None
            t_tool = estimate_tokens(tool_output or "")

        # 2. Remover rag_hits (do último ao primeiro)
        while _over() > 0 and rag_hits:
            removed = rag_hits.pop()
            t_rag -= estimate_tokens(removed.get("content", ""))

        # 3. Encurtar recent (remove as mais antigas)
        while _over() > 0 and len(recent) > 1:
            removed = recent.pop(0)
            t_recent -= estimate_tokens(removed.get("content", ""))

        # 3b. Último recurso na janela: truncar o conteúdo da mensagem restante
        # quando uma única mensagem recente, sozinha, já estoura o orçamento.
        if _over() > 0 and recent:
            content = recent[-1].get("content", "")
            keep_chars = max(0, len(content) - _over() * 4)
            recent[-1] = {**recent[-1], "content": content[:keep_chars]}
            t_recent = _messages_tokens(recent)

        # 4. Truncar resumo
        if _over() > 0 and summary:
            keep_chars = max(0, len(summary) - _over() * 4)
            summary = summary[:keep_chars] if keep_chars else None
            t_summary = estimate_tokens(summary or "")

        final_tokens = tokens_system + t_summary + t_rag + t_recent + t_tool

        self.breakdown = TokenBreakdown(
            system=tokens_system,
            summary=t_summary,
            rag=t_rag,
            recent=t_recent,
            tool=t_tool,
            total=final_tokens,
        )

        logger.info(
            "context_budget model=%s window=%d budget=%d "
            "tokens_system=%d tokens_summary=%d tokens_rag=%d "
            "tokens_recent=%d tokens_tool=%d tokens_total=%d",
            self.model or "(default)",
            self.context_window,
            self.budget,
            tokens_system,
            t_summary,
            t_rag,
            t_recent,
            t_tool,
            final_tokens,
        )

        return _build_blocks(
            system=system,
            summary=summary,
            rag_hits=rag_hits,
            recent=recent,
            tool_output=tool_output,
        )


def _build_blocks(
    *,
    system: str,
    summary: str | None,
    rag_hits: list[dict[str, str]],
    recent: list[dict[str, str]],
    tool_output: str | None,
) -> list[dict[str, str]]:
    """Monta a lista de mensagens na ordem canônica de blocos."""
    out: list[dict[str, str]] = [{"role": "system", "content": system}]
    if summary:
        out.append({"role": "system", "content": f"{MEMORY_HEADER}\n{summary}"})
    if rag_hits:
        combined = "\n\n".join(m.get("content", "") for m in rag_hits)
        out.append({"role": "system", "content": f"[Trechos relevantes do material]\n{combined}"})
    out.extend(recent)
    if tool_output:
        out.append({"role": "system", "content": f"[Saída de ferramenta]\n{tool_output}"})
    return out


# ---------------------------------------------------------------------------
# Histórico (issue #31) — planejamento puro
# ---------------------------------------------------------------------------


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


def _assemble_metered(
    *,
    system_prompt: str,
    summary: str | None,
    recent: list[Message],
    model: str,
    rag_hits: list[dict[str, str]] | None = None,
    tool_output: str | None = None,
) -> tuple[list[dict[str, str]], TokenBreakdown]:
    """Monta o prompt e devolve também a quebra de tokens por bloco (issue #37)."""
    recent_dicts = [{"role": m.role, "content": m.content} for m in recent]
    budget = ContextBudget(model=model)
    messages = budget.assemble(
        system=system_prompt,
        summary=summary,
        rag_hits=rag_hits,
        recent=recent_dicts,
        tool_output=tool_output,
    )
    return messages, budget.breakdown or TokenBreakdown()


def build_messages(
    *,
    system_prompt: str,
    summary: str | None,
    recent: list[Message],
    model: str = "",
) -> list[dict[str, str]]:
    """Monta a lista final via ContextBudget: system + bloco de memória + recentes.

    Aceita ``model`` para registrar o log de tokens correto por turno.
    """
    messages, _ = _assemble_metered(
        system_prompt=system_prompt, summary=summary, recent=recent, model=model
    )
    return messages


# ---------------------------------------------------------------------------
# I/O: carga de histórico, sumarização e persistência
# ---------------------------------------------------------------------------


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
    model: str = "",
    rag_hits: list[dict[str, str]] | None = None,
    tool_output: str | None = None,
) -> tuple[list[dict[str, str]], TokenBreakdown]:
    """Carrega o histórico, aplica a estratégia e devolve ``(mensagens, quebra)``.

    Quando há mensagens fora da janela acima do limiar e um ``summarizer`` é
    fornecido, gera/atualiza o resumo e persiste a compactação (auditoria).

    ``rag_hits`` (issue #34) são os trechos recuperados do material; entram no
    bloco de RAG do prompt, com cota própria de tokens.

    O ``model`` é repassado ao ``ContextBudget`` para o log de tokens correto; a
    ``TokenBreakdown`` retornada alimenta a observabilidade do turno (issue #37).
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
            return _assemble_metered(
                system_prompt=system_prompt,
                summary=prior_summary,
                recent=plan.to_summarize + plan.recent,
                model=model,
                rag_hits=rag_hits,
                tool_output=tool_output,
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

    return _assemble_metered(
        system_prompt=system_prompt,
        summary=summary_text,
        recent=plan.recent,
        model=model,
        rag_hits=rag_hits,
        tool_output=tool_output,
    )


# ---------------------------------------------------------------------------
# Fábrica de resumidor (OpenAI-compatível)
# ---------------------------------------------------------------------------


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
