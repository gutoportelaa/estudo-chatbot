# Contexto do Projeto — ThinkAI

Documento de referência que descreve a evolução, as decisões técnicas e a arquitetura do projeto desde o início.

---

## Origem

O ThinkAI nasceu como um estudo prático de engenharia de software full-stack, com foco em construir uma aplicação real do zero — não um tutorial, mas um produto funcional com infraestrutura real. O objetivo central foi aprender fazendo, cobrindo todas as camadas: backend, frontend, banco de dados, autenticação e deploy em nuvem.

---

## Evolução por etapas

### Etapa 1 — Protótipo inicial (feat/chatbot-prototype)

O primeiro protótipo usava **Ollama** como LLM rodando localmente, sem banco de dados e sem autenticação. Toda a sessão era mantida em memória. Essa versão serviu para validar o fluxo básico: frontend React se comunicando com um backend FastAPI via streaming SSE.

**Decisão:** substituir Ollama pelo **Google Gemini** (API gratuita), eliminando a dependência de hardware local e viabilizando o deploy na nuvem.

### Etapa 2 — Infraestrutura base da API (task-2)

Reestruturação do backend para adotar **PostgreSQL** com **SQLAlchemy async** como banco de dados principal. Introdução do **Alembic** para gerenciamento de migrations.

- Stack definida: FastAPI + SQLAlchemy + asyncpg + Alembic
- Gerenciador de pacotes: **uv** (substituindo pip/poetry)

### Etapa 3 — Modelos de dados (task-3)

Definição dos modelos centrais da aplicação:

| Modelo | Descrição |
|---|---|
| `User` | Usuário com email, senha (bcrypt) e timestamps |
| `Session` | Sessão de chat vinculada a um usuário (UUID) |
| `Message` | Mensagem individual com role (user/assistant) e conteúdo |

Migrations aplicadas via Alembic para criar as tabelas no PostgreSQL.

### Etapa 4 — Autenticação JWT (task-11)

Implementação do módulo de autenticação completo:

- `POST /auth/signup` — cadastro com hash bcrypt da senha
- `POST /auth/signin` — login com retorno de JWT (python-jose)
- Middleware de autenticação protegendo rotas de chat e sessão
- Token com expiração configurável via `SECRET_KEY` no `.env`

**Decisão:** JWT stateless (sem refresh token) para manter simplicidade no estudo, aceitando que tokens não podem ser revogados antes do vencimento.

### Etapa 5 — Containerização com Docker (task-8)

Orquestração dos três serviços via `docker-compose.yml`:

| Container | Imagem | Porta |
|---|---|---|
| `thinkai-db` | postgres:16-alpine | 5432 |
| `thinkai-api` | build local (uv + Python 3.12) | 8000 |
| `thinkai-web` | build local (bun + nginx:alpine) | 80 |

O frontend é buildado com `VITE_API_URL` como build arg, permitindo apontar para qualquer host sem recompilar o código.

### Etapa 6 — Deploy na AWS EC2 (task-9)

Deploy da aplicação em instância EC2 pública (Ubuntu 24.04 LTS, t2.micro — free tier):

- Security Group liberando portas 22, 80 e 8000
- `VITE_API_URL` parametrizada via `.env` (sem editar o `docker-compose.yml`)
- Script `scripts/setup_ec2.sh` para automatizar futuros deploys
- Aplicação acessível em `http://3.14.85.184`

### Etapa 7 — CI/CD com GitHub Actions (task-12)

Pipeline automatizado com dois workflows:

**CI** (`ci.yml`) — roda em todo push e PR para `main`:
- Backend: `uv sync` + `uvx ruff check`
- Frontend: `bun install` + `bunx tsc --noEmit` + `bun run build`

**CD** (`cd.yml`) — roda após CI passar no `main`:
- SSH na EC2 → `git pull` → `docker compose up -d --build` → health check

PRs com erro de lint ou build são bloqueados automaticamente antes do merge.

### Etapa 8 — Multi-provider LLM + Ollama

