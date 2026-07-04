#!/usr/bin/env bash
#
# Cria as issues da Entrega Final (app de resumo de PDFs sobre o ThinkAI) no
# GitHub, espelhando docs/handoff-entrega-final.md.
#
# Uso:
#   bash scripts/create-entrega-issues.sh            # cria de verdade
#   DRY_RUN=1 bash scripts/create-entrega-issues.sh  # só imprime o que faria
#
# Requer: gh autenticado (gh auth status).
set -euo pipefail

REPO="gutoportelaa/estudo-chatbot"
DRY_RUN="${DRY_RUN:-0}"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

ensure_label() {
  local name="$1" color="$2" desc="$3"
  if gh label list --repo "$REPO" --limit 200 | grep -qiE "^${name}\b"; then
    return 0
  fi
  run gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" || true
}

create_issue() {
  local title="$1" labels="$2" body="$3"
  run gh issue create --repo "$REPO" --title "$title" --label "$labels" --body "$body"
}

# ---- Labels ----
ensure_label "entrega-final" "5319e7" "Escopo da entrega final (resumo de PDFs)"
ensure_label "backend"       "1d76db" "API / FastAPI / Postgres"
ensure_label "frontend"      "0e8a16" "Web / React"
ensure_label "infra"         "b60205" "AWS / deploy"
ensure_label "epic"          "fbca04" "Agrupador de tarefas"

# ============================================================================
# EPIC A — Domínio de arquivos e resumos
# ============================================================================
create_issue \
  "[A1][RF-TEC-002] Modelo de dados de arquivos e resumos" \
  "entrega-final,backend" \
"## Contexto
Fundação de persistência para o app de resumo de PDFs (estende o ThinkAI).

