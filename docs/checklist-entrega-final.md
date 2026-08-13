Este projeto consiste no desenvolvimento de uma aplicação web segura para gerenciamento e análise de documentos PDF, onde usuários devidamente autenticados poderão fazer upload de arquivos de até 50 MB, visualizar seus documentos armazenados e solicitar a geração de resumos individuais ou consolidados de múltiplos arquivos utilizando modelos de LLM. A implementação inclui um sistema completo de autenticação, dashboard personalizado e perfil de usuário, sendo hospedada em infraestrutura AWS com VPC dedicada, instância EC2 e configurações de segurança apropriadas, além de contemplar a documentação técnica e repositório de código versionado para entrega do protótipo funcional.

## Backend: gestão de histórico — janela deslizante + sumarização (compaction) #31
## Descrição
O histórico cresce sem limite — `app/adk_runtime.py` carrega todos os eventos da sessão e `app/llm.py` monta `history` com todas as `Message`. Esta issue implementa a estratégia híbrida **buffer recente verbatim + resumo do passado**: as últimas N mensagens entram íntegras e as antigas são condensadas em um resumo contínuo, reescrito quando um limiar de tokens/eventos é atingido.

No caminho ADK/Gemini, avaliar o **Context Compaction** nativo (janela deslizante + evento de resumo) antes de reimplementar do zero.

## Estratégias
| Estratégia | Uso | Custo |
|---|---|---|
| Janela deslizante (últimas N) | continuidade recente | trivial, perde passado |
| Sumarização incremental | preservar passado | 1 chamada LLM barata por compactação |
| Híbrido (buffer + resumo) | **escolhido** | equilíbrio recência × memória |

## Tarefas
- [ ] Janela deslizante das últimas N mensagens (N configurável)
- [ ] Sumarização incremental das mensagens que saem da janela, persistida como evento de resumo na sessão
- [ ] Recompactação quando o próprio resumo cresce demais (resumo-de-resumo)
- [ ] No caminho ADK, avaliar/adotar o **Context Compaction** nativo do `google-adk`
- [ ] Integrar o resumo ao bloco "memória" do `app/context.py`

## Fluxo
```
mensagens antigas (fora da janela) ── LLM resumidor ──► resumo persistido (evento)
últimas N mensagens ───────────────────────────────────► entram verbatim
                                  │
                       Context Assembler monta: system + resumo + recentes
```

## Critério de aceitação
- Conversa de 100+ turnos mantém referência ao início via resumo.
- Os tokens de histórico estabilizam (não crescem linearmente com o número de turnos).

