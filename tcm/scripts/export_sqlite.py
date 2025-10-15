#!/usr/bin/env python3
"""Utility to export the SQLite database to an external medium."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from tcm.app.core.config import AppConfig


def vacuum_into(db_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        quoted = str(destination).replace("'", "''")
        connection.execute(f"VACUUM INTO '{quoted}'")
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export SQLite data using VACUUM INTO to avoid write amplification."
    )
    parser.add_argument(
        "--config",
        default="tcm/config/app.yaml",
        help="Ścieżka do pliku konfiguracyjnego aplikacji (domyślnie tcm/config/app.yaml).",
    )
    parser.add_argument(
        "--db-path",
        help="Bezpośrednia ścieżka do bazy SQLite. Domyślnie pobierana z konfiguracji.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Docelowy plik na zewnętrznym nośniku (VACUUM INTO).",
    )
    args = parser.parse_args()

    config = AppConfig.from_yaml(Path(args.config))
    db_path = Path(args.db_path) if args.db_path else Path(config.logging.sqlite_path)
    output = Path(args.output)

    vacuum_into(db_path, output)


if __name__ == "__main__":
    main()
