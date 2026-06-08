# ThinkAI — Chatbot multiusuário (estudo)

[![CI](https://github.com/gutoportelaa/estudo-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/gutoportelaa/estudo-chatbot/actions/workflows/ci.yml)

Protótipo funcional de um chatbot multiusuário, usando **Google Gemini** como LLM
e **LangGraph** para orquestração com histórico isolado por sessão.

| Camada    | Stack                                                    | Gerenciador |
| --------- | -------------------------------------------------------- | ----------- |
| `web/`    | React + TypeScript + Vite                                | **bun / npm** |
| `api/`    | Python + FastAPI + LangGraph + `langchain-google-genai` | **uv**      |
| LLM       | Google Gemini · modelo `gemini-2.0-flash` (API gratuita) | —           |
| Histórico | LangGraph `SqliteSaver` (`thread_id = session_id`)       | —           |

---

## Como funciona (arquitetura)

![Diagrama de arquitetura do ThinkAI](docs/diagrama_thinkai.png)

- **Multiusuário:** o backend é assíncrono; cada requisição protegida usa `Authorization: Bearer <token>`.
- **Isolamento:** o histórico é guardado por sessão no PostgreSQL, então cada resposta volta apenas para a sessão correta.
- **Persistência:** o histórico sobrevive a reinícios do servidor (PostgreSQL containerizado).

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
# edite .env e preencha: GEMINI_API_KEY=sua_chave_aqui
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (`web/`)
```bash
cd web
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm install            # ou: bun install
npm run dev            # ou: bun run dev
```

Abra <http://localhost:5173>, envie uma mensagem e veja a resposta em streaming.
Use o botão 🌙/☀️ no topo para alternar entre claro e nocturne.

---

## Rodando com Docker (tudo junto)

```bash
# Na raiz do projeto:
cp .env.example .env
# edite .env e preencha: GEMINI_API_KEY=sua_chave_aqui

docker compose up -d --build
```

- Web: <http://localhost> (porta 80)
- API: <http://localhost:8000>

---

## Documentação do endpoint (API)

Base URL local: `http://localhost:8000`

### `GET /health`
Verifica se a API está no ar.
```bash
curl http://localhost:8000/health
# {"status":"ok","model":"gemini-2.0-flash"}
```

### `POST /auth/signup`
Cria um novo usuário.
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"123456"}'
```

### `POST /auth/signin`
Autentica e retorna JWT.
```bash
curl -X POST http://localhost:8000/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"123456"}'
# {"access_token":"...","token_type":"bearer"}
```

### `GET /auth/profile`
Retorna perfil do usuário autenticado.
```bash
curl http://localhost:8000/auth/profile \
  -H "Authorization: Bearer <jwt>"
```

### `GET /sessions`
Lista as sessões do usuário autenticado.
```bash
curl http://localhost:8000/sessions \
  -H "Authorization: Bearer <jwt>"
```

### `POST /sessions`
Cria nova sessão para o usuário autenticado.
```bash
curl -X POST http://localhost:8000/sessions \
  -H "Authorization: Bearer <jwt>"
```

### `DELETE /sessions/{id}`
Remove uma sessão do usuário autenticado.
```bash
curl -X DELETE http://localhost:8000/sessions/<session_id> \
  -H "Authorization: Bearer <jwt>"
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
  -H "Authorization: Bearer <jwt>" \
  -d '{"session_id":"<uuid>","message":"Explique o que é uma API REST"}'
```

Exemplo no browser (consumindo o stream):
```js
const res = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  },
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
curl http://localhost:8000/history/<uuid> \
  -H "Authorization: Bearer <jwt>"
# {"session_id":"...","messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

> Documentação interativa (Swagger) disponível em `http://localhost:8000/docs`.

---

## Testando o frontend com Vite

Use este roteiro para validar a integração JWT + sessões no browser:

1. Suba a API:
```bash
cd api
uv run uvicorn app.main:app --reload --port 8000
```

2. Em outro terminal, suba o frontend com Vite:
```bash
cd web
npm install
npm run dev
```

3. Abra `http://localhost:5173` e valide:
- tela inicial mostra formulário de autenticação
- `Criar conta` cria usuário e já autentica
- após login, aparece seletor de sessão + botão `Nova sessão`
- cada conversa tem menu de três pontos para `Renomear` ou `Remover conversa`
- enviar mensagem faz streaming normalmente
- trocar sessão troca histórico
- botão de logout limpa estado autenticado

