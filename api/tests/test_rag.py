"""Testes de RAG (chunking + seleção de embedder) — issue #34.

As operações vetoriais (index/retrieve) dependem de Postgres+pgvector e são
validadas em smoke E2E; aqui cobrimos a lógica pura e a troca de embedder por
configuração (espelha o critério "trocar sem alterar as chamadas").
"""

from __future__ import annotations

import pytest

from app.tools.rag import OpenAICompatEmbedder, chunk_text, get_embedder


def test_chunk_text_empty_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_short_text_single_chunk():
    out = chunk_text("frase curta", size=1000, overlap=100)
    assert out == ["frase curta"]


def test_chunk_text_splits_with_overlap_and_covers_text():
    text = " ".join(f"palavra{i}" for i in range(200))
    chunks = chunk_text(text, size=200, overlap=40)
    assert len(chunks) > 1
    # Cada chunk respeita ~o tamanho pedido (com folga do corte em espaço).
    assert all(len(c) <= 200 for c in chunks)
    # Cobertura: o começo e o fim do texto aparecem nos chunks.
    assert "palavra0" in chunks[0]
    assert "palavra199" in chunks[-1]


def test_chunk_text_overlap_preserves_boundary_context():
    text = "A" * 50 + " " + "B" * 50 + " " + "C" * 50
    chunks = chunk_text(text, size=70, overlap=30)
    # Com overlap, chunks consecutivos compartilham conteúdo na fronteira.
    assert len(chunks) >= 2


def test_get_embedder_ollama_returns_openai_compat():
    class _S:
        embedding_provider = "ollama"
        embedding_model = ""
        ollama_model = "llama3.2:3b"
        ollama_base_url = "http://localhost:11434/v1"

    emb = get_embedder(_S())
    assert isinstance(emb, OpenAICompatEmbedder)
    assert emb.model == "llama3.2:3b"
    # Proveniência: usada para gravar em cada chunk e filtrar a busca ao modelo.
    assert emb.provider == "ollama"
    assert emb.model_id == "llama3.2:3b"


def test_get_embedder_gemini_uses_openai_compat_endpoint():
    class _S:
        embedding_provider = "gemini"
        embedding_model = ""
        gemini_api_key = "k"
        gemini_openai_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

    emb = get_embedder(_S())
    assert isinstance(emb, OpenAICompatEmbedder)
    assert emb.provider == "gemini"
    assert emb.model_id == "gemini-embedding-001"  # default estável
    assert emb.base_url.endswith("/openai/")


def test_get_embedder_unknown_provider_raises():
    class _S:
        embedding_provider = "bedrock"
        embedding_model = ""

    with pytest.raises(NotImplementedError):
        get_embedder(_S())
