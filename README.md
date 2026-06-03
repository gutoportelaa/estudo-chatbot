# ThinkAI — Chatbot multiusuário (estudo)

Protótipo funcional de uma página de chatbot, usando um
LLM local via **Ollama** orquestrado por **LangGraph**.

| Camada    | Stack                                            | Gerenciador |
| --------- | ------------------------------------------------ | ----------- |
| `web/`    | React + TypeScript + Vite                        | **bun**     |
| `api/`    | Python + FastAPI + LangGraph + `langchain-ollama`| **uv**      |
| LLM       | Ollama · modelo `llama3.2:3b`                     | —           |
| Histórico | LangGraph `SqliteSaver` (`thread_id = session_id`)| —          |

---

## Como funciona (arquitetura)

```
Browser (React/Vite)               FastAPI (api)                 Ollama
  │  session_id (UUID,                 │                            │
  │  guardado em localStorage)         │                            │
  ├── POST /session ──────────────────►│  gera UUID                 │
  │                                    │                            │
  ├── POST /chat (SSE) ───────────────►│  LangGraph.astream ───────►│ llama3.2:3b
  │◄───── tokens (text/event-stream) ──┤  thread_id = session_id    │
  │                                    │                            │
  │                              SqliteSaver (data/sessions.sqlite)
  │                              histórico isolado por sessão
```

- **Multiusuário:** o backend é assíncrono; cada requisição carrega seu `session_id`.
- **Isolamento:** o `SqliteSaver` do LangGraph guarda o histórico por `thread_id`, então cada
  resposta volta apenas para a sessão/usuário correto (verificado: a sessão A lembra o nome
  informado; a sessão B não tem acesso a ele).
- **Persistência:** o histórico sobrevive a reinícios do servidor (fica em `api/data/sessions.sqlite`).

---

## Rodando localmente (desenvolvimento)

Pré-requisitos: [Ollama](https://ollama.com), [uv](https://docs.astral.sh/uv/) e [bun](https://bun.sh).

### 1. Modelo (Ollama)
```bash
ollama pull llama3.2:3b      # ~2 GB
ollama serve                 # se ainda não estiver rodando (porta 11434)
```

### 2. Backend (`api/`)
```bash
cd api
cp .env.example .env         # ajuste se quiser
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 3. Frontend (`web/`)
```bash
cd web
cp .env.example .env         # VITE_API_URL=http://localhost:8000
bun install
bun run dev                  # http://localhost:5173
```

Abra <http://localhost:5173>, envie uma mensagem e veja a resposta em streaming.
Use o botão 🌙/☀️ no topo para alternar entre claro e nocturne.

---

## Rodando com Docker (tudo junto)

```bash
docker compose up -d --build
# Na primeira vez, baixe o modelo dentro do container do Ollama:
docker exec -it thinkai-ollama ollama pull llama3.2:3b
```

- Web: <http://localhost> (porta 80)
- API: <http://localhost:8000>
- Ollama: <http://localhost:11434>

---

## Documentação do endpoint (API)

Base URL local: `http://localhost:8000`

### `GET /health`
Verifica se a API está no ar.
```bash
curl http://localhost:8000/health
# {"status":"ok","model":"llama3.2:3b"}
```

### `POST /session`
Cria uma nova sessão e devolve um **ID único** (UUID). O frontend guarda esse ID em
`localStorage` e o reenvia em cada mensagem.
```bash
curl -X POST http://localhost:8000/session
# {"session_id":"bb98ab08-883c-41fb-a460-b52cbe41dacc"}
```

### `POST /chat`
Envia uma mensagem e recebe a resposta em **streaming (SSE)**. Cada evento é uma linha
`data: <pedaço de texto>`; o fim é sinalizado por `data: [DONE]`. Quebras de linha vêm
escapadas como `\n`.

Corpo (JSON):
```json
{ "session_id": "<uuid>", "message": "Sua pergunta aqui" }
```
Exemplo:
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<uuid>","message":"Explique o que é uma API REST"}'
```

Exemplo no browser (consumindo o stream):
```js
const res = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ session_id, message: "Olá!" }),
});
const reader = res.body.getReader();
const dec = new TextDecoder();
let buf = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buf += dec.decode(value, { stream: true });
  for (const part of buf.split("\n\n")) {
    if (!part.startsWith("data:")) continue;
    const txt = part.slice(5).trim();
    if (txt === "[DONE]") break;
    console.log(txt.replace(/\\n/g, "\n"));
  }
}
```

### `GET /history/{session_id}`
Retorna o histórico persistido de uma sessão.
```bash
curl http://localhost:8000/history/<uuid>
# {"session_id":"...","messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

> Documentação interativa (Swagger) disponível em `http://localhost:8000/docs`.

---

## Demonstrando o histórico isolado por sessão

Cada usuário recebe um `session_id` (UUID) e o histórico é guardado por `thread_id = session_id`
no `SqliteSaver`. Há duas formas práticas de demonstrar o isolamento:

### A) Pelo navegador (multiusuário real)
O `session_id` fica no `localStorage`, então **cada navegador/janela anônima é um usuário diferente**:
1. Abra <http://localhost:5173> no navegador normal e diga: *"Meu nome é Ana"*.
2. Abra a mesma URL numa **janela anônima** (ou outro navegador/dispositivo) e pergunte: *"Qual é o meu nome?"*.
3. A primeira sessão lembra "Ana"; a segunda **não sabe** — históricos isolados.
4. Recarregar a página mantém a conversa (o ID persiste e o histórico vem de `/history`).

