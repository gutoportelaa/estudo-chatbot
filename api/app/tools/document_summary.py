"""Resumo de documentos — individual e consolidado (issues #44/#45).

Reaproveita o mesmo client/model do chat (``llm.resolve_client``) e o mesmo
princípio de orçamento de tokens do contrato de ferramentas (#32): o texto de
cada documento é cortado para caber numa cota antes de entrar no prompt do
LLM — nunca colamos o material inteiro cru no prompt.

    single: 1 documento → resumo direto
    consolidated: N documentos → síntese integrando todos, citando a origem
"""

from __future__ import annotations

from typing import Literal

from openai import AsyncOpenAI

from ..context import estimate_tokens

_SINGLE_SYSTEM_PROMPT = (
    "Você é um assistente que resume documentos de estudo. Gere um resumo "
    "claro e objetivo do documento a seguir, em português, destacando os "
    "pontos principais."
)

_CONSOLIDATED_SYSTEM_PROMPT = (
    "Você é um assistente que sintetiza múltiplos documentos de estudo. Gere "
    "um resumo consolidado que integre os pontos principais de todos os "
    "documentos a seguir, indicando entre parênteses de qual documento vem "
    "cada ponto relevante."
)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    return text[: max(0, max_tokens) * 4]


async def generate_summary(
    *,
    client: AsyncOpenAI,
    model: str,
    kind: Literal["single", "consolidated"],
    documents: list[tuple[str, str]],
    max_input_tokens: int,
) -> str:
    """Gera um resumo — ``single``: 1 documento; ``consolidated``: síntese de N.

    Divide ``max_input_tokens`` igualmente entre os documentos antes de montar
    o prompt, para que nenhum documento sozinho estoure a cota de entrada.
    """
    per_doc_budget = max(1, max_input_tokens // max(1, len(documents)))
    parts = [
        f"[Documento: {filename}]\n{_truncate_to_tokens(text, per_doc_budget)}"
        for filename, text in documents
    ]
    body = "\n\n".join(parts)

    system_prompt = _CONSOLIDATED_SYSTEM_PROMPT if kind == "consolidated" else _SINGLE_SYSTEM_PROMPT
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": body},
        ],
    )
    return (response.choices[0].message.content or "").strip()
