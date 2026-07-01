FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# tesseract-ocr: OCR local (issue #33). Em produção pode-se usar AWS Textract
# (OCR_ENGINE=textract) e remover estes pacotes para uma imagem menor.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia o lock para um build reprodutível.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Migrations do banco (Alembic) precisam ir para a imagem.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Aplica as migrations antes de subir a API (single-instance). Para múltiplas
# instâncias, rodar as migrations num passo separado do deploy.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
