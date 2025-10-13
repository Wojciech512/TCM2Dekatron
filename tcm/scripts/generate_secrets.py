#!/usr/bin/env python3
from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

if __package__ is None or __package__ == "":
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

    from tcm.app.core.secrets import (
        generate_admin_hash,
        generate_app_fernet_key,
        generate_app_secret_key,
        write_secret,
    )
else:
    from ..app.core.secrets import (
        generate_admin_hash,
        generate_app_fernet_key,
        generate_app_secret_key,
        write_secret,
    )

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "secrets"


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


if __name__ == "__main__":
    main()