4. Verificação rápida no DevTools (Network):
- requests protegidas com header `Authorization: Bearer ...`
- `POST /chat` com SSE e bearer

## Demonstrando o histórico isolado por sessão

Cada usuário recebe um `session_id` (UUID) e o histórico é guardado por `thread_id = session_id`
no `SqliteSaver`. Há duas formas práticas de demonstrar o isolamento:

### A) Pelo navegador (multiusuário real)
Cada usuário autenticado pode ter várias sessões, e cada sessão mantém seu histórico isolado:
1. Faça login no navegador normal e crie uma sessão A.
2. Envie: *"Meu nome é Ana"*.
3. Crie uma sessão B e pergunte: *"Qual é o meu nome?"*.
4. A sessão A lembra "Ana"; a B não compartilha o mesmo contexto.

> Para simular usuários distintos, use uma janela anônima e autentique com outro usuário.

### B) Por script (reproduzível, via API)
Com a API rodando, execute o roteiro pronto que cria duas sessões e comprova o isolamento:
```bash
./scripts/demo_sessions.sh
# ou apontando para outra URL:
API_URL=http://SEU_IP_PUBLICO:8000 ./scripts/demo_sessions.sh
```
Saída esperada (resumo): a sessão **A** aprende e lembra o nome/cor; a sessão **B**, com outro
`session_id`, não tem acesso a esses dados, e `GET /history` mostra os históricos separados.

---

## Deploy na AWS EC2 (público) - Guia Passo a Passo

Como este pode ser seu primeiro contato com a infraestrutura da AWS, aqui está um guia didático e detalhado de como subir a aplicação usando o nível gratuito (Free Tier).

### Passo 1: Criando a Instância EC2 (O seu "Computador na Nuvem")

