# Handoff — Entrega Final (App de Resumo de PDFs sobre o ThinkAI)

> Documento de passagem para a **próxima sessão**. Consolida o estado atual do
> repositório, o gap entre o que existe e o que a entrega final exige
> (`docs/entrega-final.pdf`), e o backlog de issues a implementar.
>
> **Estratégia decidida:** *estender o ThinkAI* — adicionar os módulos de
> upload/resumo de PDF ao app existente, reaproveitando autenticação, camada
> multi-provider de LLM, Postgres, React e Docker. O chat continua como feature.

---

## 1. Estado atual do repositório

### Branches relevantes
- `main` (998e0df) — **defasada**: não contém a linha multi-provider/Ollama
  (`api/app/llm.py`). Seguiu por outra linha (PRs #26–#29).
- `dev` — **branch de integração** (base `cde95c0`). Contém:
  - Tema customizável (frontend) — `feat/theme-customization`.
  - Gestão de histórico híbrida (issue #31) — `31-backend-...`.
- `feat/adk-ollama-litellm` — caminho ADK rodando sobre Ollama via LiteLLM
  (sem chave Gemini). **Ainda não mesclada na `dev`.**

> ⚠️ A linha que tem `llm.py`/Ollama **não está em `main`**. Toda nova issue
> backend deve sair de `dev` (ou de `cde95c0`), nunca de `main`.

### O que já existe (reutilizável para a entrega)
| Requisito da entrega | Já existe no ThinkAI |
|---|---|
| Backend FastAPI + Postgres + Alembic | ✅ `api/app/` |
| Autenticação JWT (register/login) | ✅ `api/app/auth.py`, `routers/auth.py` (parcial — faltam campos) |
| Integração LLM (RF-TEC-001) | ✅ multi-provider: Gemini/Groq/OpenRouter/Ollama (`llm.py`, `agent.py`) |
| Tratamento de erros LLM, streaming SSE | ✅ |
| Frontend React + Vite | ✅ `web/` |
| Docker / docker-compose | ✅ `docker-compose.yml`, Dockerfiles |
| Persistência de dados (RF-TEC-002, parcial) | ✅ users/sessions/messages |

### Ambiente de teste local
- Postgres: `docker compose up -d db` (porta **5433**, ver `api/.env`).
- Ollama local com `llama3.2:3b` (`http://localhost:11434`).
- Testes: `cd api && .venv/bin/python -m pytest`.
- Migrations: `cd api && .venv/bin/alembic upgrade head`.
- Deploy AWS: **sem instância de pé atualmente** (apenas para demonstrações).

---

## 2. Gap analysis (entrega-final.pdf × estado atual)

| ID | Requisito | Status | Observação |
|---|---|---|---|
| RF-001 | Registro/login com nome completo, username, **email**, senha; opcionais: **imagem de perfil**, **descrição**; created_at | 🟡 Parcial | Hoje só username+senha. Faltam campos + edição de perfil. |
| RF-002 | Upload PDF ≤ 50 MB, validação `.pdf`, storage seguro por usuário | 🔴 Falta | Novo módulo. |
| RF-003 | Listagem + seleção individual/múltipla de arquivos | 🔴 Falta | Backend + frontend. |
| RF-004 | Resumo de arquivo único via LLM + armazenamento | 🔴 Falta | Reusa camada LLM existente. |
| RF-005 | Resumo consolidado de múltiplos arquivos + armazenamento | 🔴 Falta | Reusa camada LLM. |
| RF-006 | Dashboard pós-login: menu, edição de perfil, acesso a upload/listagem, ver docs e resumos | 🔴 Falta | Frontend principal. |
| RF-TEC-001 | Integração com LLM | ✅ Pronto | — |
| RF-TEC-002 | Persistência de usuários, metadados, PDFs e resumos | 🟡 Parcial | Faltam tabelas de arquivos/resumos e storage de binários. |
| INF-001 | VPC dedicada (subnets, rotas) | 🔴 Falta | IaC ou passo a passo. |
| INF-002 | Security groups (80/443, SSH restrito) | 🔴 Falta | — |
| INF-003 | EC2 com acesso público | 🔴 Falta | — |
| Entreg. | README de deploy, apresentação | 🟡 Parcial | README existe; falta seção de deploy AWS. |

**Métrica de sucesso:** geração de resumo < 30 s (atenção ao tamanho do PDF e ao
modelo; Ollama local pode ser lento — considerar Groq/Gemini para a métrica).

---

## 3. Backlog de issues (organizado por módulo do PDF)

> Granularidade pensada para implementação incremental, cada uma com critério de
> aceitação verificável. Dependências indicadas.

### EPIC A — Domínio de arquivos e resumos (fundação)
- **A1 · RF-TEC-002: Modelo de dados de arquivos e resumos**
  Tabelas `documents` (id, user_id, filename, size, content_type, storage_path,
  page_count, created_at) e `summaries` (id, user_id, kind=single|consolidated,
  llm_model, content, created_at) + N:N `summary_documents`. Migration Alembic.
  *Aceite:* migrations sobem; modelos com FK/cascade; testes de schema.

### EPIC B — Autenticação e perfil (RF-001, RF-006 parcial)
- **B1 · RF-001: Estender usuário** (nome completo, email único, descrição,
  imagem de perfil, created_at) + ajustes de register/login e hashing.
  *Aceite:* registro com novos campos; email validado/único; migration.
- **B2 · RF-006: Edição de perfil** (endpoint PATCH /me + upload de avatar).
  *Aceite:* usuário edita nome/descrição/imagem; persiste.

### EPIC C — Upload e gestão de arquivos (RF-002, RF-003)
- **C1 · RF-002: Upload de PDF** (≤ 50 MB, validação `.pdf` + *magic bytes* `%PDF`).
  **Decisão de arquitetura: S3 + presigned URLs** — o frontend pede uma URL
  assinada e sobe o PDF **direto no S3** (a EC2 nunca segura o binário); a API só
  persiste `s3_key`/metadados em `documents`. Acesso ao bucket via **IAM Role**
  da EC2 (sem access key em disco). Em dev: fallback para filesystem local.
  *Aceite:* upload válido persiste metadados + objeto no S3; rejeita > 50 MB e
  não-PDF; isolamento por usuário; presigned URL expira.
- **C2 · RF-003: Listagem e seleção** (GET /documents do usuário; frontend com
  seleção individual e múltipla). *Aceite:* lista só os do usuário; multiseleção.

### EPIC D — Resumo via LLM (RF-004, RF-005)
> **Decisão de arquitetura: processamento assíncrono.** PDFs grandes estouram o
> timeout HTTP. Introduzir tabela `jobs` (status pending/running/done/error) e
> processar fora do request — Baseline: `BackgroundTasks` + **SSE** (já existe!)
> para progresso; evolução: SQS + worker. Provedor de nuvem (**Groq** primário)
> para cumprir a métrica < 30 s; Ollama só em dev.
- **D1 · Extração de texto de PDF** (lib p.ex. `pypdf`; tratar PDFs grandes;
  chunking). *Aceite:* extrai texto de PDF de teste; trata erro de PDF inválido.
- **D2 · RF-004: Resumo de arquivo único** (job assíncrono; reusa camada LLM;
  persiste em `summaries`; progresso via SSE).
  *Aceite:* gera e armazena resumo; < 30 s com provedor de nuvem; não bloqueia a API.
- **D3 · RF-005: Resumo consolidado** (map-reduce sobre múltiplos PDFs: resumo
  parcial por doc → síntese final; reusa chunking/sumarização da issue #31).
  *Aceite:* resumo consolidado coerente de ≥ 2 arquivos; armazenado.

### EPIC E — Dashboard (RF-006)
- **E1 · Dashboard principal** (menu de navegação, acesso rápido a upload/listagem,
  visualização de documentos e resumos). *Aceite:* fluxo completo navegável pós-login.

### EPIC F — Infraestrutura AWS (INF-001/002/003)
> **Reaproveitar** a branch `copilot/fix-deploy-na-ec2` (endurece o probe SSH do
> `cd.yml`) e o pipeline GHCR→EC2 existente, em vez de reescrever.
- **F1 · VPC dedicada** (subnet pública p/ EC2/nginx, subnet privada p/ banco;
  rotas + IGW) — IaC (Terraform) ou runbook manual. *Aceite:* VPC documentada e reprodutível.
- **F2 · Security groups + segredos + HTTPS** (80/443 abertos; **SSH restrito por
  IP**; **segredos em SSM Parameter Store**, não em `.env`; **IAM Role** na EC2
  p/ S3; TLS via Let's Encrypt/Caddy no nginx).
  *Aceite:* regras aplicadas; segredos fora do disco; 443 servindo HTTPS.
- **F3 · EC2 + deploy** (instância `t3.small/medium`; **Elastic IP** p/ endereço
  estável entre stop/start; docker-compose em produção; health check + rollback).
  *Aceite:* app acessível via Internet; README de deploy; deploy reflete `main`.

### EPIC G — Entregáveis e qualidade
- **G1 · README de instalação/deploy** (local + AWS) e doc de arquitetura (opcional).
- **G2 · Roteiro de apresentação** (demo de 20 min, passos de implementação, colaboração).

### Dependências
```
A1 ──► C1 ──► C2 ──► D1 ──► D2 ──► D3 ──► E1
B1 ──► B2 ──────────────────────────────► E1
A1 ──► D2
(F1 ──► F2 ──► F3) independente; G depende de tudo entregue.
```

---

## 4. Pretensões de arquitetura (decididas)
Síntese das decisões que sofisticam o protótipo dentro do custo "EC2 só para demo":
- **Storage:** S3 + presigned URLs + IAM Role (upload do browser direto p/ S3).
- **Resumo:** jobs assíncronos (`jobs` table) com progresso via SSE; Groq como
  provedor primário para a métrica < 30 s; Ollama só em dev.
- **Rede:** VPC com subnet pública (app) + privada (banco); banco em container
  agora, **RDS em subnet privada** documentado como evolução de produção.
- **Segurança:** SSH restrito por IP; segredos em **SSM Parameter Store**; **IAM
  Role** na EC2 (sem access key); HTTPS (Let's Encrypt/Caddy); validação por
  *magic bytes* `%PDF`.
- **CI/CD e custo:** pipeline GHCR→EC2 existente + health check/rollback; Elastic
  IP; opcional EventBridge+Lambda p/ ligar/desligar a instância.

## 4.1. Riscos / pendências
- ⚠️ **Deploy aponta para `main`, mas o código vive em `dev`** (e `main` está
  defasada, sem `llm.py`). **Reconciliar `dev → main`** antes de qualquer deploy.
- **Métrica < 30 s:** depende do provedor e do tamanho do PDF; medir cedo.
- **Branches a integrar:** `feat/adk-ollama-litellm` (PR → dev), `testes` (suíte
  de API), `copilot/fix-deploy-na-ec2` (deploy). Ver MEMORY: estrutura de branches.
- **Custo de S3/RDS:** S3 é barato; RDS cobra ocioso — por isso banco em container
  no protótipo.

---

## 5. Como começar na próxima sessão
1. Partir de `dev` atualizada (`git checkout dev`).
2. Implementar na ordem das EPICs (A → C → D → E em paralelo com B; F e G ao final).
3. Cada issue em sua branch `feat/<id>-<slug>`, PR para `dev`.
4. Validar com Postgres (5433) + Ollama local; usar provedor de nuvem para a métrica de tempo.
