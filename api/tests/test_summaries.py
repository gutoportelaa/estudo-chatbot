from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Document
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


@pytest.fixture
def enqueue_mock(monkeypatch):
    calls: list[str] = []

    async def _fake_enqueue(summary_id: str) -> None:
        calls.append(summary_id)

    monkeypatch.setattr("app.routers.summaries.enqueue_summary", _fake_enqueue)
    return calls


def _auth(client, username="summary_user", password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    signin = client.post("/auth/signin", json={"username": username, "password": password}).json()
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    user = client.get("/auth/profile", headers=headers).json()
    return headers, user["id"]


def _seed_document(user_id: str, *, filename="material.pdf", ready=True) -> str:
    storage = get_storage()
    suffix = uuid.uuid4().hex
    pdf_key = f"{user_id}/{suffix}.pdf"
    text_key = f"{user_id}/{suffix}.txt"
    storage.save(pdf_key, b"%PDF-1.4\n%%EOF\n")
    if ready:
        storage.save(text_key, b"Texto extraido para gerar resumo.")

    async def _go():
        async with AsyncSessionLocal() as db:
            doc = Document(
                user_id=user_id,
                filename=filename,
                size_bytes=16,
                content_type="application/pdf",
                storage_backend="local",
                storage_key=pdf_key,
                page_count=1 if ready else None,
                extraction_status="done" if ready else "pending",
                extracted_key=text_key if ready else None,
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            return doc.id

    return asyncio.run(_go())


def test_create_summary_requires_auth(client):
    response = client.post("/summaries", json={"document_ids": ["doc-1"]})

    assert response.status_code in (401, 403)


def test_create_summary_rejects_empty_document_list(client, storage_tmp, enqueue_mock):
    headers, _ = _auth(client, username="summary_empty")

    response = client.post("/summaries", headers=headers, json={"document_ids": []})

    assert response.status_code == 400
    assert enqueue_mock == []


def test_create_summary_with_ready_document_returns_pending(client, storage_tmp, enqueue_mock):
    headers, user_id = _auth(client, username="summary_create")
    doc_id = _seed_document(user_id, filename="biologia.pdf")

    response = client.post("/summaries", headers=headers, json={"document_ids": [doc_id]})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["document_ids"] == [doc_id]
    assert body["title"] is None
    assert body["content"] is None
    assert enqueue_mock == [body["id"]]


def test_create_summary_marks_failed_when_queue_is_unavailable(client, storage_tmp, monkeypatch):
    async def _fail_enqueue(summary_id: str) -> None:
        raise RuntimeError("redis indisponivel")

    monkeypatch.setattr("app.routers.summaries.enqueue_summary", _fail_enqueue)
    headers, user_id = _auth(client, username="summary_queue_down")
    doc_id = _seed_document(user_id, filename="fila.pdf")

    response = client.post("/summaries", headers=headers, json={"document_ids": [doc_id]})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"]


def test_create_summary_rejects_foreign_document(client, storage_tmp, enqueue_mock):
    _, owner_id = _auth(client, username="summary_owner")
    foreign_doc = _seed_document(owner_id, filename="privado.pdf")
    intruder_headers, _ = _auth(client, username="summary_intruder")

    response = client.post(
        "/summaries",
        headers=intruder_headers,
        json={"document_ids": [foreign_doc]},
    )

    assert response.status_code == 404
    assert enqueue_mock == []


def test_create_summary_requires_extracted_document(client, storage_tmp, enqueue_mock):
    headers, user_id = _auth(client, username="summary_not_ready")
    doc_id = _seed_document(user_id, filename="pendente.pdf", ready=False)

    response = client.post("/summaries", headers=headers, json={"document_ids": [doc_id]})

    assert response.status_code == 409
    assert "Extraia" in response.json()["detail"]
    assert enqueue_mock == []


def test_list_summaries_returns_only_current_user(client, storage_tmp, enqueue_mock):
    alice_headers, alice_id = _auth(client, username="summary_alice")
    bob_headers, bob_id = _auth(client, username="summary_bob")
    alice_doc = _seed_document(alice_id, filename="alice.pdf")
    bob_doc = _seed_document(bob_id, filename="bob.pdf")

    alice_summary = client.post(
        "/summaries",
        headers=alice_headers,
        json={"document_ids": [alice_doc]},
    ).json()
    client.post("/summaries", headers=bob_headers, json={"document_ids": [bob_doc]})

    response = client.get("/summaries", headers=alice_headers)

    assert response.status_code == 200
    summaries = response.json()
    assert len(summaries) == 1
    assert summaries[0]["id"] == alice_summary["id"]
    assert summaries[0]["document_ids"] == [alice_doc]


def test_summary_detail_includes_documents_and_blocks_other_users(client, storage_tmp, enqueue_mock):
    owner_headers, owner_id = _auth(client, username="summary_detail_owner")
    doc_id = _seed_document(owner_id, filename="detalhe.pdf")
    summary = client.post(
        "/summaries",
        headers=owner_headers,
        json={"document_ids": [doc_id]},
    ).json()
    intruder_headers, _ = _auth(client, username="summary_detail_intruder")

    detail = client.get(f"/summaries/{summary['id']}", headers=owner_headers)
    blocked = client.get(f"/summaries/{summary['id']}", headers=intruder_headers)

    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == summary["id"]
    assert body["documents"] == [{"id": doc_id, "filename": "detalhe.pdf"}]
    assert blocked.status_code == 404


def test_poll_summaries_returns_only_current_user(client, storage_tmp, enqueue_mock):
    alice_headers, alice_id = _auth(client, username="summary_poll_alice")
    bob_headers, bob_id = _auth(client, username="summary_poll_bob")
    alice_doc = _seed_document(alice_id, filename="alice-poll.pdf")
    bob_doc = _seed_document(bob_id, filename="bob-poll.pdf")
    alice_summary = client.post(
        "/summaries",
        headers=alice_headers,
        json={"document_ids": [alice_doc]},
    ).json()
    bob_summary = client.post(
        "/summaries",
        headers=bob_headers,
        json={"document_ids": [bob_doc]},
    ).json()

    response = client.post(
        "/summaries/status",
        headers=alice_headers,
        json={"ids": [alice_summary["id"], bob_summary["id"]]},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": alice_summary["id"],
            "status": "pending",
            "error": None,
            "title": None,
        }
    ]


def test_delete_summary_removes_only_owned_summary(client, storage_tmp, enqueue_mock):
    owner_headers, owner_id = _auth(client, username="summary_delete_owner")
    intruder_headers, _ = _auth(client, username="summary_delete_intruder")
    doc_id = _seed_document(owner_id, filename="delete.pdf")
    summary = client.post(
        "/summaries",
        headers=owner_headers,
        json={"document_ids": [doc_id]},
    ).json()

    blocked = client.delete(f"/summaries/{summary['id']}", headers=intruder_headers)
    deleted = client.delete(f"/summaries/{summary['id']}", headers=owner_headers)
    after = client.get("/summaries", headers=owner_headers)

    assert blocked.status_code == 404
    assert deleted.status_code == 204
    assert after.json() == []


def test_delete_summary_inexistente_retorna_404(client, storage_tmp, enqueue_mock):
    headers, _ = _auth(client, username="summary_delete_missing")

    response = client.delete("/summaries/summary-inexistente", headers=headers)

    assert response.status_code == 404
