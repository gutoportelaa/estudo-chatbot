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

def test_send_message_sessao_inexistente_retorna_404(client):
    headers = _auth_headers(client, username="user_chat_404")

    response = client.post(
        "/sessions/sessao-inexistente/messages",
        headers=headers,
        json={"content": "Olá"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Sessão não encontrada"