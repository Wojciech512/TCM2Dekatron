"""SQLite backed event log service with optional encryption."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from ..core.database import create_connection, iter_rows


EVENT_TYPES = {"INPUT", "OUTPUT", "SENSOR", "CFG", "AUTH", "STRIKE"}


@dataclass
class EventRecord:
    ts: float
    type: str
    message: str
    payload: Dict[str, object]


class EventLogger:
    def __init__(
        self,
        db_path: Path,
        encrypted_fields: Iterable[str],
        fernet_key: Optional[str],
        max_records: Optional[int] = None,
    ) -> None:
        self.db_path = db_path
        self.encrypted_fields = set(encrypted_fields)
        self.fernet: Optional[Fernet] = Fernet(fernet_key) if fernet_key else None
        self._conn = create_connection(db_path)
        self.max_records = max_records if max_records and max_records > 0 else None
        self._ensure_schema()

    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
        self._conn.commit()

    # ------------------------------------------------------------------
    def log(self, event_type: str, message: str, payload: Optional[Dict[str, object]] = None) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type {event_type}")
        payload = payload or {}
        payload_json = json.dumps(payload, ensure_ascii=False)
        if self.fernet and "payload_json" in self.encrypted_fields:
            payload_json = self.fernet.encrypt(payload_json.encode("utf-8")).decode("utf-8")
        with self._conn:
            if self.max_records:
                cursor = self._conn.execute("SELECT COUNT(*) FROM events")
                current = cursor.fetchone()[0]
                if current >= self.max_records:
                    to_remove = (current - self.max_records) + 1
                    self._conn.execute(
                        "DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY ts ASC LIMIT ?)",
                        (to_remove,),
                    )
            self._conn.execute(
                "INSERT INTO events(ts, type, message, payload_json) VALUES (?, ?, ?, ?)",
                (time.time(), event_type, message, payload_json),
            )

    # ------------------------------------------------------------------
    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        order: str = "desc",
    ) -> List[EventRecord]:
        query = "SELECT ts, type, message, payload_json FROM events"
        params: List[object] = []
        if event_type:
            query += " WHERE type = ?"
            params.append(event_type)
        order_clause = "DESC" if order.lower() != "asc" else "ASC"
        query += f" ORDER BY ts {order_clause} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = self._conn.execute(query, params)
        return [self._row_to_record(row) for row in iter_rows(cursor)]

    # ------------------------------------------------------------------
    def count_events(self, event_type: Optional[str] = None) -> int:
        query = "SELECT COUNT(*) FROM events"
        params: List[object] = []
        if event_type:
            query += " WHERE type = ?"
            params.append(event_type)
        cursor = self._conn.execute(query, params)
        count = cursor.fetchone()[0]
        return int(count)

    # ------------------------------------------------------------------
    def iter_events(
        self, chunk_size: int = 500, event_type: Optional[str] = None, order: str = "desc"
    ) -> Iterator[EventRecord]:
        offset = 0
        while True:
            batch = self.list_events(limit=chunk_size, offset=offset, event_type=event_type, order=order)
            if not batch:
                break
            for record in batch:
                yield record
            offset += chunk_size

    # ------------------------------------------------------------------
    def export_jsonl(self, chunk_size: int = 500) -> Iterator[str]:
        for record in self.iter_events(chunk_size=chunk_size):
            yield json.dumps(
                {
                    "ts": record.ts,
                    "type": record.type,
                    "message": record.message,
                    "payload": record.payload,
                },
                ensure_ascii=False,
            )

    # ------------------------------------------------------------------
    def purge_older_than(self, cutoff_ts: float) -> int:
        cursor = self._conn.execute("DELETE FROM events WHERE ts < ?", (cutoff_ts,))
        self._conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    def _row_to_record(self, row: sqlite3.Row) -> EventRecord:
        payload_json = row["payload_json"]
        if self.fernet and "payload_json" in self.encrypted_fields:
            try:
                payload_json = self.fernet.decrypt(payload_json.encode("utf-8")).decode("utf-8")
            except InvalidToken:
                payload_json = "{}"
        payload = json.loads(payload_json)
        return EventRecord(ts=row["ts"], type=row["type"], message=row["message"], payload=payload)

