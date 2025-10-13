#!/usr/bin/env python3
"""Generate application secrets for TCM 2.0."""

from __future__ import annotations

import argparse
import os
import secrets
from getpass import getpass
from pathlib import Path

from cryptography.fernet import Fernet
from passlib.hash import argon2

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "secrets"


def generate_app_secret_key() -> str:
    """Return a 64-byte secret key encoded as hex."""

    # ``secrets.token_hex`` returns two hex characters per byte.
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


def collect_admin_password(provided: str | None, *, confirm: bool = True) -> str:
    if provided is not None:
        return provided

    password = getpass("Admin bootstrap password: ")
    if confirm:
        password_confirm = getpass("Confirm password: ")
        if password != password_confirm:
            raise ValueError("Passwords do not match.")

    if not password:
        raise ValueError("Password cannot be empty.")

    return password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Docker secret files required to run the TCM 2.0 FastAPI app."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory where secret files will be written. "
            "Defaults to the repository's tcm/secrets folder."
        ),
    )
    parser.add_argument(
        "--admin-password",
        help=(
            "Password to hash for the bootstrap administrator account. "
            "If omitted you will be prompted securely."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing secret files.",
    )
    parser.add_argument(
        "--print",
        dest="print_values",
        action="store_true",
        help="Print generated values to stdout in addition to writing files.",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Do not ask to confirm the admin password (useful for automation).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    admin_password = collect_admin_password(
        args.admin_password, confirm=not args.no_confirm
    )

    secrets_map: dict[str, str] = {
        "app_secret_key": generate_app_secret_key(),
        "app_fernet_key": generate_app_fernet_key(),
        "admin_bootstrap_hash": generate_admin_hash(admin_password),
    }

    for filename, value in secrets_map.items():
        target_path = args.output_dir / filename
        write_secret(target_path, value, force=args.force)

    if args.print_values:
        for filename, value in secrets_map.items():
            print(f"{filename}: {value}")

    print(f"Secrets written to {args.output_dir}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
