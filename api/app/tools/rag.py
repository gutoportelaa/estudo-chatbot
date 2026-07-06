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

from sqlalchemy import delete, func, select
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
    """Contrato de embeddings: texto(s) → vetor(es).

    ``provider``/``model_id`` identificam o espaço vetorial: embeddings de
    modelos diferentes não são comparáveis, então essa proveniência é gravada em
    cada chunk e usada para filtrar a busca ao modelo vigente.
    """

    provider: str
    model_id: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAICompatEmbedder:
    """Embeddings via endpoint OpenAI-compatível (Ollama no dev).

    Embeda os textos concorrentemente (um a um) para compatibilidade ampla com
    o backend local; provedores que aceitam batch continuam corretos.
    """

    def __init__(self, *, base_url: str, api_key: str, model: str, provider: str = "ollama") -> None:
        self.base_url = base_url
        self.api_key = api_key or "no-key"
        self.model = model
        self.provider = provider
        self.model_id = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

        async def _one(t: str) -> list[float]:
            # encoding_format="float": o SDK da OpenAI usa base64 por padrão quando
            # há numpy, o que alguns provedores (ex.: OpenRouter) não devolvem —
            # forçar float garante compatibilidade ampla.
            resp = await client.embeddings.create(
                model=self.model, input=t, encoding_format="float"
            )
            return list(resp.data[0].embedding)

        return list(await asyncio.gather(*(_one(t) for t in texts)))


def get_embedder(settings: Settings) -> Embedder:
    """Seleciona o embedder por configuração — troca sem alterar as chamadas.

    Dev/teste usa Ollama (OpenAI-compat) como primário. Para a entrega AWS,
    plugar aqui um embedder Gemini/Bedrock Titan mantendo o mesmo contrato
    ``Embedder`` (com ``provider``/``model_id``) — ao trocar o modelo, os chunks
    do modelo antigo ficam obsoletos e devem ser re-vetorizados (``reindex_user``).
    """
    provider = settings.embedding_provider.lower()
    if provider == "ollama":
        model = settings.embedding_model or settings.ollama_model
        return OpenAICompatEmbedder(
            base_url=settings.ollama_base_url, api_key="ollama", model=model, provider="ollama"
        )
    if provider == "gemini":
        # Gemini expõe embeddings via endpoint OpenAI-compatível — reusa a mesma
        # classe. Modelo estável: gemini-embedding-001.
        model = settings.embedding_model or "gemini-embedding-001"
        return OpenAICompatEmbedder(
            base_url=settings.gemini_openai_base_url,
            api_key=settings.gemini_api_key,
            model=model,
            provider="gemini",
        )
    if provider == "openrouter":
        # OpenRouter expõe /embeddings (OpenAI-compat). Modelo free por padrão:
        # nvidia/llama-nemotron-embed-vl-1b-v2:free (dim 2048).
        model = settings.embedding_model or "nvidia/llama-nemotron-embed-vl-1b-v2:free"
        return OpenAICompatEmbedder(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            model=model,
            provider="openrouter",
        )
    # Bedrock Titan: implementar quando a entrega usar AWS Bedrock.
    raise NotImplementedError(
        f"Embedder para provider '{provider}' ainda não implementado "
        "(use 'ollama', 'gemini' ou 'openrouter')"
    )


# ---------------------------------------------------------------------------
# Ingestão e recuperação (pgvector)
# ---------------------------------------------------------------------------


