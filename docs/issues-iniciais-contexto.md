# Issues iniciais — Gestão da janela de contexto no fluxo do chat

> **Por que este documento existe (e não issues no GitHub):** não foi possível
> autenticar o `gh` nesta sessão, então não consegui ler as issues já existentes
> para replicar o padrão de escrita do **Jailson**. Conforme combinado, redijo a
> entrega aqui em markdown. Quando o `gh auth login -s project,repo` estiver
> feito, converto este conteúdo em issues no
> [Project 5](https://github.com/users/gutoportelaa/projects/5/views/1) **já no
> padrão do Jailson** (ajustar título/labels/seções ao estilo dele antes de criar).

---

## Tese da entrega

Hoje o chat envia **todo o histórico a cada turno** — tanto no caminho ADK/Gemini
(`adk_runtime.py` carrega todos os eventos da sessão) quanto no OpenAI-compat
(`llm.py` monta `history` com todas as `Message`). Não há truncamento,
sumarização nem orçamento de tokens.

Isso ainda funciona porque o chat é só texto. Mas as features pedidas
(**extração** de PDF/imagem, **busca** na web, **plotação** de diagramas) injetam
volumes grandes de conteúdo no prompt. Um PDF de 80 páginas extraído cru, ou 10
resultados de busca, estouram a janela e o custo em poucos turnos.

> **Decisão de arquitetura:** a janela de contexto é o recurso escasso central.
> Antes de plugar ferramentas, estabelecemos **uma camada de montagem de contexto
> com orçamento de tokens**, e cada ferramenta declara seu **"contrato de
> contexto"** — quanto ela tem direito de ocupar e o que vai para storage/RAG em
> vez do prompt.

```
                 ┌──────────────────────────────────────────────┐
  turno do user  │  Context Assembler (orçamento de tokens)      │
  ────────────►  │  systemprompt → memória/resumo → RAG hits →   │ ──► LLM
                 │  últimas N msgs → saída de ferramenta (resumida)│
                 └──────────────────────────────────────────────┘
                        ▲ histórico (janela + sumarização)
                        ▲ extração → S3 + pgvector (não entra cru)
                        ▲ busca web → snippets rankeados + citações
                        ▲ plotação → Mermaid (texto determinístico)
```

As issues abaixo são a **fundação** (1–3 e 8) mais as **três famílias de serviço**
que o usuário citou — extração (4–5), busca (6) e plotação (7) — cada uma escrita
em função de como respeita o orçamento de contexto.

### Padrão de issue usado aqui (provisório)

Cada issue tem: **Contexto · Objetivo · Tarefas (checklist) · Contrato de
contexto · Critérios de aceite · Infra AWS · Referências**. Substituir pelo
template do Jailson assim que as issues existentes forem legíveis.

---

## #1 — Camada de montagem de contexto + orçamento de tokens (fundação)

**Contexto.** O prompt é montado ad-hoc em dois lugares diferentes
(`llm.py` e `adk_runtime.py`), sempre com histórico completo. Não existe um ponto
único que decida o que entra no contexto nem que conte tokens.

**Objetivo.** Criar um módulo único `context.py` (Context Assembler) que monta o
prompt final dentro de um **orçamento de tokens** configurável por modelo,
ordenando os blocos do mais estável (front, cache-friendly) ao mais dinâmico.

**Tarefas.**
- [ ] `ContextBudget` com limite por modelo (ex.: Gemini 2.5 Flash, Llama 3.1) e
      margem reservada para a resposta.
- [ ] Contagem de tokens por bloco (tokenizer do provedor; fallback por heurística
      de caracteres/4).
- [ ] Ordem fixa: `system prompt → resumo/memória → hits de RAG → últimas N
      mensagens → saída de ferramenta` (estável na frente p/ prefix caching).
- [ ] Pontos de corte explícitos quando o orçamento estoura (qual bloco cede
      primeiro).
- [ ] Unificar os dois caminhos (ADK e OpenAI-compat) para passarem por aqui.

**Contrato de contexto.** Este é o "dono" do orçamento; as demais issues negociam
cotas com ele.

**Critérios de aceite.**
- Nenhum turno excede `context_window − reserva_resposta`.
- Log por turno com tokens de cada bloco (alimenta a #8).

**Infra AWS.** Nenhuma nova; é código. Habilita o uso de **prefix/context caching**
do provedor ao manter o prefixo estável.

**Referências.**
- [Context Window Optimization Strategies — DataHub](https://datahub.com/blog/context-window-optimization/)
- [Context Window Management Strategies — APXML](https://apxml.com/courses/langchain-production-llm/chapter-3-advanced-memory-management/context-window-management)
- [Strategies for Managing Context Window Size — Medium](https://mohdmus99.medium.com/strategies-and-techniques-for-managing-the-size-of-the-context-window-when-using-llm-large-3c2dbc5dcc3a)

---

## #2 — Estratégia de histórico: janela deslizante + sumarização (compaction)

**Contexto.** Histórico cresce sem limite. Precisamos preservar continuidade sem
mandar tudo.

**Objetivo.** Implementar o híbrido **buffer recente verbatim + resumo do
passado**: manter as últimas N mensagens íntegras e condensar as antigas num
resumo contínuo que é reescrito quando um limiar de eventos/tokens é atingido.

**Tarefas.**
- [ ] Janela deslizante das últimas N mensagens (config).
- [ ] Sumarização incremental das mensagens que saem da janela (LLM barato),
      persistida como evento de resumo na sessão.
- [ ] No ADK, avaliar o **Context Compaction** nativo (sliding window +
      summary event) antes de reimplementar.
- [ ] Recompactar quando o resumo em si ficar grande (resumo-de-resumo).

**Contrato de contexto.** Histórico ocupa, no máximo, `buffer_recente +
resumo` ≤ cota definida na #1.

**Critérios de aceite.**
- Conversa de 100+ turnos mantém referência ao que foi dito no início via resumo.
- Tokens de histórico estabilizam (não crescem linearmente).

**Infra AWS.** Nenhuma nova (usa Postgres atual p/ persistir resumos).

**Referências.**
- [ADK — Context compaction](https://adk.dev/context/compaction/)
- [ADK Discussion #826 — Context Management (Windowing/Summarization)](https://github.com/google/adk-python/discussions/826)
- [LLM Chat History Summarization — mem0](https://mem0.ai/blog/llm-chat-history-summarization-guide-2025)
- [Context Engineering in Google ADK — Medium](https://medium.com/@juanc.olamendy/context-engineering-in-google-adk-the-ultimate-guide-to-building-scalable-ai-agents-f8d7683f9c60)

---

## #3 — Contrato de contexto para ferramentas (tool-output budgeting)

**Contexto.** Quando adicionarmos tools (extração, busca, plotação), a saída delas
é o maior risco de estouro: texto extraído, resultados de busca, dados de gráfico.

**Objetivo.** Definir um protocolo único: **toda tool retorna (a) um artefato
completo persistido (S3/DB/RAG) e (b) um resumo curto + referência** que é o que
de fato entra no contexto.

**Tarefas.**
- [ ] Interface comum de tool: `{ summary_for_context, artifact_ref, tokens }`.
- [ ] Saídas acima de um limiar de tokens são truncadas/sumarizadas antes de
      entrar no prompt; o conteúdo cru vira artefato recuperável.
- [ ] Política de "spill para RAG": material grande é indexado (#5) e reentra por
      recuperação seletiva, nunca inteiro.

**Contrato de contexto.** Saída de ferramenta ≤ cota da #1; o resto vive fora do
prompt.

**Critérios de aceite.**
- Extrair um PDF de 80 páginas **não** adiciona o texto inteiro ao prompt.
- Cada tool reporta quantos tokens injetou (para a #8).

**Infra AWS.** Depende de **S3** (#4) e **pgvector** (#5).

**Referências.**
- [Context Window Management — oneuptime](https://oneuptime.com/blog/post/2026-01-30-context-window-management/view)
- [Architecting efficient context-aware multi-agent framework — Google Developers Blog](https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/)

---

## #4 — Extração de material (PDF/imagem) → texto, fora do contexto cru

**Contexto.** Primeiro passo das features pedagógicas: receber PDF/imagem e
extrair texto. Sem isso não há resumo, questão nem card.

**Objetivo.** Endpoint de upload → **S3** → extração de texto, alimentando o
pipeline de RAG (#5) e respeitando o contrato da #3.

**Tarefas.**
- [ ] `POST /materials` (upload) + modelo `Material` (owner, S3 key, status).
- [ ] PDF nativo: **PyMuPDF** (rápido, texto direto). ⚠️ atenção à licença
      **AGPL** para uso SaaS.
- [ ] PDF escaneado / imagem: OCR — **dev/teste: Tesseract** (local, grátis);
      **entrega final: AWS Textract** (melhor acurácia, `boto3`, custo baixo por
      uso). Abstrair atrás de uma interface `OcrEngine` para trocar sem mexer no
      resto.
- [ ] Texto extraído **não** volta cru ao chat: vai para chunking/embeddings (#5).

**Contrato de contexto.** A extração nunca empurra o documento inteiro ao prompt;
entrega `artifact_ref` + metadados (#3).

**Critérios de aceite.**
- PDF nativo e PDF escaneado produzem texto correto pelos dois engines.
- Troca Tesseract↔Textract por configuração, sem alterar chamadas.

**Infra AWS.**
- **S3** (materiais) — obrigatório.
- **Textract** (OCR de produção) — entrega final; Tesseract no container para dev.
- OCR é ~1000× mais lento que extração nativa → roteia para job assíncrono.

**Referências.**
- [EasyOCR vs Tesseract vs Amazon Textract — Pochetti](https://francescopochetti.com/easyocr-vs-tesseract-vs-amazon-textract-an-ocr-engine-comparison/)
- [PyMuPDF — OCR recipes](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)
- [Extract text from PDF with PyMuPDF (scanned, tables, OCR) — Nutrient](https://www.nutrient.io/blog/extract-text-from-pdf-pymupdf/)

---

## #5 — RAG + embeddings + pgvector: recuperação seletiva no lugar de stuffing

**Contexto.** É o mecanismo que permite "conversar com o material" sem colar o
material inteiro no contexto.

**Objetivo.** Chunking + embeddings do texto extraído, armazenados em **pgvector**
no Postgres atual; recuperação dos top-k trechos relevantes por turno, entrando
como bloco "hits de RAG" da #1.

**Tarefas.**
- [ ] Extensão `pgvector` + tabela de chunks (material_id, texto, embedding).
- [ ] Estratégia de chunking (tamanho/overlap) e modelo de embeddings
      (Gemini embeddings; alternativa **Bedrock Titan** na entrega AWS).
- [ ] Tool `retrieve_material(query, k)` retornando trechos + fonte.
- [ ] Integração com a #1: hits de RAG ocupam cota própria do orçamento.

**Contrato de contexto.** Só os top-k trechos (cota fixa) entram no prompt — nunca
o documento inteiro.

**Critérios de aceite.**
- Pergunta sobre o material é respondida citando o trecho-fonte.
- Tokens injetados por recuperação são limitados por k e por cota.

**Infra AWS.**
- **pgvector** no Postgres/RDS (evita custo de OpenSearch).
- **Bedrock (Titan Embeddings)** como opção de embeddings gerenciado.

**Referências.**
- [Context Window Optimization (RAG/compression) — DataHub](https://datahub.com/blog/context-window-optimization/)
- [ADK — Sessions, State e Memory](https://google.github.io/adk-docs/sessions/)

---

## #6 — Ferramenta de busca web (Tavily) com citações

**Contexto.** "Pesquisar na internet / referências" sem busca real = referências
alucinadas. Precisamos de grounding com fontes verificáveis.

**Objetivo.** Tool `web_search(query)` via **Tavily** (API feita para LLMs),
retornando snippets rankeados + citações que entram resumidos no contexto.

**Tarefas.**
- [ ] Integração Tavily (chave em **Secrets Manager** na entrega; `.env` no dev).
- [ ] Tool retorna `summary_for_context` (snippets rankeados) + lista de fontes
      (URL/título) — padrão da #3.
- [ ] Citações renderizadas na resposta do chat.
- [ ] (Opcional) busca acadêmica — Semantic Scholar/Crossref — como tool irmã.

**Contrato de contexto.** Apenas snippets resumidos e top-n fontes no prompt; raw
content fica fora.

**Critérios de aceite.**
- Resposta com pesquisa traz fontes clicáveis e reais.
- Saída da busca respeita a cota de tokens da #3.

**Infra AWS.** **Secrets Manager** para a API key. Sem novo serviço de compute.

**Referências.**
- [Tavily 101 — AI-powered Search for Developers](https://www.tavily.com/blog/tavily-101-ai-powered-search-for-developers)
- [Best Web Search APIs for AI Applications 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-web-search-apis)
- [CiteAudit — verifying scientific references (arXiv)](https://arxiv.org/pdf/2602.23452)

---

## #7 — Plotação: diagramas/mapas mentais via Mermaid/Markmap (texto, não imagem)

**Contexto.** "Diagramas e mapas mentais" pedem **geração de texto Mermaid/Markmap
renderizado no frontend**, não geração de imagem. Texto é determinístico,
cacheável, versionável e barato em contexto.

**Objetivo.** Tool `gen_diagram(tipo, conteúdo)` que produz Mermaid válido
(fluxograma, mindmap, sequência) + componente de render no React.

**Tarefas.**
- [ ] Tool retornando bloco Mermaid; validação de sintaxe antes de devolver.
- [ ] Render no frontend (mermaid.js) com fallback de código se falhar.
- [ ] Mindmap a partir de outline hierárquico do material (usa RAG #5).
- [ ] Cache por entrada (mesma entrada → mesmo diagrama).

**Contrato de contexto.** A definição Mermaid (texto curto) é o artefato; dados
volumosos para gerá-la vêm do RAG, não do histórico.

**Critérios de aceite.**
- Diagrama gerado renderiza no chat; mesma entrada gera saída idêntica (cacheável).

**Infra AWS.** Nenhuma nova (render client-side). Artefato pode ser salvo em **S3**
para export.

**Referências.**
- [3 Easy Ways to Create Flowcharts & Diagrams Using LLMs — KDnuggets](https://www.kdnuggets.com/3-easy-ways-create-flowcharts-diagrams-using-llms)
- [LLM + Mermaid — Mike Vincent (Medium)](https://mike-vincent.medium.com/llm-mermaid-how-modern-teams-create-uml-diagrams-without-lucidchart-e54c56350804)
- [Mermaid — Mindmap syntax](https://mermaid.ai/open-source/syntax/mindmap.html)

---

## #8 — Observabilidade de tokens/custo por turno (medir antes de otimizar)

**Contexto.** Não dá para gerir a janela de contexto sem medir. Toda a fundação
(1–3) depende de enxergar quantos tokens cada bloco consome.

**Objetivo.** Instrumentar cada turno: tokens por bloco (system, resumo, RAG,
histórico, tool), total de entrada/saída, latência e custo estimado por usuário.

**Tarefas.**
- [ ] Log estruturado por turno com a quebra de tokens da #1.
- [ ] Métrica de custo por usuário/sessão (base p/ rate limiting futuro).
- [ ] Dashboard mínimo (logs ou Grafana) para acompanhar crescimento de contexto.

**Critérios de aceite.**
- Para qualquer turno, dá para responder "onde foram os tokens?".

**Infra AWS.** **CloudWatch** (logs/métricas) na entrega; logs estruturados no dev.

**Referências.**
- [Understanding the Context Window Limit in LLMs — aiagentmemory](https://aiagentmemory.org/articles/context-window-limit-llm/)
- [Memory Management & Contextual Consistency for Long-Running Agents (arXiv)](https://arxiv.org/pdf/2509.25250)

---

## Ordem sugerida de execução

```
#1 (assembler/orçamento) ──► #2 (histórico) ──► #3 (contrato de tools)
        │                                              │
        └──────────────► #8 (observabilidade) ◄────────┘
                                  │
   #4 (extração+S3) ─► #5 (RAG/pgvector) ─► #6 (busca)  #7 (plotação)
```

A fundação (1, 2, 3, 8) entra primeiro; as três famílias de serviço (extração+RAG,
busca, plotação) plugam no orçamento já estabelecido.

## Resumo de infra AWS por fase

| Fase | Dev/teste (agora) | Entrega final (AWS) |
|---|---|---|
| Extração/OCR | Tesseract no container | **Textract** + **S3** |
| RAG/embeddings | pgvector local + Gemini embeddings | **pgvector (RDS)** ou **Bedrock Titan** |
| Busca web | Tavily key no `.env` | Tavily + **Secrets Manager** |
| Plotação | Mermaid render client-side | idem (+ **S3** p/ export) |
| Jobs pesados (OCR/geração) | BackgroundTasks | **SQS + worker** |
| Observabilidade | logs estruturados | **CloudWatch** |
