def test_signup_cria_usuario(client):
    response = client.post(
        "/auth/signup",
        json={
            "username": "lucas_auth_1",
            "password": "123456",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["username"] == "lucas_auth_1"
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_signup_usuario_duplicado_retorna_409(client):
    payload = {
        "username": "lucas_auth_2",
        "password": "123456",
    }

    client.post("/auth/signup", json=payload)

    response = client.post("/auth/signup", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Usuário já existe"


def test_signin_com_credenciais_validas_retorna_token(client):
    payload = {
        "username": "lucas_auth_3",
        "password": "123456",
    }

    client.post("/auth/signup", json=payload)

    response = client.post("/auth/signin", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_signin_com_senha_incorreta_retorna_401(client):
    client.post(
        "/auth/signup",
        json={
            "username": "lucas_auth_4",
            "password": "123456",
        },
    )

    response = client.post(
        "/auth/signin",
        json={
            "username": "lucas_auth_4",
            "password": "senha_errada",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Usuário ou senha inválidos"


def test_profile_sem_token_retorna_401(client):
    response = client.get("/auth/profile")

    assert response.status_code == 401


def _signup_and_login(client, username, password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    token = client.post(
        "/auth/signin", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_update_profile_troca_username(client):
    headers = _signup_and_login(client, "profile_user_1")

    response = client.patch(
        "/auth/profile", json={"username": "profile_user_1_novo"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["username"] == "profile_user_1_novo"


def test_update_profile_username_duplicado_retorna_409(client):
    _signup_and_login(client, "profile_user_2a")
    headers_b = _signup_and_login(client, "profile_user_2b")

    response = client.patch(
        "/auth/profile", json={"username": "profile_user_2a"}, headers=headers_b
    )

    assert response.status_code == 409


def test_update_profile_troca_senha(client):
    headers = _signup_and_login(client, "profile_user_3", password="senha_antiga")

    response = client.patch(
        "/auth/profile", json={"password": "senha_nova_123"}, headers=headers
    )
    assert response.status_code == 200

    # Login com a senha antiga falha; com a nova, funciona.
    old = client.post(
        "/auth/signin", json={"username": "profile_user_3", "password": "senha_antiga"}
    )
    assert old.status_code == 401

    new = client.post(
        "/auth/signin", json={"username": "profile_user_3", "password": "senha_nova_123"}
    )
    assert new.status_code == 200


def test_update_profile_sem_token_retorna_401(client):
    response = client.patch("/auth/profile", json={"username": "x"})
    assert response.status_code == 401


def test_update_profile_sem_campos_retorna_400(client):
    headers = _signup_and_login(client, "profile_user_4")

    response = client.patch("/auth/profile", json={}, headers=headers)

    assert response.status_code == 400