# ThinkAI — Chatbot multiusuário (estudo)

Protótipo funcional de um chatbot multiusuário, usando **Google Gemini** como LLM
e **LangGraph** para orquestração com histórico isolado por sessão, com **autenticação** e persistência em banco de dados.

| Camada    | Stack                                                    | Gerenciador |
| --------- | -------------------------------------------------------- | ----------- |
| `web/`    | React + TypeScript + Vite                                | **bun**     |
| `api/`    | Python + FastAPI + LangGraph + `langchain-google-genai`  | **uv**      |
| DB        | PostgreSQL (via asyncpg e SQLAlchemy)                    | —           |
| LLM       | Google Gemini · modelo `gemini-2.0-flash` (API gratuita) | —           |

---

## Arquitetura e Fluxo

```mermaid
sequenceDiagram
    participant B as Browser (React/Vite)
    participant A as FastAPI (api)
    participant DB as Banco de Dados
    participant LLM as Google Gemini API

    B->>A: POST /auth/signup (Cria conta)
    A->>DB: Salva Usuário
    A-->>B: Confirmação

    B->>A: POST /auth/signin (Login)
    A->>DB: Verifica credenciais
    A-->>B: JWT Access Token

    B->>A: POST /sessions (Cria sessão)
    Note over B,A: Header: Authorization: Bearer <token>
    A->>DB: Associa UUID da sessão ao usuário
    A-->>B: session_id (UUID)

    B->>A: POST /chat (SSE) + Token + session_id
    A->>DB: Autentica Token e verifica permissão
    A->>LLM: LangGraph.astream (thread_id = session_id)
    LLM-->>A: tokens em stream
    A-->>B: text/event-stream
```

- **Autenticação:** A API é protegida por tokens JWT.
- **Multiusuário:** o backend é assíncrono; cada requisição carrega seu `session_id` e token.
- **Isolamento:** o checkpointer do LangGraph guarda o histórico por `thread_id` atrelado ao usuário da requisição.

---

## Pré-requisito: chave da API Gemini

Obtenha gratuitamente em <https://aistudio.google.com/app/apikey> (conta Google).
O tier gratuito oferece **1.500 requisições/dia** e **15 req/min** — mais que suficiente.

---

