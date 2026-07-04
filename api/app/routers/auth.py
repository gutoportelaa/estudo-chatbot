from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str
    password: str


class SigninRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UpdateProfileRequest(BaseModel):
    username: str | None = None
    password: str | None = None


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    existing = await db.scalar(select(User).where(User.username == body.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário já existe")

    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/signin", response_model=TokenResponse)
async def signin(
    body: SigninRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await db.scalar(select(User).where(User.username == body.username))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": create_access_token(user.id)}


@router.get("/profile", response_model=UserResponse)
async def profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Edição mínima de perfil (EPIC E): trocar username e/ou senha."""
    if body.username is None and body.password is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe username e/ou password")

    if body.username is not None:
        username = body.username.strip()
        if not username:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username não pode ser vazio")
        if username != current_user.username:
            existing = await db.scalar(select(User).where(User.username == username))
            if existing:
                raise HTTPException(status.HTTP_409_CONFLICT, "Usuário já existe")
            current_user.username = username

    if body.password is not None:
        if len(body.password) < 8:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Senha deve ter ao menos 8 caracteres"
            )
        current_user.password_hash = hash_password(body.password)

    await db.commit()
    await db.refresh(current_user)
    return current_user
