# Backend FastAPI + LangGraph, gerenciado com uv.
FROM python:3.12-slim

# uv: gerenciador de pacotes Python.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instala dependências primeiro (cache de camadas).
COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
