"""Abstração de armazenamento de binários (PDFs).

Dois backends selecionados por configuração (`storage_backend`):

- **local** — filesystem; ideal para desenvolvimento/testes (sem AWS).
- **s3** — produção; suporta *presigned URLs* (upload do browser direto p/ o S3,
  sem o binário passar pela API).

O banco guarda só a referência (`storage_backend` + `storage_key`); o binário
vive aqui.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from .config import get_settings


def build_key(user_id: str, filename: str) -> str:
    """Gera uma chave única e isolada por usuário: ``<user_id>/<uuid>.pdf``."""
    ext = Path(filename).suffix.lower() or ".pdf"
    return f"{user_id}/{uuid.uuid4().hex}{ext}"


class StorageBackend(ABC):
    """Contrato de armazenamento. Métodos síncronos — o router os executa em
    threadpool para não bloquear o event loop."""

    name: str = "base"
    supports_presign: bool = False

    @abstractmethod
    def save(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def load(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    def presigned_put_url(self, key: str, content_type: str) -> str:
        raise NotImplementedError("Backend não suporta presigned URLs")

    def presigned_get_url(self, key: str) -> str:
        raise NotImplementedError("Backend não suporta presigned URLs")


class LocalStorage(StorageBackend):
    name = "local"
    supports_presign = False

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        # Resolve e garante que a chave não escapa do diretório-raiz.
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("chave de armazenamento inválida")
        return p

    def save(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage(StorageBackend):
    name = "s3"
    supports_presign = True

    def __init__(self, bucket: str, region: str, expire_seconds: int) -> None:
        import boto3  # import tardio: só carrega se o backend s3 for usado

        self.bucket = bucket
        self.expire = expire_seconds
        # Sem credenciais explícitas: usa a IAM Role da EC2 (boa prática AWS).
        self.client = boto3.client("s3", region_name=region)

    def save(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def load(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_put_url(self, key: str, content_type: str) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=self.expire,
        )

    def presigned_get_url(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.expire,
        )


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    s = get_settings()
    if s.storage_backend.lower() == "s3":
        return S3Storage(s.s3_bucket, s.s3_region, s.presign_expire_seconds)
    return LocalStorage(s.storage_dir)
