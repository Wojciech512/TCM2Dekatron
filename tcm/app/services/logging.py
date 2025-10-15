"""SQLite backed event log service with optional encryption."""

from __future__ import annotations

import atexit
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

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
        *,
        flush_interval_seconds: float = 5.0,
        flush_max_records: int = 32,
        vacuum_interval_seconds: float = 1800.0,
        vacuum_pages: int = 32,
    ) -> None:
        self.db_path = db_path
        self.encrypted_fields = set(encrypted_fields)
        self.fernet: Optional[Fernet] = Fernet(fernet_key) if fernet_key else None
        self._conn = create_connection(db_path)
        self.max_records = max_records if max_records and max_records > 0 else None
        self.flush_interval = flush_interval_seconds if flush_interval_seconds > 0 else 0.0
        self.flush_max_records = flush_max_records if flush_max_records > 0 else 1
        self.vacuum_interval = vacuum_interval_seconds if vacuum_interval_seconds > 0 else 0.0
        self.vacuum_pages = vacuum_pages if vacuum_pages and vacuum_pages > 0 else 0
        self._buffer: List[Tuple[float, str, str, str]] = []
        self._lock = Lock()
        now = time.monotonic()
        self._last_flush = now
        self._last_vacuum = now
        self._ensure_schema()
        atexit.register(self.flush)

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
    def _should_flush_locked(self) -> bool:
        if not self._buffer:
            return False
        if self.flush_interval == 0.0:
            return True
        if len(self._buffer) >= self.flush_max_records:
            return True
        return (time.monotonic() - self._last_flush) >= self.flush_interval

    def _run_incremental_vacuum(self) -> None:
        if not self.vacuum_interval:
            return
        now = time.monotonic()
        if (now - self._last_vacuum) < self.vacuum_interval:
            return
        if self.vacuum_pages:
            self._conn.execute(f"PRAGMA incremental_vacuum({self.vacuum_pages})")
        else:
            self._conn.execute("PRAGMA incremental_vacuum")
        self._conn.commit()
        self._last_vacuum = now

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        records = list(self._buffer)
        self._buffer.clear()
        with self._conn:
            if self.max_records:
                cursor = self._conn.execute("SELECT COUNT(*) FROM events")
                current = int(cursor.fetchone()[0])
                overflow = (current + len(records)) - self.max_records
                if overflow > 0:
                    self._conn.execute(
                        "DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY ts ASC LIMIT ?)",
                        (overflow,),
                    )
            self._conn.executemany(
                "INSERT INTO events(ts, type, message, payload_json) VALUES (?, ?, ?, ?)",
                records,
            )
        self._last_flush = time.monotonic()
        self._run_incremental_vacuum()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    # ------------------------------------------------------------------
    def log(
        self, event_type: str, message: str, payload: Optional[Dict[str, object]] = None
    ) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type {event_type}")
        payload = payload or {}
        payload_json = json.dumps(payload, ensure_ascii=False)
        if self.fernet and "payload_json" in self.encrypted_fields:
            payload_json = self.fernet.encrypt(payload_json.encode("utf-8")).decode(
                "utf-8"
            )
        record = (time.time(), event_type, message, payload_json)
        with self._lock:
            self._buffer.append(record)
            if self._should_flush_locked():
                self._flush_locked()

    # ------------------------------------------------------------------
    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        order: str = "desc",
    ) -> List[EventRecord]:
        self.flush()
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
        self.flush()
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
        self,
        chunk_size: int = 500,
        event_type: Optional[str] = None,
        order: str = "desc",
    ) -> Iterator[EventRecord]:
        self.flush()
        offset = 0
        while True:
            batch = self.list_events(
                limit=chunk_size, offset=offset, event_type=event_type, order=order
            )
            if not batch:
                break
            for record in batch:
                yield record
            offset += chunk_size

    # ------------------------------------------------------------------
    def export_jsonl(self, chunk_size: int = 500) -> Iterator[str]:
        self.flush()
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
        self.flush()
        cursor = self._conn.execute("DELETE FROM events WHERE ts < ?", (cutoff_ts,))
        self._conn.commit()
        self._run_incremental_vacuum()
        return cursor.rowcount

    # ------------------------------------------------------------------
    def _row_to_record(self, row: sqlite3.Row) -> EventRecord:
        payload_json = row["payload_json"]
        if self.fernet and "payload_json" in self.encrypted_fields:
            try:
                payload_json = self.fernet.decrypt(payload_json.encode("utf-8")).decode(
                    "utf-8"
                )
            except InvalidToken:
                payload_json = "{}"
        payload = json.loads(payload_json)
        return EventRecord(
            ts=row["ts"], type=row["type"], message=row["message"], payload=payload
        )
