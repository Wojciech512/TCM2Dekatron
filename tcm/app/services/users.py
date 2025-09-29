"""User repository backed by SQLite."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from passlib.context import CryptContext

from ..core.database import create_connection

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class UserStore:
    def __init__(self, db_path: Path) -> None:
        self._conn = create_connection(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    def create_user(self, username: str, password: str, role: str) -> None:
        password_hash = pwd_context.hash(password)
        self._conn.execute(
            "INSERT OR REPLACE INTO users(username, password_hash, role) VALUES(?, ?, ?)",
            (username, password_hash, role),
        )
        self._conn.commit()

    def create_user_with_hash(
        self, username: str, password_hash: str, role: str
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO users(username, password_hash, role) VALUES(?, ?, ?)",
            (username, password_hash, role),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    def verify_credentials(self, username: str, password: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            return None
        if pwd_context.verify(password, row["password_hash"]):
            return row["role"]
        return None

    def get_role(self, username: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT role FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row["role"] if row else None
