from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.jobs import process_summary
from app.models import Document, Summary, SummaryDocument, User
from app.storage import get_storage


@pytest.fixture
def storage_tmp(tmp_path):
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_DIR"] = str(tmp_path / "docs")
    get_settings.cache_clear()
    get_storage.cache_clear()
    yield
    for var in ("STORAGE_BACKEND", "STORAGE_DIR"):
        os.environ.pop(var, None)
    get_settings.cache_clear()
    get_storage.cache_clear()


def _seed_summary(*, status="pending", ready_document=True) -> str:
    user_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    summary_id = str(uuid.uuid4())
    storage = get_storage()
    pdf_key = f"{user_id}/{doc_id}.pdf"
    text_key = f"{user_id}/{doc_id}.txt"
    storage.save(pdf_key, b"%PDF-1.4\n%%EOF\n")
    if ready_document:
        storage.save(text_key, b"Texto extraido do documento para resumir.")

    async def _go():
        async with AsyncSessionLocal() as db:
            db.add(User(id=user_id, username=f"user_{user_id}", password_hash="hash"))
            db.add(
                Document(
                    id=doc_id,
                    user_id=user_id,
                    filename="material.pdf",
                    size_bytes=16,
                    content_type="application/pdf",
                    storage_backend="local",
                    storage_key=pdf_key,
                    page_count=1 if ready_document else None,
                    extraction_status="done" if ready_document else "pending",
                    extracted_key=text_key if ready_document else None,
                )
            )
            db.add(
                Summary(
                    id=summary_id,
                    user_id=user_id,
                    status=status,
                    title="Resumo existente" if status == "done" else None,
                    content="Conteudo existente" if status == "done" else None,
                    mindmap="# Existente" if status == "done" else None,
                    llm_model="modelo-antigo" if status == "done" else None,
                )
            )
            db.add(SummaryDocument(summary_id=summary_id, document_id=doc_id))
            await db.commit()
            return summary_id

    return asyncio.run(_go())


def _summary_from_db(summary_id: str) -> Summary | None:
    async def _go():
        async with AsyncSessionLocal() as db:
            return await db.get(Summary, summary_id)

    return asyncio.run(_go())


def test_process_summary_generates_content_and_marks_done(storage_tmp, monkeypatch):
    summary_id = _seed_summary()
    calls: dict[str, object] = {}

    def _build_chat_client(settings):
        calls["settings"] = settings
        return object(), "modelo-teste"

    async def _summarize_documents(client, model, docs):
        calls["summary_docs"] = docs
        return "Titulo gerado", "## Resumo\n- Conteudo gerado"

    async def _generate_mindmap(client, model, docs):
        calls["mindmap_docs"] = docs
        return "# Mapa\n## material.pdf\n- Conteudo"

    monkeypatch.setattr("app.llm.build_chat_client", _build_chat_client)
    monkeypatch.setattr("app.tools.summarize.summarize_documents", _summarize_documents)
    monkeypatch.setattr("app.tools.summarize.generate_mindmap_from_documents", _generate_mindmap)

    result = asyncio.run(process_summary({}, summary_id))

    assert result == {"summary_id": summary_id, "status": "done"}
    summary = _summary_from_db(summary_id)
    assert summary is not None
    assert summary.status == "done"
    assert summary.title == "Titulo gerado"
    assert summary.content == "## Resumo\n- Conteudo gerado"
    assert summary.mindmap == "# Mapa\n## material.pdf\n- Conteudo"
    assert summary.llm_model == "modelo-teste"
    assert summary.error is None
    assert calls["summary_docs"] == [("material.pdf", "Texto extraido do documento para resumir.")]
    assert calls["mindmap_docs"] == [("material.pdf", "Texto extraido do documento para resumir.")]


def test_process_summary_fails_when_document_has_no_extracted_text(storage_tmp, monkeypatch):
    summary_id = _seed_summary(ready_document=False)

    def _build_chat_client(settings):
        raise AssertionError("Nao deveria chamar LLM sem texto extraido")

    monkeypatch.setattr("app.llm.build_chat_client", _build_chat_client)

    result = asyncio.run(process_summary({}, summary_id))

    assert result["summary_id"] == summary_id
    assert result["status"] == "failed"
    summary = _summary_from_db(summary_id)
    assert summary is not None
    assert summary.status == "failed"
    assert "sem texto" in summary.error
    assert summary.content is None
    assert summary.mindmap is None


def test_process_summary_marks_failed_when_llm_generation_fails(storage_tmp, monkeypatch):
    summary_id = _seed_summary()

    def _build_chat_client(settings):
        return object(), "modelo-teste"

    async def _summarize_documents(client, model, docs):
        raise RuntimeError("falha na llm")

    async def _generate_mindmap(client, model, docs):
        raise AssertionError("Nao deveria gerar mindmap apos falha no resumo")

    monkeypatch.setattr("app.llm.build_chat_client", _build_chat_client)
    monkeypatch.setattr("app.tools.summarize.summarize_documents", _summarize_documents)
    monkeypatch.setattr("app.tools.summarize.generate_mindmap_from_documents", _generate_mindmap)

    result = asyncio.run(process_summary({}, summary_id))

    assert result["summary_id"] == summary_id
    assert result["status"] == "failed"
    summary = _summary_from_db(summary_id)
    assert summary is not None
    assert summary.status == "failed"
    assert "falha na llm" in summary.error
    assert summary.title is None
    assert summary.content is None
    assert summary.mindmap is None
    assert summary.llm_model is None


def test_process_summary_ignores_already_done_summary(storage_tmp, monkeypatch):
    summary_id = _seed_summary(status="done")

    def _build_chat_client(settings):
        raise AssertionError("Resumo done nao deve ser reprocessado")

    monkeypatch.setattr("app.llm.build_chat_client", _build_chat_client)

    result = asyncio.run(process_summary({}, summary_id))

    assert result == {"summary_id": summary_id, "status": "done"}
    summary = _summary_from_db(summary_id)
    assert summary is not None
    assert summary.status == "done"
    assert summary.title == "Resumo existente"
    assert summary.content == "Conteudo existente"
    assert summary.mindmap == "# Existente"
    assert summary.llm_model == "modelo-antigo"


def test_process_summary_returns_not_found_for_missing_summary(storage_tmp):
    result = asyncio.run(process_summary({}, "summary-inexistente"))

    assert result == {"summary_id": "summary-inexistente", "status": "not_found"}
