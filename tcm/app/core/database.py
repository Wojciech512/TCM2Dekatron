"""Database helpers for SQLite-backed services."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator


def ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def create_connection(path: Path) -> sqlite3.Connection:
    ensure_parent(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def iter_rows(cursor: sqlite3.Cursor) -> Iterator[sqlite3.Row]:
    row = cursor.fetchone()
    while row is not None:
        yield row
        row = cursor.fetchone()
