"""Testes de resumo de documentos — individual e consolidado (issues #44/#45, EPIC C).

Espelha o padrão de `test_documents.py`/`test_extraction.py` (PDFs reais via
PyMuPDF, storage local em diretório temporário). O client LLM é stubado (via
`resolve_client`) para não depender de rede — o que se testa aqui é o fluxo
(posse dos documentos, exigência de extração prévia, kind inferido, listagem),
não a qualidade do texto gerado pelo modelo.
"""

from __future__ import annotations

import os

import pytest

from app.config import get_settings
from app.storage import get_storage

fitz = pytest.importorskip("fitz")


def _pdf(text: str) -> bytes:
    """Insere o texto em várias linhas — `insert_text` não quebra linha sozinho,
    então uma única linha longa fica truncada pela largura da página."""
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for i in range(0, len(text), 60):
        page.insert_text((72, y), text[i : i + 60], fontsize=12)
        y += 16
    data = doc.tobytes()
    doc.close()
    return data


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


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, content: str = "Resumo gerado pelo LLM de teste.") -> None:
        self.chat = _FakeChat(_FakeCompletions(content))


@pytest.fixture(autouse=True)
def _stub_resolve_client(monkeypatch):
    monkeypatch.setattr(
        "app.routers.summaries.resolve_client",
        lambda settings: (_FakeClient(), "fake-model", "fake-provider"),
    )


def _auth(client, username="summary_user", password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    r = client.post("/auth/signin", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload_and_extract(client, headers, text, name="doc.pdf"):
    # Repete o texto até ficar bem acima do limiar de "PDF escaneado"
    # (extraction_ocr_min_chars_per_page, padrão 100 chars/página) — evita
    # depender de um binário de OCR (tesseract) instalado no ambiente de teste.
    padded = text
    while len(padded) < 200:
        padded += " " + text
    up = client.post(
        "/documents", headers=headers, files={"file": (name, _pdf(padded), "application/pdf")}
    )
    doc_id = up.json()["id"]
    r = client.post(f"/documents/{doc_id}/extract", headers=headers)
    assert r.status_code == 200, r.text
    return doc_id


def test_create_summary_single_documento(client, storage_tmp):
    headers = _auth(client)
    doc_id = _upload_and_extract(client, headers, "Fotossíntese é o processo das plantas.")

    r = client.post("/summaries", headers=headers, json={"document_ids": [doc_id]})

    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "single"
    assert body["document_ids"] == [doc_id]
    assert body["content"]
    assert body["llm_model"] == "fake-model"


def test_create_summary_consolidado_com_dois_documentos(client, storage_tmp):
    headers = _auth(client)
    doc1 = _upload_and_extract(client, headers, "Texto do primeiro documento.", name="a.pdf")
    doc2 = _upload_and_extract(client, headers, "Texto do segundo documento.", name="b.pdf")

    r = client.post("/summaries", headers=headers, json={"document_ids": [doc1, doc2]})

    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "consolidated"
    assert set(body["document_ids"]) == {doc1, doc2}


def test_create_summary_documento_nao_extraido_retorna_409(client, storage_tmp):
    headers = _auth(client)
    up = client.post(
        "/documents", headers=headers, files={"file": ("a.pdf", _pdf("texto"), "application/pdf")}
    )
    doc_id = up.json()["id"]  # sem chamar /extract

    r = client.post("/summaries", headers=headers, json={"document_ids": [doc_id]})

    assert r.status_code == 409


def test_create_summary_documento_de_outro_usuario_retorna_404(client, storage_tmp):
    a = _auth(client, username="alice_sum")
    doc_id = _upload_and_extract(client, a, "Texto de alice.")

    b = _auth(client, username="bob_sum")
    r = client.post("/summaries", headers=b, json={"document_ids": [doc_id]})

    assert r.status_code == 404


def test_create_summary_sem_documentos_retorna_400(client, storage_tmp):
    headers = _auth(client)
    r = client.post("/summaries", headers=headers, json={"document_ids": []})
    assert r.status_code == 400


def test_create_summary_falha_do_llm_retorna_502(client, storage_tmp, monkeypatch):
    class _BoomCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("LLM indisponível")

    class _BoomChat:
        def __init__(self):
            self.completions = _BoomCompletions()

    class _BoomClient:
        def __init__(self):
            self.chat = _BoomChat()

    monkeypatch.setattr(
        "app.routers.summaries.resolve_client",
        lambda settings: (_BoomClient(), "fake-model", "fake-provider"),
    )

    headers = _auth(client, username="summary_llm_boom")
    doc_id = _upload_and_extract(client, headers, "Texto qualquer para o teste de falha do LLM.")

    r = client.post("/summaries", headers=headers, json={"document_ids": [doc_id]})

    assert r.status_code == 502


def test_list_summaries_filtra_por_usuario_e_kind(client, storage_tmp):
    headers = _auth(client, username="lister")
    doc1 = _upload_and_extract(client, headers, "Doc um.", name="a.pdf")
    doc2 = _upload_and_extract(client, headers, "Doc dois.", name="b.pdf")
    client.post("/summaries", headers=headers, json={"document_ids": [doc1]})
    client.post("/summaries", headers=headers, json={"document_ids": [doc1, doc2]})

    all_summaries = client.get("/summaries", headers=headers).json()
    assert len(all_summaries) == 2

    singles = client.get("/summaries?kind=single", headers=headers).json()
    assert len(singles) == 1
    assert singles[0]["kind"] == "single"

    other = _auth(client, username="lister2")
    assert client.get("/summaries", headers=other).json() == []


def test_get_summary_de_outro_usuario_retorna_404(client, storage_tmp):
    a = _auth(client, username="alice_get")
    doc_id = _upload_and_extract(client, a, "Texto.")
    summary_id = client.post(
        "/summaries", headers=a, json={"document_ids": [doc_id]}
    ).json()["id"]

    b = _auth(client, username="bob_get")
    r = client.get(f"/summaries/{summary_id}", headers=b)
    assert r.status_code == 404


def test_get_summary_inexistente_retorna_404(client, storage_tmp):
    headers = _auth(client)
    r = client.get("/summaries/nao-existe", headers=headers)
    assert r.status_code == 404
