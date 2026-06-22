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