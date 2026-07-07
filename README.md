# ThinkAI — Chatbot de estudo com RAG de documentos

Aplicação full-stack de chatbot multiusuário voltada a estudo: chat com streaming,
**upload de PDFs**, **RAG** (busca vetorial com citação de página), **busca web**,
**resumos/mapas mentais**, gestão da **janela de contexto** e **observabilidade** de
uso — com deploy em nuvem (AWS) e CI/CD.

| Camada    | Stack                                                              | Gerenciador |
| --------- | ------------------------------------------------------------------ | ----------- |
| `web/`    | React + TypeScript + Vite (SPA state-driven)                       | **bun**     |
| `api/`    | Python 3.12 + FastAPI + SQLAlchemy async + Alembic                 | **uv**      |
| LLM       | Gemini (ADK) · Groq / OpenRouter / **Ollama** (OpenAI-compat)      | —           |
| Embeddings| Ollama (dev) · Gemini / **OpenRouter** (prod)                      | —           |
| Banco     | PostgreSQL 16 + **pgvector**                                       | —           |
| Nuvem     | AWS: VPC + EC2 + S3 (+ CloudFront no front)                        | —           |

---

## 📚 Documentação

Toda a documentação de referência vive em [`docs/`](docs/):

| Documento | Conteúdo |
|---|---|
| [`docs/CONTEXT.md`](docs/CONTEXT.md) | **Evolução completa** do projeto por etapas, decisões técnicas, arquitetura, diferenças em relação ao planejamento, testes e ambientes de teste |
| [`docs/aws-runbook.md`](docs/aws-runbook.md) | Bootstrap da infra AWS (VPC/SG/S3/IAM/EC2), custos e checklist de aceitação |
| [`docs/inicializacao-local.md`](docs/inicializacao-local.md) | Bring-up local (Postgres 5433 + Alembic) |
| [`docs/decisoes-janela-contexto.md`](docs/decisoes-janela-contexto.md) | Relatório técnico do épico de gestão de contexto (#30–#37) |

> **Diagramas como "sinal" (`diagram-spec`):** os blocos ` ```diagram-spec ` neste
> README e no `CONTEXT.md` contêm um JSON descritivo do diagrama. Para gerar a
> **imagem**, envie o JSON a uma LLM geradora de imagem pedindo "renderize este
> diagrama". O diagrama-fonte renderizado fica em [`docs/diagrama_thinkai.png`](docs/diagrama_thinkai.png).

---

## Arquitetura

```diagram-spec
{
  "id": "arquitetura-thinkai",
  "titulo": "Arquitetura ThinkAI (visão de deploy)",
  "tipo": "arquitetura-de-sistema",
  "orientacao": "esquerda-para-direita",
  "nos": [
    {"id": "user", "rotulo": "Usuário (browser)", "grupo": "cliente"},
    {"id": "cf", "rotulo": "CloudFront + S3 (frontend 24/7)", "grupo": "aws-edge"},
    {"id": "web", "rotulo": "React SPA (Vite/bun)", "grupo": "cliente"},
    {"id": "api", "rotulo": "FastAPI (EC2, subnet pública)", "grupo": "aws-vpc-publica"},
    {"id": "db", "rotulo": "PostgreSQL 16 + pgvector", "grupo": "aws-vpc-privada"},
    {"id": "s3", "rotulo": "S3 (PDFs, presigned)", "grupo": "aws"},
    {"id": "llm", "rotulo": "LLM (Gemini/Groq/OpenRouter/Ollama)", "grupo": "externo"},
    {"id": "embed", "rotulo": "Embeddings (OpenRouter/Gemini/Ollama)", "grupo": "externo"},
    {"id": "web_search", "rotulo": "Busca web (Tavily/DuckDuckGo)", "grupo": "externo"}
  ],
  "arestas": [
    {"de": "user", "para": "cf", "rotulo": "HTTPS"},
    {"de": "cf", "para": "web", "rotulo": "serve build"},
    {"de": "web", "para": "api", "rotulo": "REST + SSE"},
    {"de": "api", "para": "db", "rotulo": "SQLAlchemy async"},
    {"de": "api", "para": "s3", "rotulo": "upload/presign"},
    {"de": "api", "para": "llm", "rotulo": "chat streaming"},
    {"de": "api", "para": "embed", "rotulo": "RAG reindex/query"},
    {"de": "api", "para": "web_search", "rotulo": "tool de contexto"}
  ]
}
```

### Fluxo de chat (montagem de contexto por turno)

```diagram-spec
{
  "id": "fluxo-chat-contexto",
  "titulo": "Fluxo de um turno de chat (Context Assembler)",
  "tipo": "fluxograma",
  "orientacao": "vertical",
  "etapas": [
    {"id": "msg", "rotulo": "Usuário envia mensagem (POST /chat, SSE)"},
    {"id": "budget", "rotulo": "Context Assembler abre orçamento de tokens do modelo"},
    {"id": "system", "rotulo": "Bloco system (prompt do agente)"},
    {"id": "summary", "rotulo": "Bloco resumo do histórico (sumarização híbrida)"},
    {"id": "tools", "rotulo": "Ferramentas negociam cota: RAG (top-k por sessão) + busca web"},
    {"id": "recent", "rotulo": "Bloco janela recente (N mensagens verbatim)"},
    {"id": "call", "rotulo": "Chama LLM → streaming de tokens"},
    {"id": "persist", "rotulo": "Persiste Message + sources + TurnMetric (tokens/custo/status)"}
  ],
  "fluxo": ["msg","budget","system","summary","tools","recent","call","persist"]
}
```

### Fluxo RAG (upload → resposta com citação de página)

```diagram-spec
{
  "id": "pipeline-rag",
  "titulo": "Pipeline RAG",
  "tipo": "fluxograma",
  "orientacao": "vertical",
  "etapas": [
    {"id": "upload", "rotulo": "Upload PDF (≤50MB) → S3"},
    {"id": "extract", "rotulo": "Extração PyMuPDF (+ OCR Tesseract/Textract), preserva \\f"},
    {"id": "chunk", "rotulo": "Chunking page-aware (Chunk.page)"},
    {"id": "embed", "rotulo": "Embeddings em batch (32) + retry, proveniência por chunk"},
    {"id": "store", "rotulo": "pgvector (Vector dimensionless)"},
    {"id": "query", "rotulo": "Turno: top-k restrito à sessão (SessionDocument)"},
    {"id": "answer", "rotulo": "Resposta + citação de página"}
  ],
  "fluxo": ["upload","extract","chunk","embed","store","query","answer"]
}
```

### Fluxo agêntico (caminho ADK/Gemini)

```diagram-spec
{
  "id": "fluxo-agentico-adk",
  "titulo": "Fluxo agêntico ADK/Gemini",
  "tipo": "fluxograma",
  "orientacao": "vertical",
  "etapas": [
    {"id": "runner", "rotulo": "Runner (app/runner.py) recebe o turno"},
    {"id": "session", "rotulo": "SessionService carrega estado/eventos da sessão"},
    {"id": "agent", "rotulo": "LlmAgent decide: responder ou chamar tool"},
    {"id": "tool", "rotulo": "Function call → tool (RAG/busca/extração) executa"},
    {"id": "obs", "rotulo": "Observação volta ao agente (loop até resposta final)"},
    {"id": "compact", "rotulo": "Context compaction nativa do ADK (opcional)"},
    {"id": "final", "rotulo": "Evento final → streaming de tokens ao cliente"}
  ],
  "fluxo": ["runner","session","agent","tool","obs","compact","final"]
}
```

---

## Rodando localmente (desenvolvimento)

Pré-requisitos: [uv](https://docs.astral.sh/uv/), [bun](https://bun.sh) e Docker
(para o Postgres + pgvector). Detalhes em [`docs/inicializacao-local.md`](docs/inicializacao-local.md).

### 1. Banco (Postgres + pgvector)
```bash
docker compose up -d db     # sobe pgvector/pgvector:pg16
```

### 2. Backend (`api/`)
```bash
cd api
cp .env.example .env        # ajuste LLM_PROVIDER, chaves, DATABASE_URL
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8001
```

> **Sem chave de API:** use `LLM_PROVIDER=ollama` e `EMBEDDING_PROVIDER=ollama`
> (com o [Ollama](https://ollama.com) rodando `llama3.2:3b`) para desenvolver
> 100% offline. A busca web cai no fallback DuckDuckGo sem `TAVILY_API_KEY`.

### 3. Frontend (`web/`)
```bash
cd web
cp .env.example .env        # VITE_API_URL=http://localhost:8001
bun install
bun run dev                 # http://localhost:5173
```

---

## Rodando com Docker (tudo junto)

```bash
cp .env.example .env        # preencha as chaves do provedor escolhido
docker compose up -d --build
```
- Web: <http://localhost> (porta 80) · API: <http://localhost:8001>

---

## Testes

```bash
cd api && uv run pytest     # ~76 testes (SQLite em memória, sem rede)
```
CI (`.github/workflows/ci.yml`): a cada push/PR roda ruff + pytest (backend) e
`tsc --noEmit` + build (frontend), bloqueando merge em caso de falha. Cobertura de
ambientes de teste (local/rede e AWS) documentada em [`docs/CONTEXT.md`](docs/CONTEXT.md#testes-e-ambientes-de-teste).

---

## Deploy na AWS

Guia completo (VPC, Security Groups, S3/IAM, EC2, CI/CD, CloudFront e checklist de
aceitação da banca) em **[`docs/aws-runbook.md`](docs/aws-runbook.md)**.

Resumo: EC2 pública serve a API (Postgres+pgvector em container), S3 guarda os PDFs
via IAM Role (sem chave no disco), o CD (`.github/workflows/cd.yml`) faz
SSH → `git pull` → `docker compose pull/up` → health check ao promover `dev → main`.
O frontend pode ir para S3+CloudFront (workflow `frontend-deploy.yml`, gateado por
`ENABLE_FRONTEND_DEPLOY=true`).

---

## Como funciona o isolamento por usuário/sessão

Autenticação **JWT**; cada sessão de chat pertence a um usuário e o histórico é
persistido no Postgres por sessão. O RAG é escopado por conversa (`SessionDocument`):
documentos anexados a uma conversa não vazam para outra. Roteiro reproduzível:
```bash
./scripts/demo_sessions.sh
```

---

## API (endpoints principais)

Swagger interativo em `http://localhost:8001/docs`. Grupos de rotas:
`auth` (signup/signin/perfil), `chat` (`/chat` SSE, sessões, contexto),
`documents` (upload, raw, thumbnail, reindex, summary, mindmap),
`summaries` (consolidado), `metrics` (`/metrics/usage`).

---

## Estrutura do projeto

Ver a árvore anotada e a descrição de cada módulo em
[`docs/CONTEXT.md`](docs/CONTEXT.md#estrutura-de-diretórios).
