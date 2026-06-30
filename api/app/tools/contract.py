"""Contrato de contexto para ferramentas — tool-output budgeting (issue #32).

A saída das ferramentas (extração de PDF, RAG, busca web, plotação) é o maior
risco de estouro da janela: um PDF inteiro extraído, dezenas de resultados de
busca, dados de um gráfico. Para que o orçamento do Context Assembler (issue #30)
continue valendo, toda ferramenta segue **um protocolo único**:

    tool.run() ──► artefato completo ──► S3 / pgvector / DB   (fora do prompt)
              └─► summary_for_context ──► Context Assembler   (cota da tool)

Ou seja, a ferramenta devolve **(a)** um artefato completo persistido e **(b)**
um resumo curto + a referência ao artefato. **Só (b) entra no contexto**, e
sempre dentro de uma cota de tokens. O conteúdo cru nunca vai inteiro ao prompt:
ele vira artefato recuperável (e, quando houver RAG — issue #34 — reentra por
recuperação seletiva, nunca inteiro).

Este módulo é a **fundação** das issues de ferramenta (#33 extração, #34 RAG,
#35 busca, plotação): cada uma produz um ``ToolResult`` via ``fit_to_budget`` e o
Context Assembler recebe apenas ``summary_for_context``.

A lógica de corte é **pura** (sem I/O) para ser testável de forma determinística.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..context import estimate_tokens

# Aviso anexado ao resumo quando a saída foi truncada para caber na cota.
# Aponta para o artefato completo, deixando explícito ao modelo que há mais.
DEFAULT_TRUNCATION_NOTICE = "[…saída truncada para caber no contexto; conteúdo completo em {ref}]"


@dataclass
class ToolResult:
    """Resultado padronizado de uma ferramenta.

    Apenas ``summary_for_context`` entra no prompt; ``artifact_ref`` aponta para
    o conteúdo completo persistido fora do contexto (S3 key, id no DB, id no
    vetor). ``tokens`` é o custo do resumo no prompt (insumo da observabilidade,
    issue #37). ``truncated`` indica que o resumo foi cortado para caber na cota.
    """

    summary_for_context: str
    artifact_ref: str
    tokens: int
    truncated: bool = False


@runtime_checkable
class Tool(Protocol):
    """Interface comum das ferramentas do agente.

    A implementação persiste o artefato completo e usa ``fit_to_budget`` para
    montar o ``ToolResult`` dentro da cota antes de devolvê-lo ao assembler.
    """

    name: str

    async def run(self, **kwargs) -> ToolResult: ...


def fit_to_budget(
    raw_output: str,
    *,
    artifact_ref: str,
    max_tokens: int,
    notice: str = DEFAULT_TRUNCATION_NOTICE,
) -> ToolResult:
    """Encaixa a saída crua de uma ferramenta na cota de tokens.

    - Se cabe na cota, o resumo é a própria saída (``truncated=False``).
    - Se estoura, trunca deterministicamente para ~``max_tokens`` e anexa um
      aviso apontando para ``artifact_ref`` — o conteúdo completo continua
      recuperável fora do prompt. A truncagem reserva espaço para o aviso, de
      modo que o resultado final **nunca** excede ``max_tokens``.

    A truncagem é determinística (sem LLM) para ser barata e testável; uma
    sumarização semântica opcional pode ser plugada por cima reaproveitando o
    ``build_summarizer`` do Context Assembler.
    """
    quota = max(1, max_tokens)
    if estimate_tokens(raw_output) <= quota:
        return ToolResult(
            summary_for_context=raw_output,
            artifact_ref=artifact_ref,
            tokens=estimate_tokens(raw_output),
            truncated=False,
        )

    suffix = "\n" + notice.format(ref=artifact_ref)
    suffix_tokens = estimate_tokens(suffix)
    # Espaço para o conteúdo, já descontado o aviso (mínimo de 1 token).
    body_tokens = max(1, quota - suffix_tokens)
    body = raw_output[: body_tokens * 4]
    summary = body + suffix
    # Garante a cota mesmo se a heurística de chars/token oscilar.
    while estimate_tokens(summary) > quota and len(body) > 0:
        body = body[: max(0, len(body) - 16)]
        summary = body + suffix

    return ToolResult(
        summary_for_context=summary,
        artifact_ref=artifact_ref,
        tokens=estimate_tokens(summary),
        truncated=True,
    )


def collect_tool_block(results: list[ToolResult], *, max_tokens: int) -> str | None:
    """Combina vários ``ToolResult`` num único bloco dentro de uma cota total.

    Usado quando mais de uma ferramenta roda no mesmo turno. Concatena os resumos
    em ordem, parando assim que a cota total se esgota (ferramentas anteriores têm
    prioridade). Retorna ``None`` quando não há nada a injetar.

    O texto resultante é o ``tool_output`` passado ao ``ContextBudget.assemble``,
    que ainda aplica o corte final caso o orçamento global esteja apertado.
    """
    quota = max(1, max_tokens)
    parts: list[str] = []
    used = 0
    for r in results:
        if not r.summary_for_context:
            continue
        cost = estimate_tokens(r.summary_for_context)
        if used + cost > quota:
            remaining = quota - used
            if remaining <= 0:
                break
            fitted = fit_to_budget(
                r.summary_for_context,
                artifact_ref=r.artifact_ref,
                max_tokens=remaining,
            )
            parts.append(fitted.summary_for_context)
            break
        parts.append(r.summary_for_context)
        used += cost

    if not parts:
        return None
    block = "\n\n".join(parts)
    # Salvaguarda final: o arredondamento de chars/token na concatenação pode
    # somar um ou dois tokens; garante o teto duro da cota.
    if estimate_tokens(block) > quota:
        block = block[: quota * 4]
    return block