## Referências
- [ADK — Context compaction](https://adk.dev/context/compaction/)
- [ADK Discussion #826 — Context Management (Windowing/Summarization)](https://github.com/google/adk-python/discussions/826)
- [LLM Chat History Summarization — mem0](https://mem0.ai/blog/llm-chat-history-summarization-guide-2025)


## Backend: camada de montagem de contexto + orçamento de tokens (Context Assembler) #30

## Descrição
Hoje o prompt é montado de forma ad-hoc em dois lugares (`app/llm.py` e `app/adk_runtime.py`), sempre com o **histórico completo** da sessão e **sem contagem de tokens**. Esta issue cria uma camada única — o **Context Assembler** (`app/context.py`) — responsável por montar o prompt final dentro de um **orçamento de tokens** por modelo, ordenando os blocos do mais estável (frente, _cache-friendly_) ao mais dinâmico.

Esta é a fundação para todas as ferramentas seguintes (extração, RAG, busca, plotação): cada uma vai negociar uma cota deste orçamento em vez de injetar conteúdo livremente.

## Ordem dos blocos no contexto
| Posição | Bloco | Estabilidade |
|---|---|---|
| 1 | System prompt | fixo (cacheável) |
| 2 | Resumo / memória da conversa | semi-estável |
| 3 | Hits de RAG | dinâmico |
| 4 | Últimas N mensagens | dinâmico |
| 5 | Saída de ferramenta | mais dinâmico |

## Tarefas
- [ ] Criar `app/context.py` com `ContextBudget` (limite por modelo + margem reservada para a resposta)
- [ ] Contagem de tokens por bloco (tokenizer do provedor; _fallback_ heurístico ~chars/4)
- [ ] Montagem na ordem fixa acima (prefixo estável na frente para _prefix caching_)
- [ ] Política de corte explícita quando o orçamento estoura (qual bloco cede primeiro)
- [ ] Unificar os dois caminhos (`_stream_adk` em `app/routers/chat.py` e `stream_openai_compatible` em `app/llm.py`) para montarem o prompt via `context.py`

## Fluxo
```python
budget = ContextBudget(model="gemini-2.5-flash", reserve_output=1024)
prompt = budget.assemble(
    system=settings.system_prompt,
    summary=session_summary,      # issue de histórico
    rag_hits=retrieved_chunks,    # issue de RAG
    recent=last_n_messages,
    tool_output=tool_summary,     # issue de contrato de tools
)
# garante: tokens(prompt) <= context_window - reserve_output
```

## Critério de aceitação
- Nenhum turno excede `context_window − reserva_resposta`, em qualquer provedor.
- Cada turno emite um log com a quebra de tokens por bloco (insumo da issue de observabilidade).

## Referências
- [Context Window Optimization Strategies — DataHub](https://datahub.com/blog/context-window-optimization/)
- [Context Window Management Strategies — APXML](https://apxml.com/courses/langchain-production-llm/chapter-3-advanced-memory-management/context-window-management)


## Descrição
Mecanismo que permite **conversar com o material sem colar o material inteiro no contexto**. O texto extraído é dividido em _chunks_, vetorizado por **embeddings** e armazenado em **pgvector** no Postgres atual. A cada turno, recuperamos os top-k trechos relevantes, que entram como o bloco "hits de RAG" do Context Assembler.

## Decisão de armazenamento vetorial
| Opção | Custo | Decisão |
|---|---|---|
| **pgvector** no Postgres existente | nenhum serviço novo | **escolhido** |
| OpenSearch / serviço dedicado | mais caro | evitado para o estudo |
| Embeddings (dev) | Gemini embeddings | — |
| Embeddings (entrega AWS) | **Bedrock Titan** | opção gerenciada |

## Tarefas
- [ ] Habilitar extensão `pgvector` + tabela de chunks (`material_id`, `texto`, `embedding`) e migration Alembic
- [ ] Definir estratégia de chunking (tamanho/overlap) e modelo de embeddings
- [ ] Tool `retrieve_material(query, k)` retornando trechos + fonte (padrão `ToolResult`)
- [ ] Integrar os hits ao bloco de RAG do `app/context.py` (cota própria de tokens)

## Fluxo
```
material → chunks → embeddings → pgvector
pergunta → embedding → top-k chunks ──► Context Assembler (bloco RAG, cota fixa)
                              └─► resposta cita o trecho-fonte
```

## Critério de aceitação
- Pergunta sobre o material é respondida citando o trecho-fonte.
- Tokens injetados por recuperação são limitados por `k` e pela cota do orçamento.

## Referências
- [Context Window Optimization (RAG/compression) — DataHub](https://datahub.com/blog/context-window-optimization/)
- [ADK — Sessions, State e Memory](https://google.github.io/adk-docs/sessions/)


## Descrição
"Pesquisar na internet / referências" **sem busca real = referências alucinadas**. Esta issue adiciona a ferramenta `web_search(query)` via **Tavily** (API de busca feita para LLMs), que retorna _snippets_ rankeados + **citações verificáveis**. Apenas o resumo rankeado e as top-n fontes entram no contexto (padrão `ToolResult`); o conteúdo bruto fica fora.

## Tarefas
- [ ] Integração com **Tavily** (chave em **Secrets Manager** na entrega; `.env` no dev)
- [ ] Tool retorna `summary_for_context` (snippets rankeados) + lista de fontes (URL/título)
- [ ] Renderizar as citações na resposta do chat (frontend)
- [ ] (Opcional) tool irmã de busca acadêmica — **Semantic Scholar / Crossref**

## Fluxo
```
web_search("...") ──► Tavily ──► snippets rankeados + fontes
                              └─► summary_for_context (cota da tool) ──► contexto
resposta ──► texto + [1] fonte, [2] fonte (clicáveis)
```

## Critério de aceitação
- Resposta com pesquisa traz fontes reais e clicáveis (sem referências inventadas).
- A saída da busca respeita a cota de tokens do contrato de ferramentas.

## Referências
- [Tavily 101 — AI-powered Search for Developers](https://www.tavily.com/blog/tavily-101-ai-powered-search-for-developers)
- [Best Web Search APIs for AI Applications 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-web-search-apis)
- [CiteAudit — verifying scientific references (arXiv)](https://arxiv.org/pdf/2602.23452)
