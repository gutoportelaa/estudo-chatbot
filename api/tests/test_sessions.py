import os

import pytest

from app.config import get_settings
from app.storage import get_storage


PDF_BYTES = b"%PDF-1.4\n%%EOF\n"


@pytest.fixture
def storage_tmp(tmp_path):
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


def _auth_headers(client, username="lucas_sessions", password="123456"):
    client.post(
        "/auth/signup",
        json={"username": username, "password": password},
    )

    response = client.post(
        "/auth/signin",
        json={"username": username, "password": password},
    )

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _upload_pdf(client, headers, name="a.pdf"):
    return client.post(
        "/documents",
        headers=headers,
        files={"file": (name, PDF_BYTES, "application/pdf")},
    )


def _mock_openai_response(monkeypatch, text="Resposta persistida"):
    from app.config import Settings

    class _Stream:
        async def __aiter__(self):
            delta = type("Delta", (), {"content": text})()
            choice = type("Choice", (), {"delta": delta})()
            yield type("Chunk", (), {"choices": [choice]})()

    class _Completions:
        async def create(self, **kwargs):
            return _Stream()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        chat = _Chat()

        def __init__(self, **kwargs):
            pass

    settings = Settings(
        llm_provider="ollama",
        ollama_model="modelo-teste",
        web_search_heuristic=False,
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.llm.get_settings", lambda: settings)
    monkeypatch.setattr("app.llm.AsyncOpenAI", _FakeOpenAI)


def test_create_session_retorna_201(client):
    headers = _auth_headers(client)

    response = client.post("/sessions", headers=headers)

    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert "title" in data


def test_list_sessions_usuario_sem_sessoes_retorna_lista_vazia(client):
    headers = _auth_headers(client)

    response = client.get("/sessions", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_list_sessions_retorna_sessao_criada(client):
    headers = _auth_headers(client)

    created = client.post("/sessions", headers=headers).json()

    response = client.get("/sessions", headers=headers)

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == created["id"]


def test_get_messages_sessao_inexistente_retorna_404(client):
    headers = _auth_headers(client)

    response = client.get(
        "/sessions/sessao-inexistente/messages",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sessão não encontrada"


def test_rename_session_atualiza_titulo_com_strip(client):
    headers = _auth_headers(client)

    session = client.post("/sessions", headers=headers).json()

    response = client.patch(
        f"/sessions/{session['id']}",
        headers=headers,
        json={"title": "   Minha conversa   "},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == session["id"]
    assert data["title"] == "Minha conversa"


def test_delete_session_inexistente_retorna_404(client):
    headers = _auth_headers(client)

    response = client.delete(
        "/sessions/sessao-inexistente",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sessão não encontrada"

def test_delete_session_existente_remove_da_listagem_e_bloqueia_acesso(client):
    headers = _auth_headers(client, username="user_delete_session")
    session = client.post("/sessions", headers=headers).json()

    response = client.delete(f"/sessions/{session['id']}", headers=headers)

    assert response.status_code == 204
    assert client.get("/sessions", headers=headers).json() == []

    messages = client.get(f"/sessions/{session['id']}/messages", headers=headers)
    assert messages.status_code == 404
    assert messages.json()["detail"] == "Sessão não encontrada"


def test_delete_session_nao_remove_sessao_de_outro_usuario(client):
    owner = _auth_headers(client, username="session_owner")
    intruder = _auth_headers(client, username="session_intruder")
    session = client.post("/sessions", headers=owner).json()

    response = client.delete(f"/sessions/{session['id']}", headers=intruder)

    assert response.status_code == 404
    owner_sessions = client.get("/sessions", headers=owner).json()
    assert [s["id"] for s in owner_sessions] == [session["id"]]


def test_usuario_nao_acessa_mensagens_de_outro_usuario(client):
    headers_user_1 = _auth_headers(client, username="user1")
    headers_user_2 = _auth_headers(client, username="user2")

    session = client.post("/sessions", headers=headers_user_1).json()

    response = client.get(
        f"/sessions/{session['id']}/messages",
        headers=headers_user_2,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sessão não encontrada"


def test_usuario_nao_renomeia_sessao_de_outro_usuario(client):
    headers_user_1 = _auth_headers(client, username="user3")
    headers_user_2 = _auth_headers(client, username="user4")

    session = client.post("/sessions", headers=headers_user_1).json()

    response = client.patch(
        f"/sessions/{session['id']}",
        headers=headers_user_2,
        json={"title": "Tentativa indevida"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sessão não encontrada"

def test_detach_document_from_session(client, storage_tmp):
    headers = _auth_headers(client, username="detach_doc_user")
    session = client.post("/sessions", headers=headers).json()
    d1 = _upload_pdf(client, headers, name="d1.pdf").json()["id"]
    d2 = _upload_pdf(client, headers, name="d2.pdf").json()["id"]

    attached = client.post(
        f"/sessions/{session['id']}/documents",
        headers=headers,
        json={"document_ids": [d1, d2]},
    )
    assert set(attached.json()["document_ids"]) == {d1, d2}

    response = client.delete(f"/sessions/{session['id']}/documents/{d1}", headers=headers)

    assert response.status_code == 200
    assert response.json()["document_ids"] == [d2]
    assert client.get(f"/sessions/{session['id']}/documents", headers=headers).json()["document_ids"] == [d2]


def test_send_message_retorna_stream_com_resposta_mockada(client, monkeypatch):
    async def fake_stream_adk(user_id: str, session_id: str, content: str):
        yield "data: Olá, Lucas!\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(
        "app.routers.chat._stream_adk",
        fake_stream_adk,
    )
    # Força o caminho ADK independentemente do provedor no .env (senão o roteador
    # escolhe o caminho OpenAI-compat e o mock de _stream_adk é ignorado).
    class _Settings:
        llm_provider = "gemini"

    monkeypatch.setattr("app.config.get_settings", lambda: _Settings())

    headers = _auth_headers(client, username="user_chat")
    session = client.post("/sessions", headers=headers).json()

    response = client.post(
        f"/sessions/{session['id']}/messages",
        headers=headers,
        json={"content": "Olá"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    body = response.text
    assert "data: Olá, Lucas!" in body
    assert "data: [DONE]" in body

def test_send_message_persiste_historico_da_conversa(client, monkeypatch):
    from app.config import Settings

    class _Delta:
        content = "Resposta persistida"

    class _Choice:
        delta = _Delta()

    class _Chunk:
        choices = [_Choice()]

    class _Stream:
        async def __aiter__(self):
            yield _Chunk()

    class _Completions:
        async def create(self, **kwargs):
            return _Stream()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        chat = _Chat()

        def __init__(self, **kwargs):
            pass

    settings = Settings(
        llm_provider="ollama",
        ollama_model="modelo-teste",
        web_search_heuristic=False,
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.llm.get_settings", lambda: settings)
    monkeypatch.setattr("app.llm.AsyncOpenAI", _FakeOpenAI)

    headers = _auth_headers(client, username="user_chat_persist")
    session = client.post("/sessions", headers=headers).json()

    response = client.post(
        f"/sessions/{session['id']}/messages",
        headers=headers,
        json={"content": "Mensagem persistida"},
    )

    assert response.status_code == 200
    assert "Resposta persistida" in response.text
    assert "data: [DONE]" in response.text

    messages = client.get(f"/sessions/{session['id']}/messages", headers=headers).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Mensagem persistida"
    assert messages[1]["content"] == "Resposta persistida"


def test_send_message_atualiza_titulo_da_sessao(client, monkeypatch):
    _mock_openai_response(monkeypatch, text="Resposta para titulo")

    headers = _auth_headers(client, username="user_chat_title")
    session = client.post("/sessions", headers=headers).json()

    response = client.post(
        f"/sessions/{session['id']}/messages",
        headers=headers,
        json={"content": "Primeira pergunta para titulo"},
    )

    assert response.status_code == 200
    sessions = client.get("/sessions", headers=headers).json()
    assert sessions[0]["id"] == session["id"]
    assert sessions[0]["title"] == "Primeira pergunta para titulo"


def test_send_message_sessao_inexistente_retorna_404(client):
    headers = _auth_headers(client, username="user_chat_404")

    response = client.post(
        "/sessions/sessao-inexistente/messages",
        headers=headers,
        json={"content": "Olá"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sessão não encontrada"
