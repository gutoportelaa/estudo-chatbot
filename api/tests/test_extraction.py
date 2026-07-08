"""Testes da extração de material (PDF/imagem) — issue #33.

Critérios de aceitação:
- PDF nativo e PDF escaneado produzem texto correto pelos dois engines.
- Trocar Tesseract↔Textract por configuração, sem alterar as chamadas.
"""

from __future__ import annotations

import os
import shutil
import asyncio

import pytest

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Document
from app.storage import get_storage
from app.tools.extraction import (
    ExtractionResult,
    OcrEngine,
    TesseractOcr,
    TextractOcr,
    extract_pdf,
    get_ocr_engine,
)

fitz = pytest.importorskip("fitz")


# ---------------------------------------------------------------------------
# Helpers: gera PDFs de verdade em memória
# ---------------------------------------------------------------------------


def _native_pdf(text: str = "Fotossíntese é o processo das plantas.") -> bytes:
    """PDF com camada de texto nativa (extraível sem OCR)."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def _scanned_pdf(text: str = "TEXTO ESCANEADO") -> bytes:
    """PDF 'escaneado': página com o texto rasterizado como imagem, sem camada
    de texto nativa — força o caminho de OCR."""
    src = fitz.open()
    p = src.new_page()
    p.insert_text((72, 120), text, fontsize=40)
    pix = p.get_pixmap(dpi=150)
    src.close()

    out = fitz.open()
    page = out.new_page(width=pix.width, height=pix.height)
    page.insert_image(page.rect, stream=pix.tobytes("png"))
    data = out.tobytes()
    out.close()
    return data


# ---------------------------------------------------------------------------
# Extração nativa (PyMuPDF)
# ---------------------------------------------------------------------------


def test_native_pdf_extracts_text_without_ocr():
    result = extract_pdf(_native_pdf("Química orgânica é legal"), ocr=None)
    assert isinstance(result, ExtractionResult)
    assert result.engine == "pymupdf"
    assert result.ocr_used is False
    assert result.page_count == 1
    assert "Química orgânica" in result.text


def test_native_extraction_ignores_ocr_when_text_is_rich():
    class _BoomOcr(OcrEngine):
        name = "boom"

        def image_to_text(self, image_png: bytes) -> str:
            raise AssertionError("OCR não deveria rodar em PDF com texto nativo")

    text = "Uma frase suficientemente longa para não parecer um PDF escaneado. " * 3
    result = extract_pdf(_native_pdf(text), ocr=_BoomOcr(), ocr_min_chars_per_page=50)
    assert result.ocr_used is False
    assert result.engine == "pymupdf"


# ---------------------------------------------------------------------------
# Seleção do engine de OCR por configuração (acceptance: trocar sem mudar código)
# ---------------------------------------------------------------------------


def test_get_ocr_engine_selects_by_config():
    class _S:
        ocr_engine = "tesseract"
        ocr_language = "por+eng"
        s3_region = "us-east-1"

    assert isinstance(get_ocr_engine(_S()), TesseractOcr)
    _S.ocr_engine = "textract"
    assert isinstance(get_ocr_engine(_S()), TextractOcr)


# ---------------------------------------------------------------------------
# Fallback para OCR quando o texto nativo é esparso (engine falso, determinístico)
# ---------------------------------------------------------------------------


def test_sparse_pdf_falls_back_to_ocr_engine():
    class _FakeOcr(OcrEngine):
        name = "fake"

        def image_to_text(self, image_png: bytes) -> str:
            return "CONTEUDO RECUPERADO VIA OCR"

    result = extract_pdf(_scanned_pdf(), ocr=_FakeOcr(), ocr_min_chars_per_page=100)
    assert result.ocr_used is True
    assert result.engine == "fake"
    assert "OCR" in result.text


# ---------------------------------------------------------------------------
# Round-trip real com Tesseract (pula se o binário não estiver disponível)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract não instalado")
def test_scanned_pdf_real_tesseract_ocr():
    ocr = TesseractOcr(language="eng")
    result = extract_pdf(_scanned_pdf("HELLO WORLD"), ocr=ocr, ocr_min_chars_per_page=100)
    assert result.ocr_used is True
    assert result.engine == "tesseract"
    # OCR não é perfeito; basta reconhecer parte do texto.
    assert "HELLO" in result.text.upper() or "WORLD" in result.text.upper()


# ---------------------------------------------------------------------------
# Endpoint POST /documents/{id}/extract
# ---------------------------------------------------------------------------


@pytest.fixture
def storage_tmp(tmp_path):
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_DIR"] = str(tmp_path / "docs")
    os.environ["MAX_UPLOAD_MB"] = "5"
    get_settings.cache_clear()
    get_storage.cache_clear()
    yield
    for var in ("STORAGE_BACKEND", "STORAGE_DIR", "MAX_UPLOAD_MB"):
        os.environ.pop(var, None)
    get_settings.cache_clear()
    get_storage.cache_clear()


def _auth(client, username="extr_user", password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    r = client.post("/auth/signin", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _doc_from_db(document_id: str) -> Document | None:
    async def _go():
        async with AsyncSessionLocal() as db:
            return await db.get(Document, document_id)

    return asyncio.run(_go())


def test_extract_endpoint_persists_text_and_sets_status(client, storage_tmp):
    headers = _auth(client)
    text = (
        "Biologia celular: a mitocôndria é a usina da célula.\n"
        "Ela participa da respiração celular e ajuda a produzir ATP.\n"
        "Esse material também explica organelas, membrana plasmática e citoplasma."
    )
    pdf = _native_pdf(text)
    up = client.post("/documents", headers=headers, files={"file": ("bio.pdf", pdf, "application/pdf")})
    assert up.status_code == 201
    doc_id = up.json()["id"]
    assert up.json()["extraction_status"] == "pending"

    r = client.post(f"/documents/{doc_id}/extract", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["extraction_status"] == "done"
    assert body["page_count"] == 1
    assert body["engine"] == "pymupdf"
    assert body["artifact_ref"] == doc_id
    assert "mitocôndria" in body["summary_for_context"]

    # A listagem reflete o novo status.
    lst = client.get("/documents", headers=headers).json()
    assert lst[0]["extraction_status"] == "done"


def test_extract_large_pdf_summary_is_truncated_within_quota(client, storage_tmp):
    headers = _auth(client)
    # PDF "de 80 páginas": muito texto, deve estourar a cota e ser truncado.
    doc = fitz.open()
    for i in range(80):
        page = doc.new_page()
        page.insert_text((72, 72), f"Página {i}: " + ("conteúdo denso " * 40), fontsize=10)
    pdf = doc.tobytes()
    doc.close()

    up = client.post("/documents", headers=headers, files={"file": ("big.pdf", pdf, "application/pdf")})
    doc_id = up.json()["id"]
    r = client.post(f"/documents/{doc_id}/extract", headers=headers).json()

    settings = get_settings()
    assert r["page_count"] == 80
    assert r["truncated"] is True
    # O resumo no contexto respeita a cota — o texto inteiro NÃO entra no prompt.
    assert r["tokens"] <= settings.tool_output_max_tokens
    assert r["chars"] > r["tokens"] * 4  # muito mais texto do que foi ao contexto


def test_extract_other_users_document_is_404(client, storage_tmp):
    a = _auth(client, username="alice")
    pdf = _native_pdf()
    doc_id = client.post("/documents", headers=a, files={"file": ("a.pdf", pdf, "application/pdf")}).json()["id"]

    b = _auth(client, username="bob")
    r = client.post(f"/documents/{doc_id}/extract", headers=b)
    assert r.status_code == 404


def test_extract_failure_marks_document_as_failed(client, storage_tmp, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr("app.routers.documents.extract_pdf", _boom)

    headers = _auth(client, username="extract_fail")
    pdf = _native_pdf("Texto nativo suficiente para criar um documento valido de teste.")
    up = client.post("/documents", headers=headers, files={"file": ("fail.pdf", pdf, "application/pdf")})
    doc_id = up.json()["id"]

    response = client.post(f"/documents/{doc_id}/extract", headers=headers)

    assert response.status_code == 422
    assert "Falha na extração" in response.json()["detail"]

    docs = client.get("/documents", headers=headers).json()
    assert docs[0]["id"] == doc_id
    assert docs[0]["extraction_status"] == "failed"


def test_extract_unreadable_pdf_marks_document_as_failed(client, storage_tmp):
    headers = _auth(client, username="extract_unreadable")
    invalid_pdf = b"%PDF-1.4\nisto passa na validacao inicial, mas nao abre\n%%EOF\n"
    up = client.post(
        "/documents",
        headers=headers,
        files={"file": ("broken.pdf", invalid_pdf, "application/pdf")},
    )
    doc_id = up.json()["id"]

    response = client.post(f"/documents/{doc_id}/extract", headers=headers)

    assert response.status_code == 422
    assert "Falha" in response.json()["detail"]
    assert client.get("/documents", headers=headers).json()[0]["extraction_status"] == "failed"


def test_extract_failure_does_not_set_extracted_key_or_page_count(client, storage_tmp, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr("app.routers.documents.extract_pdf", _boom)

    headers = _auth(client, username="extract_fail_clean")
    pdf = _native_pdf("Texto nativo suficiente para criar um documento valido de teste.")
    up = client.post("/documents", headers=headers, files={"file": ("clean.pdf", pdf, "application/pdf")})
    doc_id = up.json()["id"]

    response = client.post(f"/documents/{doc_id}/extract", headers=headers)

    assert response.status_code == 422
    doc = _doc_from_db(doc_id)
    assert doc is not None
    assert doc.extraction_status == "failed"
    assert doc.extracted_key is None
    assert doc.page_count is None


def test_extract_can_retry_after_failure(client, storage_tmp, monkeypatch):
    from app.routers import documents

    original_extract_pdf = documents.extract_pdf
    calls = 0

    def _fails_once(data, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("falha temporaria")
        return original_extract_pdf(data, ocr=None)

    monkeypatch.setattr("app.routers.documents.extract_pdf", _fails_once)

    headers = _auth(client, username="extract_retry")
    text = (
        "Biologia celular: a mitocondria produz energia para a celula.\n"
        "O texto possui conteudo suficiente para a extracao nativa.\n"
        "A segunda tentativa deve concluir o processamento normalmente."
    )
    pdf = _native_pdf(text)
    up = client.post("/documents", headers=headers, files={"file": ("retry.pdf", pdf, "application/pdf")})
    doc_id = up.json()["id"]

    first = client.post(f"/documents/{doc_id}/extract", headers=headers)
    second = client.post(f"/documents/{doc_id}/extract", headers=headers)

    assert first.status_code == 422
    assert second.status_code == 200
    assert second.json()["extraction_status"] == "done"
    assert client.get("/documents", headers=headers).json()[0]["extraction_status"] == "done"
