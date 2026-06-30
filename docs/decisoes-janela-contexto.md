# Decisões de implementação — Janela de contexto do chatbot

> Relatório técnico das decisões tomadas ao implementar o épico "gestão da janela
> de contexto" (issues #30–#32, #37). Complementa o planejamento em
> [`issues-iniciais-contexto.md`](./issues-iniciais-contexto.md): lá está o
> *porquê* de cada issue; aqui ficam as decisões de *como* foram resolvidas, as
> alternativas descartadas e os pontos no código. Atualizado a cada issue do épico.

## Visão geral

O recurso escasso central do chat é a **janela de contexto** do modelo. O épico
estabelece, em camadas, uma garantia dura: **nenhum turno excede
`context_window − reserva_de_resposta`**, em qualquer provedor (Gemini, Groq,
Ollama). As três famílias de ferramentas (extração, RAG, busca, plotação) plugam
sobre essa fundação negociando cotas, em vez de injetar conteúdo livremente.

| Issue | Tema | Status |
|---|---|---|
| #30 | Context Assembler + orçamento de tokens | **Concluída** (branch `feat/context-budget` → `dev`) |
| #31 | Histórico: janela deslizante + sumarização | Concluída anteriormente |
| #32 | Contrato de contexto para ferramentas | **Concluída** (branch `feat/tool-context-contract` → `dev`) |
| #37 | Observabilidade de tokens/custo por turno | Pendente (já alimentada pelos logs de #30) |

---

## #30 — Context Assembler + orçamento de tokens

**Onde:** `api/app/context.py` (`ContextBudget`), integrado em `api/app/llm.py`.

### Decisões

- **Janela por modelo via tabela estática (`_CONTEXT_WINDOWS`) + fallback.**
  Mapeamos os modelos usados (Gemini 2.5/2.0/1.5, Llama via Groq, modelos Ollama)
  para suas janelas. Modelo desconhecido cai num default conservador de
  `32_768`. Há *match* por prefixo para resolver variantes de tag (ex.:
  `llama3.2:1b` → `llama3.2`). **Alternativa descartada:** consultar a API do
  provedor por metadados de modelo — acrescentaria I/O e latência a cada turno
  para um dado que muda raramente.

- **Contagem de tokens por heurística (~4 chars/token), não tokenizer real.**
  Evita uma dependência de tokenizer por provedor. A imprecisão é absorvida pela
  **margem reservada para a resposta** (`reserve_output`, default 1024). O custo
  de um tokenizer exato não se justifica para *decidir limiares de corte*.

- **Ordem fixa de blocos, do estável ao dinâmico** (amigável a *prefix
  caching*): `system → resumo/memória → hits de RAG → últimas N mensagens →
  saída de ferramenta`. O prefixo estável na frente maximiza reaproveitamento de
  cache do provedor.

- **Política de corte explícita quando o orçamento estoura:**
  `tool_output → rag_hits → recentes → resumo`. O `system` **nunca** é cortado; o
  resumo (memória) é o penúltimo a ceder por ser semi-estável e barato.

### Bugs encontrados e corrigidos (quebravam o critério de aceite)

1. **Mensagem recente única e gigante estourava o orçamento.** O corte reduzia a
   janela só até *1* mensagem, mas nunca truncava o **conteúdo** dela. Passamos a
   truncar a última mensagem restante como último recurso da janela, antes de
   tocar no resumo.
2. **Overhead dos rótulos de bloco não era contado.** Os cabeçalhos injetados em
   `_build_blocks` (`[Memória da conversa…]`, `[Trechos relevantes…]`, `[Saída de
   ferramenta]`) somavam ~13 tokens não previstos, deixando o total ultrapassar a
   cota. Agora o custo do rótulo entra na contagem do respectivo bloco.

### Critério de aceite

- ✅ Nenhum turno excede `context_window − reserva` (teste
  `test_assemble_never_exceeds_budget`, inclusive com uma única mensagem que,
  sozinha, estoura a janela).
- ✅ Log estruturado por turno com a quebra de tokens por bloco — insumo direto
  da observabilidade (#37). `llm.py` repassa o modelo do turno para que a janela
  e o log saiam corretos.

---

## #32 — Contrato de contexto para ferramentas (tool-output budgeting)

**Onde:** `api/app/tools/contract.py` (`ToolResult`, `Tool`, `fit_to_budget`,
`collect_tool_block`); cota em `Settings.tool_output_max_tokens` (default 2000).

### Decisão central

Toda ferramenta segue o protocolo **artefato completo fora do prompt + resumo
curto dentro dele**:

```
tool.run() ──► artefato completo ──► S3 / pgvector / DB   (recuperável)
          └─► summary_for_context ──► Context Assembler   (cota da tool)
```

A interface comum é o `ToolResult(summary_for_context, artifact_ref, tokens,
truncated)`. **Só `summary_for_context` entra no contexto**, sempre dentro da
cota. Isso é a fundação das issues de ferramenta (#33 extração, #34 RAG, #35
busca, plotação): nenhuma delas injeta conteúdo cru no prompt.

### Decisões de detalhe

- **Truncagem determinística (sem LLM) como base, sumarização semântica como
  upgrade opcional.** `fit_to_budget` corta para a cota e anexa um aviso
  apontando para o `artifact_ref` — barato, testável e sem dependência de rede.
  Quando valer a pena, uma sumarização semântica pode ser plugada por cima
  reusando o `build_summarizer` do Context Assembler. **Alternativa descartada:**
  sumarizar sempre via LLM — caro e não-determinístico para o caso comum.

- **O aviso de truncagem aponta para o artefato.** Deixa explícito ao modelo que
  há conteúdo completo recuperável (`[…saída truncada…; conteúdo completo em
  <ref>]`), em vez de o modelo "achar" que aquilo é tudo. A truncagem reserva
  espaço para o próprio aviso, de modo que o resultado nunca excede a cota.

- **`collect_tool_block` prioriza por ordem quando há várias tools no turno.**
  Concatena resumos até esgotar a cota total; ferramentas anteriores têm
  prioridade. Uma salvaguarda final clampa o bloco contra o arredondamento de
  chars/token na concatenação, garantindo o teto duro.

- **"Spill para RAG" fica como gancho documentado, não implementado aqui.** O
  conteúdo cru grande deve ser indexado (#34) e reentrar por recuperação
  seletiva. Como o RAG ainda não existe, #32 entrega o contrato e a referência ao
  artefato; a indexação seletiva chega com #34.

- **Lógica pura, sem I/O.** O módulo não persiste nada nem chama rede — apenas
  encaixa texto numa cota. A persistência do artefato é responsabilidade de cada
  ferramenta concreta. Isso mantém o contrato testável de forma determinística.

### Critério de aceite

- ✅ Saída grande (equivalente a um PDF de 80 páginas) **não** entra inteira no
  prompt — é truncada dentro da cota com referência ao artefato (teste
  `test_large_output_is_truncated_within_quota`).
- ✅ Toda saída respeita a cota de tokens, inclusive com múltiplas ferramentas no
  mesmo turno (`test_collect_tool_block_respects_priority_and_total_quota`).
- ✅ Cada `ToolResult` reporta `tokens` — insumo da observabilidade (#37).

---

## Pendências do épico

- **#37 — observabilidade:** os logs por turno (#30) e o campo `tokens` do
  `ToolResult` (#32) já são os insumos; falta agregação/dashboard.
- **#33–#35 — ferramentas:** extração (PDF/imagem), RAG (pgvector) e busca web.
  Cada uma adota o `ToolResult` e negocia sua cota com o Context Assembler.
