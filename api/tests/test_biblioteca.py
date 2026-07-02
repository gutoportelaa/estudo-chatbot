"""Testes do backend da Biblioteca: capa, exclusão, ordenação, escopo de sessão."""

from __future__ import annotations

import os

import pytest

from app.config import get_settings
from app.storage import get_storage

fitz = pytest.importorskip("fitz")


def _pdf(text: str = "Documento de teste da biblioteca") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


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


def _auth(client, username="lib_user", password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    r = client.post("/auth/signin", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(client, headers, name="a.pdf", text="conteúdo"):
    return client.post("/documents", headers=headers, files={"file": (name, _pdf(text), "application/pdf")})


def test_upload_generates_cover_thumbnail(client, storage_tmp):
    headers = _auth(client)
    up = _upload(client, headers)
    assert up.status_code == 201
    assert up.json()["has_thumbnail"] is True

    doc_id = up.json()["id"]
    thumb = client.get(f"/documents/{doc_id}/thumbnail", headers=headers)
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/png"
    assert thumb.content[:8] == b"\x89PNG\r\n\x1a\n"  # assinatura PNG


def test_delete_document_removes_it(client, storage_tmp):
    headers = _auth(client)
    doc_id = _upload(client, headers).json()["id"]

    assert client.delete(f"/documents/{doc_id}", headers=headers).status_code == 204
    assert client.get("/documents", headers=headers).json() == []
    assert client.get(f"/documents/{doc_id}/thumbnail", headers=headers).status_code == 404


def test_list_sort_by_name(client, storage_tmp):
    headers = _auth(client)
    _upload(client, headers, name="zebra.pdf")
    _upload(client, headers, name="alpha.pdf")
    names = [d["filename"] for d in client.get("/documents?sort=name", headers=headers).json()]
    assert names == ["alpha.pdf", "zebra.pdf"]


def test_cannot_access_other_users_thumbnail(client, storage_tmp):
    a = _auth(client, username="alice_lib")
    doc_id = _upload(client, a).json()["id"]
    b = _auth(client, username="bob_lib")
    assert client.get(f"/documents/{doc_id}/thumbnail", headers=b).status_code == 404
    assert client.delete(f"/documents/{doc_id}", headers=b).status_code == 404


def test_create_session_scoped_to_documents(client, storage_tmp):
    headers = _auth(client)
    d1 = _upload(client, headers, name="d1.pdf").json()["id"]
    d2 = _upload(client, headers, name="d2.pdf").json()["id"]

    r = client.post("/sessions", headers=headers, json={"document_ids": [d1, d2]})
    assert r.status_code == 201
    assert set(r.json()["document_ids"]) == {d1, d2}


def test_create_session_rejects_foreign_document(client, storage_tmp):
    a = _auth(client, username="alice_s")
    foreign = _upload(client, a, name="secret.pdf").json()["id"]
    b = _auth(client, username="bob_s")
    r = client.post("/sessions", headers=b, json={"document_ids": [foreign]})
    assert r.status_code == 404


def test_create_session_without_documents_still_works(client, storage_tmp):
    headers = _auth(client)
    r = client.post("/sessions", headers=headers)
    assert r.status_code == 201
    assert r.json()["document_ids"] == []
