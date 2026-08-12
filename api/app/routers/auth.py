from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    email: EmailStr | None = None


class SigninRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    description: str | None = None
    avatar_url: str | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    full_name: str | None = None
    email: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    existing = await db.scalar(select(User).where(User.username == body.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário já existe")

    if body.email:
        email_exists = await db.scalar(select(User).where(User.email == body.email))
        if email_exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já cadastrado")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        email=body.email,
    )
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


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """B2 — Edição de perfil: nome, email, descrição e avatar (RF-001/RF-006)."""
    if body.email and body.email != current_user.email:
        email_exists = await db.scalar(
            select(User).where(User.email == body.email, User.id != current_user.id)
        )
        if email_exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já cadastrado")

    # Atualiza apenas os campos enviados (None = não alterar)
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.email is not None:
        current_user.email = body.email
    if body.description is not None:
        current_user.description = body.description
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url

    await db.commit()
    await db.refresh(current_user)
    return current_user

