import os

import pytest

from app.config import get_settings
from app.storage import get_storage


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"


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


def _auth_headers(client, username, password="123456"):
    client.post("/auth/signup", json={"username": username, "password": password})
    signin = client.post("/auth/signin", json={"username": username, "password": password}).json()
    return {"Authorization": f"Bearer {signin['access_token']}"}


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


def test_profile_com_token_valido_retorna_usuario_publico(client):
    payload = {
        "username": "lucas_auth_profile",
        "password": "123456",
    }
    client.post("/auth/signup", json=payload)
    signin = client.post("/auth/signin", json=payload).json()

    response = client.get(
        "/auth/profile",
        headers={"Authorization": f"Bearer {signin['access_token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "lucas_auth_profile"
    assert "id" in data
    assert "created_at" in data
    assert data["full_name"] is None
    assert data["email"] is None
    assert data["description"] is None
    assert data["has_avatar"] is False
    assert "password" not in data
    assert "password_hash" not in data


def test_update_profile_persiste_campos_publicos(client):
    payload = {
        "username": "lucas_auth_update",
        "password": "123456",
    }
    client.post("/auth/signup", json=payload)
    signin = client.post("/auth/signin", json=payload).json()
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    response = client.patch(
        "/auth/profile",
        headers=headers,
        json={
            "full_name": "Lucas Silva",
            "email": "lucas@example.com",
            "description": "Estudante de computacao",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Lucas Silva"
    assert data["email"] == "lucas@example.com"
    assert data["description"] == "Estudante de computacao"

    profile = client.get("/auth/profile", headers=headers).json()
    assert profile["full_name"] == "Lucas Silva"
    assert profile["email"] == "lucas@example.com"
    assert profile["description"] == "Estudante de computacao"


def test_update_profile_normaliza_strings_vazias_para_null(client):
    payload = {
        "username": "lucas_auth_clear",
        "password": "123456",
    }
    client.post("/auth/signup", json=payload)
    signin = client.post("/auth/signin", json=payload).json()
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    client.patch(
        "/auth/profile",
        headers=headers,
        json={
            "full_name": "Lucas Silva",
            "email": "lucas@example.com",
            "description": "Descricao temporaria",
        },
    )
    response = client.patch(
        "/auth/profile",
        headers=headers,
        json={"full_name": "", "email": "", "description": ""},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] is None
    assert data["email"] is None
    assert data["description"] is None


def test_avatar_rejeita_tipo_invalido(client):
    payload = {
        "username": "lucas_auth_avatar",
        "password": "123456",
    }
    client.post("/auth/signup", json=payload)
    signin = client.post("/auth/signin", json=payload).json()

    response = client.post(
        "/auth/avatar",
        headers={"Authorization": f"Bearer {signin['access_token']}"},
        files={"file": ("avatar.txt", b"nao e imagem", "text/plain")},
    )

    assert response.status_code == 400


def test_avatar_upload_valido_e_get_avatar(client, storage_tmp):
    headers = _auth_headers(client, "lucas_auth_avatar_ok")

    upload = client.post(
        "/auth/avatar",
        headers=headers,
        files={"file": ("avatar.png", PNG_BYTES, "image/png")},
    )

    assert upload.status_code == 200
    assert upload.json()["has_avatar"] is True

    avatar = client.get("/auth/avatar", headers=headers)
    assert avatar.status_code == 200
    assert avatar.headers["content-type"] == "image/png"
    assert avatar.content == PNG_BYTES


def test_get_avatar_sem_avatar_retorna_404(client):
    headers = _auth_headers(client, "lucas_auth_no_avatar")

    response = client.get("/auth/avatar", headers=headers)

    assert response.status_code == 404
