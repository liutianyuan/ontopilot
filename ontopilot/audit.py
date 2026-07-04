from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone


class AuditLogger:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    object_type TEXT,
                    object_id TEXT,
                    params TEXT,
                    result TEXT,
                    permission_result TEXT
                )
            """)

    def log(
        self,
        user_id: str,
        operation: str,
        object_type: str | None = None,
        object_id: str | None = None,
        params: dict | None = None,
        result: dict | None = None,
        permission_result: str = "pass",
    ) -> str:
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        ts = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    audit_id, ts, user_id, operation,
                    object_type, object_id,
                    json.dumps(params or {}),
                    json.dumps(result or {}),
                    permission_result,
                ),
            )
        return audit_id

    def get_entries(
        self,
        user_id: str | None = None,
        operation: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = "SELECT * FROM audit_log WHERE 1=1"
        args: list = []
        if user_id:
            query += " AND user_id = ?"
            args.append(user_id)
        if operation:
            query += " AND operation = ?"
            args.append(operation)
        query += " ORDER BY timestamp DESC LIMIT ?"
        args.append(limit)
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, args).fetchall()
        return [dict(r) for r in rows]
