from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..storage import get_storage

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
    full_name: str | None = None
    email: str | None = None
    description: str | None = None
    has_avatar: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @staticmethod
    def of(user: User) -> "UserResponse":
        return UserResponse(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            description=user.description,
            has_avatar=user.avatar_key is not None,
            created_at=user.created_at,
        )


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    description: str | None = None


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

    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.of(user)


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
) -> UserResponse:
    return UserResponse.of(current_user)


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Edita os campos de perfil (B2/#40). Só altera o que vier no corpo."""
    data = body.model_dump(exclude_unset=True)
    for field in ("full_name", "email", "description"):
        if field in data:
            value = data[field]
            setattr(current_user, field, (value or None) if isinstance(value, str) else value)
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.of(current_user)


_AVATAR_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_AVATAR_MAX_BYTES = 2 * 1024 * 1024


@router.post("/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Envia/atualiza o avatar do usuário (B2/#40)."""
    ext = _AVATAR_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Avatar deve ser PNG, JPEG ou WEBP")
    data = await file.read()
    if len(data) > _AVATAR_MAX_BYTES:
        raise HTTPException(413, "Avatar excede 2 MB")

    storage = get_storage()
    key = f"{current_user.id}/avatar{ext}"
    await run_in_threadpool(storage.save, key, data)
    # Remove um avatar anterior de extensão diferente, se houver.
    if current_user.avatar_key and current_user.avatar_key != key:
        try:
            await run_in_threadpool(storage.delete, current_user.avatar_key)
        except Exception:  # pragma: no cover - best-effort
            pass
    current_user.avatar_key = key
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.of(current_user)


@router.get("/avatar")
async def get_avatar(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Devolve o avatar do usuário autenticado (404 se não houver)."""
    if not current_user.avatar_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sem avatar")
    data = await run_in_threadpool(get_storage().load, current_user.avatar_key)
    media = "image/png"
    if current_user.avatar_key.endswith(".jpg"):
        media = "image/jpeg"
    elif current_user.avatar_key.endswith(".webp"):
        media = "image/webp"
    return Response(content=data, media_type=media, headers={"Cache-Control": "private, max-age=300"})
