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
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-2000")  # ~2 MiB page cache in RAM
    conn.execute("PRAGMA wal_autocheckpoint=200")
    current_auto_vacuum = conn.execute("PRAGMA auto_vacuum").fetchone()[0]
    if current_auto_vacuum != 2:
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        conn.execute("VACUUM")
    else:
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


def iter_rows(cursor: sqlite3.Cursor) -> Iterator[sqlite3.Row]:
    row = cursor.fetchone()
    while row is not None:
        yield row
        row = cursor.fetchone()