O caminho de chat foi generalizado para múltiplos provedores via um cliente
**OpenAI-compatível** (`app/llm.py`): **Groq**, **OpenRouter** e **Ollama**
(local), além do caminho **Google ADK/Gemini** (`app/runner.py`,
`app/adk_runtime.py`). O ambiente de teste passou a usar **Ollama**
(`llama3.2:3b`), permitindo desenvolver sem chave de API.

### Etapa 9 — Gestão da janela de contexto (épico)

Fundação para escalar o chat além de "só texto". Ver o relatório técnico em
[`docs/decisoes-janela-contexto.md`](docs/decisoes-janela-contexto.md).

| Issue | Entrega |
|---|---|
| #30 | **Context Assembler** (`app/context.py`): orçamento de tokens por modelo, ordem de blocos estável→dinâmico, política de corte |
| #31 | **Histórico híbrido**: janela deslizante + sumarização incremental (tabela `conversation_summaries`) |
| #32 | **Contrato de ferramentas** (`app/tools/contract.py`): `ToolResult` — artefato fora do prompt + resumo na cota |
| #37 | **Observabilidade** (`app/observability.py`): log estruturado de tokens/custo/latência por turno |

### Etapa 10 — Upload de documentos com storage abstraído (C1, RF-002)

`POST /documents` (multipart) e fluxo *presigned* para S3. Abstração
`StorageBackend` (`app/storage.py`) com backends **local** (dev) e **S3**
(produção, via IAM Role — sem chave no disco). Modelo `Document` guarda só a
referência ao binário.

### Etapa 11 — Extração de texto PDF/imagem (#33)

