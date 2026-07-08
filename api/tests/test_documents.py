"""Testes de upload/listagem de documentos (C1, RF-002) — backend local, sem AWS."""

import os

import pytest

from app.config import get_settings
from app.storage import get_storage

# PDF mínimo: a validação checa apenas os magic bytes "%PDF-".
PDF_BYTES = b"%PDF-1.4\n%%EOF\n"


@pytest.fixture
def storage_tmp(tmp_path):
    """Aponta o storage para um diretório temporário e limita o upload a 1 MB."""
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_DIR"] = str(tmp_path / "docs")
    os.environ["MAX_UPLOAD_MB"] = "1"
    get_settings.cache_clear()
    get_storage.cache_clear()
    yield
    for var in ("STORAGE_BACKEND", "STORAGE_DIR", "MAX_UPLOAD_MB"):
        os.environ.pop(var, None)
    get_settings.cache_clear()
    get_storage.cache_clear()


def _auth_headers(client, username="docs_user", password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    r = client.post("/auth/signin", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(client, headers, name="a.pdf", content=PDF_BYTES, ctype="application/pdf"):
    return client.post("/documents", headers=headers, files={"file": (name, content, ctype)})


def test_upload_pdf_valido_retorna_201(client, storage_tmp):
    headers = _auth_headers(client)
    r = _upload(client, headers)
    assert r.status_code == 201
    body = r.json()
    assert body["filename"] == "a.pdf"
    assert body["size_bytes"] == len(PDF_BYTES)
    assert "id" in body


def test_rejeita_extensao_nao_pdf(client, storage_tmp):
    headers = _auth_headers(client)
    r = _upload(client, headers, name="a.txt")
    assert r.status_code == 400


def test_rejeita_magic_bytes_invalidos(client, storage_tmp):
    headers = _auth_headers(client)
    r = _upload(client, headers, content=b"isto nao e um pdf")
    assert r.status_code == 400


def test_rejeita_acima_do_limite(client, storage_tmp):
    headers = _auth_headers(client)
    grande = PDF_BYTES + b"0" * (1 * 1024 * 1024 + 10)  # > 1 MB
    r = _upload(client, headers, content=grande)
    assert r.status_code == 413


def test_exige_autenticacao(client, storage_tmp):
    r = _upload(client, headers={})
    assert r.status_code in (401, 403)


def test_lista_apenas_documentos_do_usuario(client, storage_tmp):
    h1 = _auth_headers(client, username="alice")
    h2 = _auth_headers(client, username="bob")
    _upload(client, h1, name="alice.pdf")

    assert len(client.get("/documents", headers=h1).json()) == 1
    assert client.get("/documents", headers=h2).json() == []


def test_index_document_rejeita_documento_nao_extraido(client, storage_tmp):
    headers = _auth_headers(client, username="index_not_extracted")
    doc_id = _upload(client, headers, name="material.pdf").json()["id"]

    response = client.post(f"/documents/{doc_id}/index", headers=headers)

    assert response.status_code == 409
    assert "ainda" in response.json()["detail"]