> Para simular vários usuários simultâneos a partir de um mesmo navegador, basta usar abas anônimas
> distintas — cada contexto anônimo tem seu próprio `localStorage` e, portanto, seu próprio `session_id`.

### B) Por script (reproduzível, via API)
Com a API rodando, execute o roteiro pronto que cria duas sessões e comprova o isolamento:
```bash
./scripts/demo_sessions.sh
# ou apontando para outra URL:
API_URL=http://SEU_IP_PUBLICO:8000 ./scripts/demo_sessions.sh
```
Saída esperada (resumo): a sessão **A** aprende e lembra o nome/cor; a sessão **B**, com outro
`session_id`, não tem acesso a esses dados, e `GET /history` mostra os históricos separados.

<!-- ---

## Deploy na AWS EC2 (público) + Orçamento de estudante

> Consultas de preço feitas em **junho/2026** (`us-east-1`). Confira os valores atuais antes de subir.

### Resumo do orçamento

O novo **AWS Free Tier (2026)** dá a contas novas **até US$ 200 em créditos**
(US$ 100 no cadastro + US$ 100 ao completar tarefas como lançar uma EC2), válidos por **6 meses**.

Para rodar Ollama em CPU (sem GPU) com `llama3.2:3b` (~3 GB de RAM), o ideal é uma **`t3.large`**
(8 GB / 2 vCPU). Preço on-demand: **US$ 0,0832/h**.

| Uso                                   | Custo aproximado | Cabe nos créditos? |
| ------------------------------------- | ---------------- | ------------------ |
| 24/7 o mês inteiro                    | ~US$ 60/mês      | ~3,3 meses de $200 |
| **~3 h/dia (sessões de estudo)**      | **~US$ 8–12/mês**| Sim, com folga ✅  |
| Instância **parada** (stopped)        | só EBS (~centavos/GB-mês) | —         |

**Estratégia praticamente gratuita (recomendada):**
1. Use a conta nova com os **US$ 200 em créditos**.
2. **Pare (Stop)** a instância quando não estiver estudando — parada você paga apenas o disco EBS.
3. Crie um **AWS Budgets** com alerta em US$ 5/US$ 10 para não ser surpreendido.
4. Alternativa ainda mais barata: `t3.medium` (4 GB) + `llama3.2:1b` (menos RAM, respostas mais rápidas, qualidade um pouco menor). -->

### Passo a passo

1. **Criar a instância**
   - AMI: Ubuntu Server 24.04 LTS · Tipo: **t3.large** · Disco: 20 GB gp3.
   - Region: `us-east-1`. Crie/baixe um **key pair** (`.pem`).
   - **Security Group** — libere: `22` (SSH, só seu IP), `80` (HTTP), `8000` (API). `443` se for usar HTTPS.

2. **Conectar e instalar Docker**
   ```bash
   ssh -i sua-chave.pem ubuntu@SEU_IP_PUBLICO
   sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
   sudo usermod -aG docker ubuntu && newgrp docker
   ```

3. **Clonar e subir**
   ```bash
   git clone <URL_DO_SEU_REPO> thinkai && cd thinkai
   # Aponte o frontend para o IP público da EC2:
   sed -i "s#VITE_API_URL: http://localhost:8000#VITE_API_URL: http://SEU_IP_PUBLICO:8000#" docker-compose.yml
   docker compose up -d --build
   docker exec -it thinkai-ollama ollama pull llama3.2:3b
   ```

4. **Acessar (endpoint público)**
   - Página: `http://SEU_IP_PUBLICO`
   - API: `http://SEU_IP_PUBLICO:8000` (ex.: `curl http://SEU_IP_PUBLICO:8000/health`)

5. **Economizar:** ao terminar o estudo, **pare** a instância no console
   (EC2 → Instâncias → *Stop instance*). Para retomar, *Start* (o IP público muda;
   use um **Elastic IP** se quiser fixar — grátis enquanto associado a uma instância em execução).

### Fontes consultadas (junho/2026)
- AWS Free Tier 2026 — US$ 200 em créditos / 6 meses:
  <https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits/>
- Preço EC2 on-demand (t3.large ≈ US$ 0,0832/h):
  <https://aws.amazon.com/ec2/pricing/on-demand/>
- Requisitos do Ollama com `llama3.2:3b` (~3 GB RAM, roda em CPU/t3.large):
  <https://lowendtalk.com/discussion/201172/minimum-spec-for-ollama-with-llama-3-2-3b>

---

## Estrutura do projeto

```
estudo-chatbot/
├─ api/                  # Backend (uv)
│  └─ app/
│     ├─ main.py         # FastAPI: /session, /chat (SSE), /history, /health
│     ├─ graph.py        # Grafo LangGraph (ChatOllama + checkpointer)
│     ├─ chat.py         # Streaming SSE e leitura de histórico
│     ├─ config.py       # Settings (.env)
│     └─ schemas.py
├─ web/                  # Frontend (bun)
│  └─ src/
│     ├─ App.tsx
│     ├─ api/client.ts   # createSession / streamChat / fetchHistory
│     ├─ hooks/          # useSession, useChat, useTheme
│     ├─ components/     # Header, Greeting, PromptCards, ChatInput, MessageList...
│     └─ styles/         # theme.css (claro/nocturne) + app.css
├─ docker-compose.yml    # ollama + api + web
└─ README.md
```