`app/tools/extraction.py`: **PyMuPDF** para PDF nativo e **OCR** atrás da
interface `OcrEngine` (**Tesseract** local ↔ **AWS Textract**, trocáveis por
config). O texto extraído vira artefato recuperável; ao contexto vai só um
resumo dentro da cota (contrato #32).

### Etapa 12 — RAG com embeddings + pgvector (#34)

`app/tools/rag.py`: o texto extraído é dividido em chunks, vetorizado por
**embeddings** e guardado em **pgvector**. A cada turno, os top-k trechos
relevantes entram no bloco de RAG do Context Assembler, citando a fonte. Imagem
do banco: `pgvector/pgvector:pg16`. Embedders trocáveis por config: **Ollama**
(dev) e **Gemini** `gemini-embedding-001` (produção). Como embeddings de modelos
diferentes são incompatíveis, cada chunk grava a **proveniência**
(`embedding_provider`/`model`); a busca só compara o modelo vigente e
`POST /documents/reindex` re-vetoriza ao trocar de modelo.

### Etapa 13 — Observabilidade + tela de Consumo (#37)

`app/observability.py`: cada turno emite um log estruturado (`turn_metrics`) e é
persistido em `turn_metrics` (tokens por bloco, entrada/saída, latência, custo
estimado por modelo). `GET /metrics/usage` agrega por dia/modelo; o frontend tem
uma tela de **Consumo** (estilo Google AI Studio) e um **badge de compactação**
que mostra a timeline de sumarização do histórico.

### Etapa 14 — Biblioteca de documentos (C2)

Seção **Biblioteca** (grade de capas): a **capa** é o thumbnail da 1ª página
(PyMuPDF), gerado no upload/extract e servido por `GET /documents/{id}/thumbnail`.
Operações: adicionar (dropzone ou clipe do chat), ordenar, excluir e **selecionar
documentos para uma conversa** — o RAG fica restrito a eles (`SessionDocument`).
O clipe (📎) do chat anexa um PDF à conversa atual em andamento.

---

## Arquitetura atual

![Diagrama de arquitetura](docs/diagrama_thinkai.png)

### Stack completa

| Camada | Tecnologia | Decisão |
|---|---|---|
| Frontend | React + TypeScript + Vite | SPA leve, sem framework pesado |
| Gerenciador frontend | **bun** | Instalação e build mais rápidos que npm/yarn |
| Backend | FastAPI + Python 3.12 | Async nativo, tipagem forte, OpenAPI automático |
| Gerenciador backend | **uv** | Resolução de dependências mais rápida que pip |
| LLM (produção) | Google Gemini via **ADK** | API gratuita; ADK = SDK oficial de agentes |
| LLM (multi-provider) | Groq / OpenRouter / **Ollama** | OpenAI-compat; Ollama p/ dev sem chave |
| Janela de contexto | Context Assembler próprio | Orçamento de tokens + histórico + RAG (épico) |
| Banco de dados | PostgreSQL 16 + **pgvector** | Relacional + busca vetorial (RAG) no mesmo banco |
| ORM | SQLAlchemy async + Alembic | Migrations versionadas, queries tipadas |
| Extração de PDF | **PyMuPDF** (nativo) + OCR | Tesseract (local) / AWS Textract (prod) |
| Embeddings | **Ollama** (dev) / **Gemini** (prod) | Trocável por config; proveniência por chunk + reindex |
| Observabilidade | Log `turn_metrics` + tabela + tela Consumo | Tokens/custo/latência por turno; CloudWatch na AWS |
| Armazenamento de arquivos | **S3** (prod) / filesystem (dev) | Abstração `StorageBackend`; IAM Role no S3 |
| Autenticação | JWT (python-jose + bcrypt) | Stateless, sem dependência de sessão no servidor |
| Containerização | Docker + Docker Compose | Ambiente idêntico local e produção |
| Servidor web | nginx:alpine | Serve o build estático do React |
| Nuvem | AWS: VPC + EC2 + S3 (+ Textract/Bedrock) | Free tier / créditos; ver `docs/aws-runbook.md` |
| CI/CD | GitHub Actions | Lint + build + deploy automático |

### Modelos de dados (atual)

| Modelo | Descrição |
|---|---|
| `User` | Usuário (username, hash bcrypt; campos de perfil da B1 em WIP) |
| `Session` / `Message` | Sessão de chat e mensagens (role user/assistant) |
| `ConversationSummary` | Resumo do histórico compactado (auditoria da #31) |
| `Document` | PDF enviado: storage + `extraction_status`/`extracted_key`/`thumbnail_key` |
| `Chunk` | Trecho vetorizado (`embedding` em pgvector) + proveniência do modelo — RAG |
| `SessionDocument` | Documentos escopados a uma conversa (Biblioteca / clipe) |
| `TurnMetric` | Métrica persistida por turno (tokens/custo/latência) — tela de Consumo |
| `Summary` / `SummaryDocument` | Resumo (single/consolidado) e associação N:N com documentos |

### Estrutura de diretórios

```
estudo-chatbot/
├── .github/
│   └── workflows/
│       ├── ci.yml          # Lint (ruff) + type-check + build
│       └── cd.yml          # Deploy automático na EC2
├── api/                    # Backend Python (uv)
│   ├── app/
│   │   ├── main.py         # FastAPI: monta rotas (auth, chat, documents), logging
│   │   ├── auth.py         # JWT: signup, signin, middleware
│   │   ├── models.py       # SQLAlchemy: User, Session, Message, Document, Chunk, Summary...
│   │   ├── config.py       # Settings via pydantic-settings (.env)
│   │   ├── database.py     # Engine async, sessão e base declarativa
│   │   ├── context.py      # Context Assembler: orçamento de tokens + histórico (#30/#31)
│   │   ├── observability.py# Métricas de tokens/custo por turno (#37)
│   │   ├── storage.py      # Abstração de storage: local | S3 (C1)
│   │   ├── llm.py          # Chat OpenAI-compat (Groq/OpenRouter/Ollama) + RAG por turno
│   │   ├── runner.py       # Caminho ADK/Gemini (+ compaction nativa)
│   │   ├── adk_runtime.py  # Integração Google ADK
│   │   ├── routers/        # auth.py, chat.py, documents.py, metrics.py
│   │   └── tools/          # contract.py (#32), extraction.py (#33), rag.py (#34)
│   ├── alembic/            # Migrations do banco de dados
│   ├── tests/              # pytest (contexto, tools, extração, RAG, documents, auth...)
│   ├── pyproject.toml
│   └── Dockerfile          # tesseract-ocr + alembic upgrade no start
├── web/                    # Frontend React (bun)
│   ├── src/
│   │   ├── App.tsx         # view chat | biblioteca; modais de Consumo/Preferências
│   │   ├── api/client.ts   # chat, sessões, documentos, /metrics/usage, thumbnails
│   │   ├── hooks/          # useSessions, useChat, useAuth, useTheme
│   │   ├── components/     # Header, Sidebar, ChatInput, MessageList, BibliotecaView,
│   │   │                   #   DocumentCard, ConsumptionModal, MemoryBadge, ...
│   │   └── styles/         # theme.css (claro/nocturne) + app.css
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── diagrama_thinkai.png
│   ├── aws-runbook.md              # Bootstrap da infra AWS (VPC/SG/S3/IAM/EC2)
│   ├── inicializacao-local.md      # Bring-up local (Postgres 5433 + Alembic)
│   └── decisoes-janela-contexto.md # Relatório técnico do épico de contexto
├── scripts/
│   ├── demo_sessions.sh    # Demonstra isolamento de sessões via API
│   └── setup_ec2.sh        # Automatiza setup de nova instância EC2
├── .env.example
├── docker-compose.yml
├── README.md
└── CONTEXT.md              # Este arquivo
```

---

## Decisões técnicas relevantes

**Por que não usar LangChain diretamente?**
O projeto usa o **Google ADK** (`google-adk`) para integração com Gemini em vez de `langchain-google-genai`. O ADK é a SDK oficial do Google para agentes, com suporte nativo a streaming e ferramentas — mais alinhado com a direção do ecossistema Gemini.

**Por que PostgreSQL e não SQLite?**
O protótipo inicial usava `SqliteSaver` do LangGraph. A migração para PostgreSQL foi motivada pelo objetivo de deploy em nuvem: SQLite não é adequado para múltiplas instâncias e não escala horizontalmente. Com PostgreSQL containerizado, o ambiente local e a EC2 são idênticos.

**Por que JWT stateless?**
Para manter o escopo do estudo. Refresh tokens e revogação (blacklist) adicionariam complexidade sem agregar aprendizado diferenciado. O trade-off é aceito explicitamente: tokens expiram, mas não podem ser invalidados antes disso.

**Por que bun e uv?**
Ambos são alternativas modernas e significativamente mais rápidas aos gerenciadores tradicionais (npm e pip). O ganho é visível especialmente no CI/CD, onde instalar dependências é um passo crítico de performance.

**Por que um Context Assembler próprio?**
As ferramentas (extração, RAG, busca) injetam volumes grandes no prompt. Antes de plugá-las, foi criada uma camada única (`app/context.py`) que monta o prompt dentro de um **orçamento de tokens** e garante que nenhum turno estoure a janela do modelo. Cada ferramenta negocia uma cota em vez de injetar conteúdo livremente. Ver `docs/decisoes-janela-contexto.md`.

**Por que pgvector e não um serviço vetorial dedicado?**
Para o RAG (#34), reusar o Postgres existente com a extensão **pgvector** evita custo e infra novos (OpenSearch etc.). A coluna de embedding é *dimensionless* para aceitar qualquer provedor (Ollama no dev; Bedrock Titan/Gemini na entrega) sem migrar o schema.

**Por que abstrair storage e OCR/embeddings atrás de interfaces?**
`StorageBackend` (local↔S3), `OcrEngine` (Tesseract↔Textract) e `Embedder` (Ollama↔Gemini/Bedrock) permitem rodar tudo localmente no dev (grátis, sem AWS) e trocar para os serviços gerenciados na entrega **apenas por configuração**, sem alterar as chamadas.

---

## Pontos de melhoria futura

- Refresh tokens e logout com invalidação
- Rate limiting na API (ex.: `slowapi`) — o custo por turno (#37) já é o insumo
- Embedder **Bedrock Titan** (Gemini já implementado) e índice HNSW no pgvector para escalar o RAG
- Instrumentar o caminho ADK/Gemini com o mesmo `turn_metrics` e dashboard (CloudWatch/Grafana)
- Frontend: dashboard do usuário (#46), resumos individual/consolidado (#44/#45), painel lateral de visualização do documento
- Elastic IP fixo na EC2 para não perder o endereço ao reiniciar
- Unificação das branches divergentes (B1 de perfil) e do débito de migrations
