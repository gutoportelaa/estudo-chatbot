# Runbook — Infraestrutura AWS (ThinkAI / Entrega Final)

Passo a passo para subir a aplicação na AWS, alinhado às issues **C1** (S3) e
**F1–F3** (VPC, segurança, EC2). Custo otimizado para o modelo "EC2 só nas demos".

> **Conta / orçamento:** o modelo atual da AWS oferece **US$100 em créditos**
> (não o free tier clássico de 12 meses). Os créditos duram o projeto se evitarmos
> os vilões de custo abaixo.

## Vilões de custo (evitar)
| Item | Custo | Decisão |
|---|---|---|
| **NAT Gateway** | ~US$0,045/h (~US$32/mês) **ocioso** | ❌ não usar — banco na subnet privada não precisa de internet de saída |
| **EC2 ligada 24/7** | ~US$15/mês (t3.micro) | ⏸️ desligar entre demos |
| **Elastic IP parado** | ~US$0,005/h (~US$3,6/mês) | liberar entre demos ou aceitar o custo baixo |
| **RDS** | cobra mesmo ocioso | ❌ no protótipo: Postgres em container na EC2 |

S3, SSM (params standard), IAM, VPC, IGW e Security Groups são **grátis** no uso do projeto.

---

## Ordem de bootstrap (console AWS, região `us-east-1`)

### F1 — Rede (VPC)
1. **VPC → Create VPC → "VPC and more"**: nome `thinkai`, CIDR `10.0.0.0/16`,
   1 subnet pública + 1 privada, **NAT gateways = None**, IGW incluído. Create.
   - A subnet pública hospeda a EC2; a privada existe para o banco (cumpre INF-001).

### F2 — Firewall, segredos e HTTPS
2. **EC2 → Security Groups → Create** (`thinkai-sg`). Inbound:
   - `HTTP 80` ← `0.0.0.0/0`
   - `HTTPS 443` ← `0.0.0.0/0`
   - `SSH 22` ← **My IP** (apenas seu IP de administração)
3. **Systems Manager → Parameter Store**: criar **SecureString** para cada segredo:
   `/thinkai/GROQ_API_KEY`, `/thinkai/SECRET_KEY`, `/thinkai/DB_PASSWORD`, etc.
   (A EC2 lê na inicialização; nada de segredo no `.env` em produção.)

### C1 — Bucket de PDFs (S3) + permissão (IAM)
4. **S3 → Create bucket**: `thinkai-pdfs-<sufixo-único>`, mesma região,
   **Block all public access = ON** (acesso só via app/presigned URL).
5. **IAM → Policies → Create** (`thinkai-s3-policy`, JSON):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::thinkai-pdfs-<sufixo>/*"
       },
       {
         "Effect": "Allow",
         "Action": ["ssm:GetParameter", "ssm:GetParametersByPath"],
         "Resource": "arn:aws:ssm:*:*:parameter/thinkai/*"
       }
     ]
   }
   ```
6. **IAM → Roles → Create role → EC2**, anexe `thinkai-s3-policy`. Nome `thinkai-ec2-role`.
   - Assim a EC2 acessa S3 e SSM **sem chave de acesso no disco** (boa prática AWS).

### F3 — Servidor (EC2) + deploy
7. **EC2 → Launch instance**: Ubuntu, `t3.micro`, **VPC `thinkai` + subnet pública**,
   **Auto-assign public IP = Enable**, SG `thinkai-sg`, **IAM instance profile =
   `thinkai-ec2-role`**, key pair para SSH.
8. **Elastic IP → Allocate → Associate** à instância (IP estável).
9. Na instância (SSH): instalar Docker + Compose, `git clone`, `docker compose up -d`.
   - O CD em `.github/workflows/cd.yml` já automatiza isso (GHCR → `docker compose pull`).
     Configure os secrets do repo: `EC2_HOST` (Elastic IP), `EC2_USER`, `EC2_SSH_KEY`, `GHCR_TOKEN`.
   - ⚠️ O CD dispara em **`main`** — **promover `dev → main`** antes do deploy.

### HTTPS barato (sem ALB/ACM)
Usar **Caddy** como reverse proxy na própria EC2 — emite e renova TLS via
Let's Encrypt automaticamente (só precisa de um domínio apontando para o Elastic IP):
```
thinkai.seudominio.com {
    reverse_proxy localhost:8000   # API
    # frontend servido pelo nginx/estático conforme o compose
}
```
Alternativa sem domínio: HTTP na 80 para a demo (a banca aceita, mas 443 pontua mais).

### Economia (opcional) — desligar fora de horário
**EventBridge → Schedule** (cron) → **Lambda** chamando `ec2:StopInstances`/
`StartInstances`. Ou simplesmente parar a instância manualmente após cada demo.

---

## Componentes adicionais no deploy (#33 extração, #34 RAG)

- **Banco com pgvector.** O `docker-compose.yml` usa a imagem
  **`pgvector/pgvector:pg16`** (Postgres + extensão `vector`). O RAG (#34) não
  funciona sem ela. A migration `e5c3d9a2b1f7` roda `CREATE EXTENSION vector`.
- **Migrations automáticas.** O `Dockerfile` da API roda `alembic upgrade head`
  antes de subir o uvicorn (single-instance). Num deploy multi-instância, rode as
  migrations num passo separado. Os arquivos do Alembic já vão na imagem.
- **Extração de texto (#33).** A imagem da API inclui `tesseract-ocr` (+`-por`).
  Em produção pode-se preferir **AWS Textract** (`OCR_ENGINE=textract`) — mais
  acurácia e imagem menor. Requer permissão IAM `textract:DetectDocumentText`
  (adicionar à policy da EC2 se usar Textract).
- **Embeddings do RAG (#34) — atenção.** Hoje só o embedder **Ollama** está
  implementado; `EMBEDDING_PROVIDER=gemini|bedrock` ainda levanta
  `NotImplementedError`. Para RAG em produção: (a) implementar o embedder
  gerenciado (Bedrock Titan → permissão `bedrock:InvokeModel`; ou Gemini
  embeddings), **ou** (b) rodar um Ollama acessível. Sem isso, o chat funciona
  normalmente, apenas **sem** recuperação de material (o RAG falha em silêncio,
  por design — nunca quebra o chat).
- **Config nova em produção** (via SSM/`.env`): `OCR_ENGINE`, `OCR_LANGUAGE`,
  `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_MAX_TOKENS`,
  `TOOL_OUTPUT_MAX_TOKENS`, além de `STORAGE_BACKEND=s3` + `S3_BUCKET`. Ver
  `.env.example`.

---

## Mapa serviço → issue
- **C1**: S3 (bucket) + IAM Role (passos 4–6) + presigned URLs no backend.
- **F1**: VPC/subnets/IGW/rotas (passo 1).
- **F2**: Security Group + SSM + IAM + HTTPS (passos 2–3, 5–6, Caddy).
- **F3**: EC2 + Elastic IP + deploy (passos 7–9).

## Checklist de aceitação (do PDF)
- [ ] App acessível via Internet (INF-003)
- [ ] VPC configurada (INF-001)
- [ ] Security groups aplicados; SSH restrito (INF-002)
- [ ] Integração LLM operacional em produção (RF-TEC-001)
- [ ] Upload de PDF ≤ 50 MB via S3 (RF-002)
- [ ] Banco com pgvector no ar e migrations aplicadas (`alembic current` = head)
- [ ] Extração de texto funcionando (PyMuPDF; OCR via Tesseract ou Textract)
- [ ] RAG: embedder de produção definido (Bedrock/Gemini) ou aceite explícito de rodar sem RAG
