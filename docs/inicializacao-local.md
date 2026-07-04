# Inicialização local — banco, migrations e bring-up

> Runbook atualizado para subir o ambiente de desenvolvimento do zero. A seção
> "Rodando localmente" do `README.md` está desatualizada (cita LangGraph/SQLite e
> não menciona Postgres nem Alembic) — use **este** documento até a issue #50
> (README de instalação) consolidar tudo.

## TL;DR (ambiente já existente)

Se o banco já foi criado antes e você só quer voltar a testar:

```bash
cd api
docker compose -f ../docker-compose.yml up -d db   # Postgres na porta 5433
.venv/bin/alembic upgrade head                      # aplica migrations pendentes
.venv/bin/uvicorn app.main:app --reload --port 8001 # 8000 pode estar ocupada
```

> **Por que `alembic upgrade head` é obrigatório:** o `app/main.py` roda
> `Base.metadata.create_all` no startup, mas isso **só cria tabelas que não
> existem — nunca altera tabelas já criadas**. Toda mudança de schema em tabela
> existente (ex.: as colunas de perfil da B1: `full_name`, `email`,
> `description`, `avatar_url`) **só entra via migration**. Se você adicionou
> campos no modelo e a funcionalidade "não funciona" no banco antigo, quase
> sempre é uma migration não aplicada.

---

## Passo a passo (do zero)

### 0. Pré-requisitos
- [uv](https://docs.astral.sh/uv/) (Python) e [bun](https://bun.sh) (frontend)
- [Docker](https://docs.docker.com/) (para o Postgres)

### 1. Subir o Postgres (Docker)
O `docker-compose.yml` na raiz expõe o Postgres em **`localhost:5433`** (mapeado
do `5432` do container) — atenção, **não é 5432**.

```bash
docker compose up -d db
docker compose ps        # confirme o serviço "db" como healthy
```

Credenciais (do compose): usuário `thinkai`, senha `thinkai`, base `thinkai`.

### 2. Configurar o `.env` da API
```bash
cd api
cp .env.example .env
```
Garanta que a `DATABASE_URL` aponta para a **porta 5433**:
```
DATABASE_URL=postgresql+asyncpg://thinkai:thinkai@localhost:5433/thinkai
GEMINI_API_KEY=sua_chave_aqui     # https://aistudio.google.com/app/apikey
```
> Provedor LLM alternativo p/ dev sem chave: Ollama local
> (`LLM_PROVIDER=ollama`, `OLLAMA_MODEL=llama3.2`).

### 3. Instalar dependências
```bash
uv sync
```

### 4. Aplicar as migrations
```bash
.venv/bin/alembic upgrade head
# conferir:
.venv/bin/alembic current   # deve bater com:
.venv/bin/alembic heads
```
`current` e `heads` precisam apontar para a mesma revisão. Se divergirem, há
migration pendente — rode `upgrade head`.

### 5. Subir a API
```bash
.venv/bin/uvicorn app.main:app --reload --port 8001
```
> **Porta 8000 ocupada?** O erro `[Errno 98] Address already in use` significa
> que outra coisa já escuta nela (em dev pode ser outro projeto). Use outra porta
> (`--port 8001`) ou descubra/encerre o processo:
> `ss -ltnp | grep :8000` → `kill <pid>`.

### 6. Smoke test
```bash
curl http://localhost:8001/health
# {"status":"ok","model":"..."}

# cria um usuário (a senha vira hash; o login devolve um JWT)
curl -X POST http://localhost:8001/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"username":"teste","password":"teste123","full_name":"Fulano","email":"f@ex.com"}'
```

### 7. Frontend (opcional)
```bash
cd ../web
cp .env.example .env     # VITE_API_URL=http://localhost:8001  (ajuste a porta!)
bun install
bun run dev              # http://localhost:5173
```

---

## Estado das migrations (referência)

Cadeia linear, único head:

```
e311d14f419e  cria users/sessions/messages
b2f7a1c9d4e0  cria conversation_summaries           (#31 histórico)
c3a8e1f04b21  cria documents e summaries            (A1 / C1)
78f6acf9771a  b1_user_profile_fields  ← head        (B1 perfil de usuário)
```

> As features de janela de contexto (#30 Context Assembler, #32 contrato de
> ferramentas) **não exigem migration** — são código puro. A última migration de
> schema do épico de contexto foi a `b2f7a1c9d4e0` (#31).

## Criar uma nova migration (quando mexer no schema)
```bash
# 1. altere os modelos em app/models.py
# 2. gere a migration por autogenerate (compara modelos x banco):
.venv/bin/alembic revision --autogenerate -m "descricao curta"
# 3. revise o arquivo gerado em alembic/versions/ antes de aplicar
.venv/bin/alembic upgrade head
```

## Resetar o banco (dev)
Apaga TODOS os dados — só em desenvolvimento:
```bash
docker compose down -v        # remove o volume postgres-data
docker compose up -d db
cd api && .venv/bin/alembic upgrade head
```

---

## Notas para Docker/produção
- O `Dockerfile` **não** roda migrations no startup (o `CMD` só sobe o uvicorn).
  Em deploy (EC2/compose), aplique as migrations explicitamente após o `up`:
  `docker compose exec api alembic upgrade head`.
- Em produção a `DATABASE_URL` aponta para o serviço `db` interno na porta
  **5432** (`...@db:5432/thinkai`), não 5433 — a 5433 é só o mapeamento de host
  para acesso local.