## Rodando localmente (desenvolvimento)

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e [bun](https://bun.sh).

### 1. Backend (`api/`)
```bash
cd api
cp .env.example .env
# edite .env e preencha:
# GEMINI_API_KEY=sua_chave_aqui
# SECRET_KEY=sua_chave_secreta (ex: openssl rand -hex 32)
# DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/thinkai
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (`web/`)
```bash
cd web
cp .env.example .env   # VITE_API_URL=http://localhost:8000
bun install
bun run dev            # http://localhost:5173
```

Abra <http://localhost:5173>, crie uma conta, faça login, envie uma mensagem e veja a resposta em streaming.

---

## Rodando com Docker (tudo junto)

```bash
# Na raiz do projeto:
cp .env.example .env
# edite .env e preencha:
# GEMINI_API_KEY=sua_chave_aqui
# SECRET_KEY=sua_chave_secreta_jwt
# POSTGRES_PASSWORD=senha_segura_do_banco (caso use variáveis separadas)
# DATABASE_URL=... (se for alterar a padrão do Docker)

docker compose up -d --build
```

- Web: <http://localhost> (porta 80)
- API: <http://localhost:8000>
- **Swagger UI** (Documentação interativa): <http://localhost:8000/docs>

---

## Documentação da API

Base URL local: `http://localhost:8000`

> Dica: Todas as rotas também podem ser exploradas via Swagger UI em `http://localhost:8000/docs`.

### Autenticação

#### `POST /auth/signup`
Cria uma nova conta.

```bash
# 1. Criar conta
curl -X POST http://localhost:8000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"username":"ana","password":"senha123"}'
```

#### `POST /auth/signin`
Realiza login e devolve o token JWT.

```bash
# 2. Login e pegar token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/signin \
  -H 'Content-Type: application/json' \
  -d '{"username":"ana","password":"senha123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

#### `GET /auth/profile`
Retorna dados do usuário logado.

```bash
curl -X GET http://localhost:8000/auth/profile \
  -H "Authorization: Bearer $TOKEN"
```

### Sessões

#### `POST /sessions` (ou `/session` dependendo da implementação)
Cria uma nova sessão e devolve um **ID único** (UUID).

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Authorization: Bearer $TOKEN"
# {"session_id":"bb98ab08-883c-41fb-a460-b52cbe41dacc"}
```

#### `GET /sessions`
Lista as sessões ativas do usuário atual.

```bash
curl -X GET http://localhost:8000/sessions \
  -H "Authorization: Bearer $TOKEN"
```

#### `DELETE /sessions/{id}`
Deleta/encerra a sessão com o ID especificado.

```bash
curl -X DELETE http://localhost:8000/sessions/<uuid> \
  -H "Authorization: Bearer $TOKEN"
```

### Chat (SSE) & Histórico

#### `POST /chat`
Envia uma mensagem na sessão, usando **streaming (SSE)** e retorna a resposta pedaço a pedaço. O fim é sinalizado por `data: [DONE]`.

```bash
# 3. Enviar mensagem com token
curl -N -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"session_id":"<uuid>","message":"Olá!"}'
```

#### `GET /history/{session_id}`
Retorna as mensagens salvas daquela sessão específica.

```bash
curl -X GET http://localhost:8000/history/<uuid> \
  -H "Authorization: Bearer $TOKEN"
# Retorna JSON com o array de mensagens
```

---

## Demonstrando o histórico isolado por sessão (com Autenticação)

Com a API rodando, execute o roteiro pronto que cria duas contas, loga e comprova o isolamento:

```bash
./scripts/demo_sessions.sh
# ou apontando para outra URL:
API_URL=http://SEU_IP_PUBLICO:8000 ./scripts/demo_sessions.sh
```

Saída esperada: a conta/sessão **A** aprende e lembra o fato; a conta/sessão **B** não tem acesso.

---

## Deploy na AWS EC2 (público)

Com Gemini, qualquer instância EC2 serve — inclusive o **free tier** (`t2.micro`, 1 GB RAM).

### Passo a passo

1. **Criar a instância**
   - AMI: Ubuntu Server 24.04 LTS · Tipo: **t2.micro** (free tier) ou superior · Disco: 8 GB gp3.
   - Crie/baixe um **key pair** (`.pem`).
   - **Security Group** — libere: `22` (SSH, só seu IP), `80` (HTTP), `8000` (API).

2. **Conectar e instalar Docker**
   ```bash
   ssh -i sua-chave.pem ubuntu@SEU_IP_PUBLICO
   sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
   sudo usermod -aG docker ubuntu && newgrp docker
   ```

3. **Clonar e configurar o ambiente**
   ```bash
   git clone <URL_DO_SEU_REPO> thinkai && cd thinkai

   # Crie o .env:
   cp .env.example .env
   
   # Edite o .env para adicionar suas senhas reais:
   # GEMINI_API_KEY=sua_chave_aqui
   # SECRET_KEY=chave_secreta_jwt_segura_aqui (ex: openssl rand -hex 32)
   # DB_PASSWORD=senha_segura_do_banco (se a variável for usada no seu compose)
   nano .env
   ```

4. **Ajustar IPs e Subir**
   ```bash
   # Aponte o frontend para o IP público da EC2:
   sed -i "s#VITE_API_URL: http://localhost:8000#VITE_API_URL: http://SEU_IP_PUBLICO:8000#" docker-compose.yml

   docker compose up -d --build
   ```

5. **Acessar (endpoint público)**
   - Página: `http://SEU_IP_PUBLICO`
   - API: `http://SEU_IP_PUBLICO:8000` (Swagger: `http://SEU_IP_PUBLICO:8000/docs`)

6. **Economizar:** ao terminar o estudo, **pare** a instância no console (EC2 → Instâncias → *Stop instance*).