1. Acesse o [Console da AWS](https://console.aws.amazon.com/) e faça login.
2. Na barra de pesquisa superior, digite **EC2** e clique no primeiro resultado.
3. No painel esquerdo ou na tela principal, clique no botão laranja **Launch instance** (Executar instância).
4. **Name and tags:** Dê um nome para o seu servidor, por exemplo: `thinkai-server`.
5. **Application and OS Images (Amazon Machine Image):** 
   - Selecione **Ubuntu**.
   - Na lista, escolha a versão **Ubuntu Server 24.04 LTS (HVM)** (verifique se tem a tag *Free tier eligible*).
6. **Instance type:** Selecione **t2.micro** (também *Free tier eligible*, possui 1 vCPU e 1 GB de RAM).
7. **Key pair (login):** 
   - Clique em **Create new key pair**.
   - Nome: `thinkai-key` (ou o que preferir).
   - Tipo: **RSA**, Formato: **.pem** (para Mac/Linux) ou **.ppk** (para Windows usando PuTTY).
   - Clique em **Create key pair**. O download do arquivo começará automaticamente. **Guarde este arquivo**, ele é sua única forma de acessar o servidor!
8. **Network settings:**
   - Marque a caixa **Allow SSH traffic from** e selecione **My IP** (Isso garante que apenas o seu computador atual pode acessar via terminal).
   - Marque a caixa **Allow HTTP traffic from the internet** (Para que qualquer pessoa consiga acessar a porta 80 e ver o site).
9. **Configure storage:** Pode deixar o padrão de **8 GiB** (gp3). O free tier permite até 30 GB, se quiser aumentar.
10. Clique no botão laranja **Launch instance** no canto inferior direito.

### Passo 2: Configurando as Portas Extras (Security Group)

Nossa aplicação precisa da porta **8000** aberta para a comunicação da API com o Frontend.

1. No console do EC2, vá em **Instances** (no menu lateral esquerdo) e clique no ID da sua nova instância.
2. Na aba **Security**, na parte inferior da tela, clique no link abaixo de **Security groups** (ex: `sg-0abcd1234...`).
3. Na aba **Inbound rules** (Regras de entrada), clique em **Edit inbound rules**.
4. Clique em **Add rule** no final da lista:
   - **Type:** Custom TCP
   - **Port range:** 8000
   - **Source:** Anywhere-IPv4 (`0.0.0.0/0`)
   - **Description:** API Backend
5. Clique em **Save rules**.

### Passo 3: Conectando no Servidor

Agora vamos acessar o terminal do seu servidor na AWS.

1. Volte na tela de **Instances**, selecione sua instância e copie o **Public IPv4 address** (ex: `15.228.x.x`).
2. Abra o terminal (no Linux/Mac) ou o PowerShell (no Windows).
3. Navegue até a pasta onde salvou o arquivo `.pem` do Passo 1.
4. (Apenas Linux/Mac) Ajuste a permissão da chave para que não seja pública:
   ```bash
   chmod 400 thinkai-key.pem
   ```
5. Conecte-se:
   ```bash
   ssh -i "thinkai-key.pem" ubuntu@SEU_IP_PUBLICO
   ```
   *Se perguntar se tem certeza que deseja continuar conectando, digite `yes` e dê Enter.*

### Passo 4: Instalando Docker e Baixando o Projeto

Dentro do terminal da sua EC2, execute os comandos abaixo, um por um:

```bash
# Atualiza os pacotes e instala o Docker e o Git
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git

# Dá permissão para o usuário 'ubuntu' rodar o Docker sem precisar de 'sudo'
sudo usermod -aG docker ubuntu && newgrp docker

# Baixa o código do projeto
git clone https://github.com/gutoportelaa/estudo-chatbot.git && cd estudo-chatbot
```

### Passo 5: Configurando Senhas e Rodando (Deploy)

Vamos criar o arquivo de variáveis de ambiente (`.env`) e iniciar os containers:

```bash
# 1. Crie o arquivo .env e adicione a chave do Gemini
echo 'GEMINI_API_KEY=sua_chave_aqui' > .env

# 2. Gere uma chave secreta para a autenticação JWT
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env

# 3. Defina uma senha segura para o banco de dados
echo 'DB_PASSWORD=senha_super_segura_123' >> .env

# 4. Aponte o frontend para o IP público da sua EC2
sed -i 's#http://localhost:8000#http://SEU_IP_PUBLICO:8000#' docker-compose.yml

# 5. Inicie a aplicação (vai baixar as imagens, construir e rodar em segundo plano)
docker compose up -d --build
```

### Passo 6: Acessando e Testando

Após o comando anterior terminar, sua aplicação está no ar!

- **Acesse pelo navegador:** `http://SEU_IP_PUBLICO` (deve abrir a tela de login).
- **Teste a API (Healthcheck):** Pode ser feito no seu terminal local ou abrindo `http://SEU_IP_PUBLICO:8000/health` no navegador. Deve retornar `{"status":"ok"}`.

> **Dica de Economia:** Quando não estiver mais estudando ou usando, vá no console da AWS, selecione a instância e clique em **Instance state -> Stop instance**. Instâncias paradas não cobram por hora de uso (apenas centavos pelo armazenamento do disco). Lembre-se que, ao iniciar de novo (Start instance), **o IP público mudará**, então você precisará atualizar o IP no `docker-compose.yml` e rodar `docker compose up -d` novamente. Caso queira fixar o IP público para não mudar nunca mais, você pode usar a funcionalidade de **Elastic IP** (que é gratuita se associada a uma instância em execução).

---

## Estrutura do projeto

```
estudo-chatbot/
├─ api/                  # Backend (uv)
│  └─ app/
│     ├─ main.py         # FastAPI: /health e inclusão de routers
│     ├─ graph.py        # Grafo LangGraph (ChatGoogleGenerativeAI + checkpointer)
│     ├─ chat.py         # Streaming SSE e leitura de histórico
│     ├─ config.py       # Settings (.env)
│     └─ schemas.py
├─ web/                  # Frontend (bun)
│  └─ src/
│     ├─ App.tsx
│     ├─ api/client.ts   # auth JWT + sessões + chat/history
│     ├─ hooks/          # useAuth, useSessions, useChat, useTheme
│     ├─ components/     # Header, Greeting, PromptCards, ChatInput, MessageList...
│     └─ styles/         # theme.css (claro/nocturne) + app.css
├─ scripts/
│  └─ demo_sessions.sh   # Demonstra isolamento de sessões via API
├─ .env.example          # Variáveis para docker-compose
├─ docker-compose.yml    # api + web
└─ README.md
```
