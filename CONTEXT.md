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
| LLM | Google Gemini 2.0 Flash | API gratuita (1500 req/dia), sem hardware local |
| Banco de dados | PostgreSQL 16 | Relacional, robusto, suporte async via asyncpg |
| ORM | SQLAlchemy async + Alembic | Migrations versionadas, queries tipadas |
| Autenticação | JWT (python-jose + bcrypt) | Stateless, sem dependência de sessão no servidor |
| Containerização | Docker + Docker Compose | Ambiente idêntico local e produção |
| Servidor web | nginx:alpine | Serve o build estático do React |
| Nuvem | AWS EC2 (t2.micro) | Free tier suficiente para o estudo |
| CI/CD | GitHub Actions | Lint + build + deploy automático |

### Estrutura de diretórios

```
estudo-chatbot/
├── .github/
│   └── workflows/
│       ├── ci.yml          # Lint (ruff) + type-check + build
│       └── cd.yml          # Deploy automático na EC2
├── api/                    # Backend Python (uv)
│   ├── app/
│   │   ├── main.py         # FastAPI: rotas de auth, session, chat, health
│   │   ├── auth.py         # JWT: signup, signin, middleware
│   │   ├── models.py       # SQLAlchemy: User, Session, Message
│   │   ├── schemas.py      # Pydantic: request/response DTOs
│   │   ├── graph.py        # LangGraph: grafo de chat com Gemini
│   │   ├── chat.py         # Streaming SSE e leitura de histórico
│   │   ├── config.py       # Settings via pydantic-settings (.env)
│   │   └── database.py     # Engine async, sessão e base declarativa
│   ├── alembic/            # Migrations do banco de dados
│   ├── pyproject.toml
│   └── Dockerfile
├── web/                    # Frontend React (bun)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/client.ts   # createSession / streamChat / fetchHistory
│   │   ├── hooks/          # useSession, useChat, useTheme
│   │   ├── components/     # Header, Greeting, PromptCards, ChatInput, MessageList
│   │   └── styles/         # theme.css (claro/nocturne) + app.css
│   ├── package.json
│   └── Dockerfile
├── docs/
│   └── diagrama_thinkai.png
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

---

## Pontos de melhoria futura

- Refresh tokens e logout com invalidação
- Rate limiting na API (ex.: `slowapi`)
- Testes automatizados (pytest + httpx para backend, Playwright para frontend)
- Elastic IP fixo na EC2 para não perder o endereço ao reiniciar
- Observabilidade: logs estruturados + métricas (ex.: Prometheus + Grafana)