def chunk_pages(text: str, *, size: int, overlap: int) -> list[tuple[str, int | None]]:
    """Chunking ciente de página: usa o separador ``\\f`` (inserido na extração)
    para atribuir a página de origem a cada chunk. Documentos antigos (sem ``\\f``)
    caem no chunking simples com página ``None``.
    """
    if "\f" not in text:
        return [(p, None) for p in chunk_text(text, size=size, overlap=overlap)]
    out: list[tuple[str, int | None]] = []
    for page_no, page in enumerate(text.split("\f"), start=1):
        for piece in chunk_text(page, size=size, overlap=overlap):
            out.append((piece, page_no))
    return out


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
    paged = chunk_pages(text, size=settings.rag_chunk_size, overlap=settings.rag_chunk_overlap)
    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
    if not paged:
        await db.commit()
        return 0

    pieces = [p for p, _ in paged]
    vectors = await embedder.embed(pieces)
    for i, ((piece, page), vec) in enumerate(zip(paged, vectors)):
        db.add(
            Chunk(
                document_id=document_id,
                user_id=user_id,
                chunk_index=i,
                page=page,
                text=piece,
                embedding=vec,
                embedding_provider=embedder.provider,
                embedding_model=embedder.model_id,
            )
        )
    await db.commit()
    logger.info(
        "Indexados %d chunks do documento %s (embedder %s:%s)",
        len(pieces),
        document_id,
        embedder.provider,
        embedder.model_id,
    )
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

    **Guard de consistência:** só compara chunks vetorizados com o **mesmo
    modelo** do embedder atual — vetores de modelos diferentes são incomparáveis.
    Chunks obsoletos (de outro modelo) são ignorados até serem re-vetorizados.

    Restringe a ``document_ids`` quando fornecido (ex.: chat sobre docs
    selecionados). Isolado por ``user_id``.
    """
    if not query.strip() or k <= 0:
        return []
    qvec = (await embedder.embed([query]))[0]

    stmt = select(Chunk).where(
        Chunk.user_id == user_id,
        Chunk.embedding_provider == embedder.provider,
        Chunk.embedding_model == embedder.model_id,
    )
    if document_ids:
        stmt = stmt.where(Chunk.document_id.in_(document_ids))
    stmt = stmt.order_by(Chunk.embedding.cosine_distance(qvec)).limit(k)

    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def count_stale_chunks(db: AsyncSession, embedder: Embedder, *, user_id: str) -> int:
    """Quantos chunks do usuário estão vetorizados com um modelo diferente do atual.

    Insumo para decidir se é preciso re-vetorizar (ex.: após trocar de provedor
    de embeddings ao subir para produção).
    """
    return int(
        await db.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.user_id == user_id,
                (Chunk.embedding_provider != embedder.provider)
                | (Chunk.embedding_model != embedder.model_id),
            )
        )
        or 0
    )


async def reindex_user(
    db: AsyncSession,
    embedder: Embedder,
    *,
    user_id: str,
    settings: Settings,
    load_text,
    only_stale: bool = True,
) -> dict:
    """Re-vetoriza os documentos do usuário com o embedder atual.

    Usado ao trocar o modelo de embeddings (ex.: dev Ollama → produção
    Gemini/Bedrock): os vetores antigos ficam num espaço incompatível e precisam
    ser regerados a partir do **texto já extraído** (não reprocessa o PDF).

    - ``load_text(document)`` → texto extraído do documento (async).
    - ``only_stale``: pula documentos cujos chunks já estão no modelo atual.

    Retorna um resumo ``{documents, reindexed, skipped, chunks}``.
    """
    docs = list(
        (
            await db.execute(
                select(Document).where(
                    Document.user_id == user_id,
                    Document.extraction_status == "done",
                    Document.extracted_key.is_not(None),
                )
            )
        ).scalars()
    )

    reindexed = skipped = total_chunks = 0
    for doc in docs:
        if only_stale:
            current = await db.scalar(
                select(func.count(Chunk.id)).where(
                    Chunk.document_id == doc.id,
                    Chunk.embedding_provider == embedder.provider,
                    Chunk.embedding_model == embedder.model_id,
                )
            )
            if current:
                skipped += 1
                continue
        text = await load_text(doc)
        n = await index_document(
            db,
            embedder,
            document_id=doc.id,
            user_id=user_id,
            text=text,
            settings=settings,
        )
        reindexed += 1
        total_chunks += n

    return {
        "documents": len(docs),
        "reindexed": reindexed,
        "skipped": skipped,
        "chunks": total_chunks,
    }


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
