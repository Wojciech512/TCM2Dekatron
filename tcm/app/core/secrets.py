"""Utilities for generating and persisting application secrets."""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Callable, Optional

from cryptography.fernet import Fernet
from passlib.hash import argon2

LOGGER = logging.getLogger(__name__)


def generate_app_secret_key() -> str:
    """Return a 64-byte secret key encoded as hex."""

    return secrets.token_hex(64)


def generate_app_fernet_key() -> str:
    """Return a Fernet key encoded as URL-safe base64."""

    return Fernet.generate_key().decode("ascii")


def generate_admin_hash(password: str) -> str:
    """Hash the bootstrap admin password using Argon2id."""

    return argon2.using(type="ID", rounds=3, memory_cost=65536, parallelism=2).hash(
        password
    )


def write_secret(path: Path, value: str, *, force: bool = False) -> None:
    """Persist a secret to ``path`` with restrictive permissions."""

    if path.exists() and not force:
        raise FileExistsError(
            f"Secret file {path} already exists. Use --force to overwrite."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")

    try:
        os.chmod(path, 0o600)
    except PermissionError:
        # Ignore permission errors on platforms that do not support chmod.
        pass


def _ensure_secret(path: Path, factory: Callable[[], str]) -> str:
    """Return the secret stored in ``path`` creating it if necessary."""

    try:
        existing = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""

    if existing:
        return existing

    value = factory()
    write_secret(path, value, force=True)
    LOGGER.info("Generated secret %s", path.name)
    return value


def ensure_secret_material(
    *,
    secret_key_path: Path,
    fernet_key_path: Path,
    admin_hash_path: Path,
    admin_password: Optional[str],
) -> None:
    """Ensure that all required secret material is present on disk."""

    _ensure_secret(secret_key_path, generate_app_secret_key)
    _ensure_secret(fernet_key_path, generate_app_fernet_key)

    if admin_hash_path.exists():
        return

    if not admin_password:
        LOGGER.warning(
            "Admin password not provided; bootstrap user will not be created."
        )
        return

    admin_hash = generate_admin_hash(admin_password)
    write_secret(admin_hash_path, admin_hash, force=True)
    LOGGER.info("Generated admin bootstrap hash")