## Tarefas
- [ ] Tabela \`documents\` (id, user_id FK, filename, size_bytes, content_type, storage_path, page_count, created_at)
- [ ] Tabela \`summaries\` (id, user_id FK, kind = single|consolidated, llm_model, content, created_at)
- [ ] Associação N:N \`summary_documents\` (summary_id, document_id)
- [ ] Migration Alembic + índices/cascade
- [ ] Modelos SQLAlchemy em \`api/app/models.py\`

## Critério de aceitação
- \`alembic upgrade head\` cria as tabelas; FKs com ON DELETE CASCADE.
- Teste de schema básico passa.

Ref: docs/handoff-entrega-final.md (EPIC A)."

# ============================================================================
# EPIC B — Autenticação e perfil
# ============================================================================
create_issue \
  "[B1][RF-001] Estender modelo de usuário (nome, email, descrição, avatar)" \
  "entrega-final,backend" \
"## Tarefas
- [ ] Campos: nome_completo, email (único, validado), descricao (opcional), profile_image (opcional), created_at
- [ ] Ajustar registro/login (\`routers/auth.py\`, \`auth.py\`) para os novos campos
- [ ] Migration Alembic
- [ ] Validação de email único e formato

## Critério de aceitação
- Registro exige nome completo, username, email e senha; aceita opcionais.
- Email duplicado é rejeitado.

Ref: handoff EPIC B."

create_issue \
  "[B2][RF-006] Edição de perfil do usuário" \
  "entrega-final,backend,frontend" \
"## Tarefas
- [ ] Endpoint \`PATCH /me\` (nome, descrição, imagem de perfil)
- [ ] Upload/armazenamento da imagem de perfil
- [ ] Tela de edição de perfil no frontend

## Critério de aceitação
- Usuário edita e persiste nome/descrição/imagem; mudanças refletidas no dashboard.

Depende de: B1. Ref: handoff EPIC B."

# ============================================================================
# EPIC C — Upload e gestão de arquivos
# ============================================================================
create_issue \
  "[C1][RF-002] Upload de PDF (≤ 50 MB) com armazenamento seguro" \
  "entrega-final,backend" \
"## Tarefas
- [ ] Endpoint de upload (multipart) com validação de extensão \`.pdf\` e MIME
- [ ] Limite de 50 MB por arquivo (rejeição clara acima disso)
- [ ] Armazenamento por usuário (volume/filesystem ou S3 — decidir aqui) com isolamento de acesso
- [ ] Persistir metadados em \`documents\`

## Critério de aceitação
- Upload válido persiste arquivo + metadados.
- Rejeita > 50 MB e não-PDF.
- Usuário só acessa os próprios arquivos.

Depende de: A1. Ref: handoff EPIC C."

create_issue \
  "[C2][RF-003] Listagem e seleção de arquivos" \
  "entrega-final,backend,frontend" \
"## Tarefas
- [ ] \`GET /documents\` (apenas do usuário autenticado)
- [ ] Frontend: lista com seleção individual e múltipla
- [ ] (Opcional) pré-visualização/metadados do arquivo

## Critério de aceitação
- Lista exibe só os documentos do usuário.
- Seleção múltipla habilita o fluxo de resumo consolidado.

Depende de: C1. Ref: handoff EPIC C."

# ============================================================================
# EPIC D — Resumo via LLM
# ============================================================================
create_issue \
  "[D1] Extração de texto de PDF (+ chunking)" \
  "entrega-final,backend" \
"## Tarefas
- [ ] Extração de texto (ex.: pypdf) com contagem de páginas
- [ ] Estratégia de chunking para PDFs grandes
- [ ] Tratamento de PDF inválido/corrompido/sem texto (OCR fora de escopo)

## Critério de aceitação
- Extrai texto de PDF de teste; erros tratados sem derrubar a API.

Depende de: A1. Ref: handoff EPIC D."

create_issue \
  "[D2][RF-004] Resumo de arquivo único via LLM" \
  "entrega-final,backend" \
"## Tarefas
- [ ] Pipeline: extrair texto (D1) → resumir via camada LLM existente (\`llm.py\`/provedores) → persistir em \`summaries\`
- [ ] Tratamento de erros de LLM
- [ ] Endpoint para disparar/recuperar o resumo

## Critério de aceitação
- Gera e armazena resumo de 1 PDF.
- Tempo < 30 s com provedor de nuvem (Groq/Gemini).

Depende de: A1, D1. Ref: handoff EPIC D."

create_issue \
  "[D3][RF-005] Resumo consolidado de múltiplos arquivos" \
  "entrega-final,backend" \
"## Tarefas
- [ ] Seleção de múltiplos PDFs → resumo consolidado (map-reduce: resumo parcial por doc + síntese final)
- [ ] Persistir como \`summaries.kind = consolidated\` ligado aos documentos (N:N)

## Critério de aceitação
- Resumo consolidado coerente de ≥ 2 arquivos; armazenado e recuperável.

Depende de: D2. Ref: handoff EPIC D."

# ============================================================================
# EPIC E — Dashboard
# ============================================================================
create_issue \
  "[E1][RF-006] Dashboard do usuário" \
  "entrega-final,frontend" \
"## Tarefas
- [ ] Layout pós-login com menu de navegação
- [ ] Acesso rápido a upload e listagem de arquivos
- [ ] Visualização de documentos e resumos (individual e consolidado)
- [ ] Atalho para edição de perfil

## Critério de aceitação
- Fluxo completo navegável após login: upload → listar → resumir → ver resumo.

Depende de: B2, C2, D2. Ref: handoff EPIC E."

# ============================================================================
# EPIC F — Infraestrutura AWS
# ============================================================================
create_issue \
  "[F1][INF-001] VPC dedicada (subnets + rotas)" \
  "entrega-final,infra" \
"## Tarefas
- [ ] VPC dedicada com subnets pública e privada
- [ ] Tabelas de rotas (IGW na pública)
- [ ] IaC (Terraform) ou runbook manual reprodutível

## Critério de aceitação
- VPC documentada e reprodutível.

Ref: handoff EPIC F."

create_issue \
  "[F2][INF-002] Security groups" \
  "entrega-final,infra" \
"## Tarefas
- [ ] Regras de entrada/saída restritivas
- [ ] HTTP/HTTPS (80/443) abertos
- [ ] SSH restrito por IP de administração

## Critério de aceitação
- Regras descritas/aplicadas; SSH não aberto ao mundo.

Depende de: F1. Ref: handoff EPIC F."

create_issue \
  "[F3][INF-003] EC2 + deploy público da aplicação" \
  "entrega-final,infra" \
"## Tarefas
- [ ] Instância EC2 adequada à carga
- [ ] docker-compose em produção (api + web + db)
- [ ] Acesso público via Internet
- [ ] Segredos/variáveis de ambiente em produção

## Critério de aceitação
- App acessível via Internet; integração com LLM operacional em produção.

Depende de: F1, F2. Ref: handoff EPIC F."

# ============================================================================
# EPIC G — Entregáveis
# ============================================================================
create_issue \
  "[G1] README de instalação/deploy + doc de arquitetura" \
  "entrega-final" \
"## Tarefas
- [ ] README com passos de instalação local e deploy AWS
- [ ] (Opcional) documentação técnica da arquitetura

## Critério de aceitação
- Terceiro consegue instalar/deployar seguindo o README.

Ref: handoff EPIC G."

create_issue \
  "[G2] Roteiro de apresentação (demo 20 min)" \
  "entrega-final" \
"## Tarefas
- [ ] Roteiro da demo funcional (20 min)
- [ ] Descrição dos passos de implementação
- [ ] Detalhamento da colaboração da equipe
- [ ] Link do repositório

## Critério de aceitação
- Roteiro pronto cobrindo todos os critérios de aceitação do PDF.

Ref: handoff EPIC G."

echo "Concluído."
