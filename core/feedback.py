"""Lightweight feedback store.

Goal: let dogfooding doctors tap 👍 / 👎 on an answer. The resulting
rows are a signal Anamnesa itself can mine for corpus-gap prioritisation
— a query that gets a thumbs-down + "tidak ada dosis anak" note points
at a concrete pediatric gap worth closing.

Shape of one row:
  id            ULID
  query_id      client-supplied ULID from the /api/query response
  query_text    raw user query at submission time (for context)
  rating        "up" | "down"
  note          optional free-text (<= 2000 chars)
  answer_sha    short sha of the answer markdown + citation keys, so
                we can tell a "👎" was on the answer the user actually
                saw vs one that has since changed
  created_at    epoch seconds

No dedup, no upsert: each button-press is a distinct row so we preserve
the history of reconsiderations.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import structlog
from ulid import ULID

log = structlog.get_logger("anamnesa.feedback")


class FeedbackStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id           TEXT PRIMARY KEY,
                query_id     TEXT NOT NULL,
                query_text   TEXT NOT NULL,
                rating       TEXT NOT NULL CHECK (rating IN ('up','down')),
                note         TEXT,
                answer_sha   TEXT,
                created_at   REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS feedback_query_id ON feedback(query_id)"
        )
        self._conn.commit()

    def add(
        self,
        *,
        query_id: str,
        query_text: str,
        rating: str,
        note: str | None = None,
        answer_sha: str | None = None,
    ) -> str:
        if rating not in ("up", "down"):
            raise ValueError(f"rating must be 'up' or 'down', got {rating!r}")
        entry_id = str(ULID())
        now = time.time()
        trimmed_note = (note or "")[:2000] or None
        trimmed_query = (query_text or "")[:2000]
        with self._lock:
            self._conn.execute(
                "INSERT INTO feedback "
                "(id, query_id, query_text, rating, note, answer_sha, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry_id,
                    query_id,
                    trimmed_query,
                    rating,
                    trimmed_note,
                    answer_sha,
                    now,
                ),
            )
            self._conn.commit()
        log.info(
            "feedback.stored",
            id=entry_id,
            query_id=query_id,
            rating=rating,
            has_note=bool(trimmed_note),
        )
        return entry_id

    def stats(self, *, include_smoke: bool = False) -> dict[str, Any]:
        """Aggregated stats + the latest 20 rows.

        `include_smoke=False` (default) filters out entries whose
        `query_id` starts with ``SMOKE-`` — those are written by the
        prod smoke-test (`scripts/smoke_prod.py`) and aren't real user
        feedback. Pass True for debugging.
        """
        where = "" if include_smoke else " WHERE query_id NOT LIKE 'SMOKE-%'"
        where_and = (
            "" if include_smoke else " AND query_id NOT LIKE 'SMOKE-%'"
        )
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM feedback{where}"
            ).fetchone()[0]
            up = self._conn.execute(
                f"SELECT COUNT(*) FROM feedback WHERE rating='up'{where_and}"
            ).fetchone()[0]
            down = self._conn.execute(
                f"SELECT COUNT(*) FROM feedback WHERE rating='down'{where_and}"
            ).fetchone()[0]
            recent_rows = self._conn.execute(
                f"SELECT query_text, rating, note, created_at FROM feedback{where} "
                "ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        return {
            "total": int(total or 0),
            "up": int(up or 0),
            "down": int(down or 0),
            "recent": [
                {
                    "query_text": r[0],
                    "rating": r[1],
                    "note": r[2],
                    "created_at": float(r[3]),
                }
                for r in recent_rows
            ],
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["FeedbackStore"]
