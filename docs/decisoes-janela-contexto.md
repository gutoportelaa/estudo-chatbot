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
| #37 | Observabilidade de tokens/custo por turno | **Concluída** (branch `feat/token-observability` → `dev`) |

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

## #37 — Observabilidade de tokens e custo por turno

**Onde:** `api/app/observability.py` (`TurnMetrics`, `estimate_cost`,
`log_turn`, `configure_logging`); quebra por bloco vinda do `TokenBreakdown` do
Context Assembler; emissão em `api/app/llm.py`; logging ligado em `app/main.py`.

### Decisões

- **Log estruturado (JSON numa linha) por turno**, prefixado por `turn_metrics`,
  com: `session_id`, `user_id`, `model`, `provider`, quebra por bloco
  (`tokens_system/summary/rag/recent/tool`), `input_tokens`, `output_tokens`,
  `latency_ms` e `cost_usd`. O prefixo facilita filtro/parsing num coletor
  (CloudWatch Logs Insights, Grafana/Loki) sem precisar de schema. **Alternativa
  descartada:** persistir métricas em tabela própria — adia para quando houver
  dashboard; por ora o log estruturado já responde "onde foram os tokens?".

- **Quebra de tokens reaproveitada do Context Assembler.** O `ContextBudget`
  passou a expor um `TokenBreakdown` (valores **pós-corte**); `assemble_messages`
  devolve `(mensagens, quebra)` e o `llm.py` monta o `TurnMetrics`. Evita
  recontar tokens ou reparsear o prompt montado.

- **Custo estimado por tabela de preços por modelo** (`MODEL_PRICING`, USD por 1M
  de tokens, entrada/saída), com match exato/por prefixo e **default zero**
  (modelos locais/desconhecidos não custam). É estimativa — a fonte de verdade de
  faturamento é o provedor; aqui o objetivo é ordem de grandeza e base para
  *rate limiting* futuro.

- **Tokens por heurística (chars/4), não usage do provedor.** Mantém consistência
  com o resto do sistema e funciona igual em qualquer provedor (Ollama não
  devolve `usage` no stream). A captura do `usage` real pode ser plugada depois
  sem mudar o formato do log.

- **`configure_logging` idempotente, com `propagate=False`.** Sem configurar o
  nível, o default (WARNING) engoliria os logs de tokens/turno. Isola os loggers
  `thinkai.*` num handler próprio.

### Escopo

Instrumenta o **caminho OpenAI-compat** (`stream_openai_compatible` —
Groq/OpenRouter/Ollama), que é o que passa pelo Context Assembler e o ambiente
testável (Ollama). O **caminho ADK/Gemini** (`_stream_adk`) não passa por
`assemble_messages` (usa compaction nativa do ADK) e tem `usage` próprio do
provedor — sua instrumentação é um *follow-up* separado, não estimável às cegas.

### Critério de aceite

- ✅ Para qualquer turno, dá para responder "onde foram os tokens?" — validado
  end-to-end com Ollama (`llama3.2:3b`): o log `turn_metrics` saiu com a quebra
  por bloco, totais de entrada/saída, latência e custo.
- ✅ Custo por usuário/sessão disponível no log (`user_id`/`session_id` +
  `cost_usd`) — base para *rate limiting*.
- ⏳ Dashboard/CloudWatch: o log estruturado é o insumo; agregação visual fica
  para a fase AWS (#49/#50).

---

## #33 — Extração de material (PDF/imagem), primeira ferramenta

**Onde:** `api/app/tools/extraction.py` (`extract_pdf`, `OcrEngine`,
`TesseractOcr`/`TextractOcr`, `get_ocr_engine`); endpoint
`POST /documents/{id}/extract` em `app/routers/documents.py`; colunas
`extraction_status`/`extracted_key` em `Document` (migration
`d4f2a1b7c9e3`). Primeira ferramenta a **adotar o contrato da #32**.

### Decisões

- **Reusa o modelo `Document` (C1), não cria um `Material` paralelo.** A issue
  falava em `Material(owner, s3_key, status)`; o `Document` já tem owner +
  `storage_key` + `page_count`. Adicionei só `extraction_status`
  (`pending`/`done`/`failed`) e `extracted_key` — o "status" que a issue pedia.
  **Pré-requisito:** o C1 (upload/storage) foi mergeado em `dev` antes desta
  issue para haver base coerente.

- **PyMuPDF para PDF nativo; OCR só por *fallback* heurístico.** Se o texto
  nativo tem menos que `extraction_ocr_min_chars_per_page` por página, assume-se
  escaneado e renderiza-se cada página para imagem → OCR. Evita rodar OCR
  (~1000× mais lento) quando há texto direto. ⚠️ PyMuPDF é **AGPL** — reavaliar
  `pypdf`/`pdfplumber` se o produto virar SaaS fechado.

- **OCR atrás da interface `OcrEngine`, trocável por config** (`ocr_engine`:
  `tesseract` local ↔ `textract` AWS). Imports tardios: o módulo carrega sem o
  binário/serviço. Atende o critério "trocar Tesseract↔Textract sem alterar as
  chamadas".

- **O texto extraído nunca volta cru ao contexto.** O texto completo é
  persistido como artefato no storage (`extracted_key`, um `.txt` irmão do PDF);
  ao contexto vai só um resumo dentro da cota, via `fit_to_budget` (#32),
  com `artifact_ref = document_id`. Um PDF de 80 páginas entra no prompt como um
  preview truncado, não inteiro. O texto completo fica pronto para o RAG (#34).

- **Extração roda em threadpool.** PyMuPDF/OCR são CPU-bound e bloqueantes;
  `run_in_threadpool` evita travar o event loop. Na entrega, OCR pesado deve ir
  para job assíncrono (SQS + worker).

### Critério de aceite

- ✅ PDF nativo e PDF escaneado produzem texto correto pelos dois engines —
  validado com PDFs gerados em teste, incluindo *round-trip* real de OCR com
  Tesseract 5.3.
- ✅ Troca de engine por configuração, sem mudar as chamadas.
- ✅ PDF grande não entra inteiro no prompt: o resumo respeita
  `tool_output_max_tokens` (teste do PDF de 80 páginas).

---

## Pendências do épico

- **Dashboard de #37:** o log estruturado já existe; falta a agregação visual
  (CloudWatch Logs Insights/Grafana) na fase AWS.
- **Instrumentar o caminho ADK/Gemini** com o mesmo formato `turn_metrics`,
  usando o `usage` nativo do ADK.
- **#34–#35 — ferramentas:** RAG (pgvector, consome o `extracted_key` da #33) e
  busca web. Cada uma adota o `ToolResult` e negocia sua cota.
- **Débito de migrations (unificação B1):** a migration da B1 (`78f6acf9771a`)
  é WIP não-commitado em `feat/c1`, com `down_revision = c3a8e1f04b21` — o mesmo
  pai da migration desta issue (`d4f2a1b7c9e3`). Ao unificar a B1 em `dev` haverá
  dois heads a partir de `c3a8`; reparentar uma das migrations (ou usar um merge
  de alembic) na unificação.
