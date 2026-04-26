from __future__ import annotations

import os

from app.repositories.postgres_storage import PostgresObservabilityStorage
from app.repositories.storage import ObservabilityStorage
from app.repositories.storage_types import StorageBackend


def build_storage_backend() -> StorageBackend:
    backend = os.getenv("STORAGE_BACKEND", "sqlite").strip().lower()
    if backend in {"sqlite", ""}:
        return ObservabilityStorage()
    if backend == "postgres":
        dsn = _postgres_dsn_from_env()
        return PostgresObservabilityStorage(dsn=dsn)
    raise ValueError("Unsupported STORAGE_BACKEND. Use 'sqlite' or 'postgres'.")


def _postgres_dsn_from_env() -> str:
    direct = os.getenv("POSTGRES_DSN", "").strip()
    if direct:
        return direct

    host = os.getenv("POSTGRES_HOST", "").strip()
    port = os.getenv("POSTGRES_PORT", "5432").strip()
    user = os.getenv("POSTGRES_USER", "").strip()
    password = os.getenv("POSTGRES_PASSWORD", "").strip()
    database = os.getenv("POSTGRES_DB", "").strip()
    sslmode = os.getenv("POSTGRES_SSLMODE", "").strip()

    if not (host and user and database):
        raise ValueError(
            "Postgres backend selected but connection info is incomplete. "
            "Set POSTGRES_DSN or POSTGRES_HOST/POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB."
        )

    auth = f"{user}:{password}@" if password else f"{user}@"
    suffix = f"?sslmode={sslmode}" if sslmode else ""
    return f"postgresql://{auth}{host}:{port}/{database}{suffix}"
