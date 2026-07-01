"""RAG: embeddings + pgvector para recuperação seletiva — issue #34.

Permite "conversar com o material" **sem colar o material inteiro no contexto**:
o texto extraído (#33) é dividido em chunks, vetorizado por embeddings e guardado
em pgvector. A cada turno, os top-k trechos mais próximos da pergunta entram como
o bloco "hits de RAG" do Context Assembler (#30), com cota própria de tokens e
citando a fonte.

    material → chunks → embeddings → pgvector
    pergunta → embedding → top-k chunks → bloco RAG (cota fixa) → resposta cita a fonte

O embedder é trocável por configuração (Ollama no dev; Gemini/Bedrock na entrega),
espelhando a abstração de OCR da #33. As funções de I/O são async; o chunking é
puro (testável sem rede/DB).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import Chunk, Document

logger = logging.getLogger("thinkai.rag")


# ---------------------------------------------------------------------------
# Chunking (puro)
# ---------------------------------------------------------------------------


def chunk_text(text: str, *, size: int = 1000, overlap: int = 150) -> list[str]:
    """Divide o texto em janelas de ~``size`` chars com ``overlap`` de sobreposição.

    A sobreposição preserva contexto na fronteira entre chunks. Quebra
    preferencialmente em espaço para não cortar palavras no meio.
    """
    text = (text or "").strip()
    if not text:
        return []
    size = max(1, size)
    overlap = max(0, min(overlap, size - 1))

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        # Tenta terminar num espaço, sem recuar demais.
        if end < n:
            space = text.rfind(" ", start + overlap, end)
            if space != -1 and space > start:
                end = space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


# ---------------------------------------------------------------------------
# Embeddings (trocável por configuração)
# ---------------------------------------------------------------------------


@runtime_checkable
class Embedder(Protocol):
    """Contrato de embeddings: texto(s) → vetor(es)."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAICompatEmbedder:
    """Embeddings via endpoint OpenAI-compatível (Ollama no dev).

    Embeda os textos concorrentemente (um a um) para compatibilidade ampla com
    o backend local; provedores que aceitam batch continuam corretos.
    """

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key or "no-key"
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

        async def _one(t: str) -> list[float]:
            resp = await client.embeddings.create(model=self.model, input=t)
            return list(resp.data[0].embedding)

        return list(await asyncio.gather(*(_one(t) for t in texts)))


def get_embedder(settings: Settings) -> Embedder:
    """Seleciona o embedder por configuração — troca sem alterar as chamadas.

    Dev/teste usa Ollama (OpenAI-compat). Para a entrega AWS, plugar aqui um
    embedder Gemini/Bedrock Titan mantendo o mesmo contrato ``Embedder``.
    """
    provider = settings.embedding_provider.lower()
    if provider == "ollama":
        model = settings.embedding_model or settings.ollama_model
        return OpenAICompatEmbedder(
            base_url=settings.ollama_base_url, api_key="ollama", model=model
        )
    # Gemini/Bedrock: implementar quando a entrega AWS estiver de pé.
    raise NotImplementedError(
        f"Embedder para provider '{provider}' ainda não implementado; use 'ollama' no dev"
    )


# ---------------------------------------------------------------------------
# Ingestão e recuperação (pgvector)
# ---------------------------------------------------------------------------


async def index_document(
    db: AsyncSession,
    embedder: Embedder,
    *,
    document_id: str,
    user_id: str,
    text: str,
    settings: Settings,
) -> int:
    """Indexa um documento: (re)gera chunks + embeddings e persiste em pgvector.

    Reindexa de forma idempotente — remove os chunks anteriores do documento
    antes de inserir os novos. Retorna a quantidade de chunks indexados.
    """
    pieces = chunk_text(text, size=settings.rag_chunk_size, overlap=settings.rag_chunk_overlap)
    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
    if not pieces:
        await db.commit()
        return 0

    vectors = await embedder.embed(pieces)
    for i, (piece, vec) in enumerate(zip(pieces, vectors)):
        db.add(
            Chunk(
                document_id=document_id,
                user_id=user_id,
                chunk_index=i,
                text=piece,
                embedding=vec,
            )
        )
    await db.commit()
    logger.info("Indexados %d chunks do documento %s", len(pieces), document_id)
    return len(pieces)


async def retrieve(
    db: AsyncSession,
    embedder: Embedder,
    *,
    user_id: str,
    query: str,
    k: int,
    document_ids: list[str] | None = None,
) -> list[Chunk]:
    """Recupera os top-k chunks do usuário mais próximos da ``query`` (cosseno).

    Restringe a ``document_ids`` quando fornecido (ex.: chat sobre docs
    selecionados). Isolado por ``user_id``.
    """
    if not query.strip() or k <= 0:
        return []
    qvec = (await embedder.embed([query]))[0]

    stmt = select(Chunk).where(Chunk.user_id == user_id)
    if document_ids:
        stmt = stmt.where(Chunk.document_id.in_(document_ids))
    stmt = stmt.order_by(Chunk.embedding.cosine_distance(qvec)).limit(k)

    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def build_rag_hits(
    db: AsyncSession, chunks: list[Chunk]
) -> list[dict[str, str]]:
    """Formata chunks recuperados como blocos de RAG, citando a fonte.

    Cada hit vira ``{"role": "system", "content": "[Fonte: <arquivo> · trecho N] ..."}``
    para que o modelo cite o trecho-fonte na resposta.
    """
    if not chunks:
        return []
    # Resolve os nomes dos arquivos-fonte (para citação) numa só consulta.
    doc_ids = {c.document_id for c in chunks}
    rows = await db.execute(select(Document.id, Document.filename).where(Document.id.in_(doc_ids)))
    names = {i: f for i, f in rows.all()}

    hits: list[dict[str, str]] = []
    for c in chunks:
        source = names.get(c.document_id, c.document_id)
        hits.append(
            {
                "role": "system",
                "content": f"[Fonte: {source} · trecho {c.chunk_index}]\n{c.text}",
            }
        )
    return hits
