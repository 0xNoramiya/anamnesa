"""SQLite-backed cache of `(normalized_query → FinalResponse)`.

Rationale: the Drafter+Verifier loop costs ~$0.40 and 2 minutes per
query. In a shared clinical tool many users will ask the same thing
("DBD derajat 2 tatalaksana", "TB paru rejimen OAT"). Caching the
canonical answer for 24h makes every repeat question instant and free.

Cache policy:
  - Keyed on a canonical hash of the NormalizedQuery (intent,
    patient_context, condition_tags, structured_query).
  - Store `FinalResponse` + the `trace_events` list so the SSE stream
    can replay in order and the UI feels identical to a live run.
  - TTL 24h by default. Corpus reindexes invalidate by clearing the DB.
  - Only cache success + certain stable refusals (corpus_silent,
    all_superseded_no_current). Transient refusals (budget exhaustion,
    verifier retries) are NOT cached — they may succeed next time.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import structlog

from core.refusals import RefusalReason
from core.state import FinalResponse, NormalizedQuery
from core.trace import TraceEvent

log = structlog.get_logger("anamnesa.cache")

DEFAULT_TTL_SECONDS = 86_400  # 24h

# Refusal reasons that are stable given the current corpus — safe to
# cache. Everything else represents a transient state (budget, quality
# failure, verifier retry) and must not be cached.
_CACHEABLE_REFUSALS: frozenset[RefusalReason] = frozenset(
    {
        RefusalReason.CORPUS_SILENT,
        RefusalReason.ALL_SUPERSEDED_NO_CURRENT,
        RefusalReason.OUT_OF_MEDICAL_SCOPE,
        RefusalReason.PATIENT_SPECIFIC_REQUEST,
    }
)


def cache_key(query: str) -> str:
    """Canonical SHA-256 hash of a user query.

    Whitespace-collapsed + lowercased. We key on the raw input rather
    than the NormalizedQuery because the Haiku normalizer is stochastic:
    back-to-back runs on byte-identical input produce different
    `structured_query` phrasings, which would make cache hits effectively
    impossible. Keying on the raw text guarantees deterministic hits on
    re-asked questions and still benefits colloquial Bahasa because the
    same phrasing usually recurs.
    """
    canon = " ".join(query.lower().split())
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def cache_key_from_normalized(nq: NormalizedQuery) -> str:
    """Legacy helper kept for callers that only have the normalized
    query. Not currently used by the orchestrator."""
    canon = "|".join(
        [
            " ".join(nq.structured_query.lower().split()),
            nq.intent,
            nq.patient_context,
            ",".join(sorted(nq.condition_tags)),
        ]
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


class CachedAnswer:
    __slots__ = ("final_response", "trace_events", "cached_at")

    def __init__(
        self,
        final_response: FinalResponse,
        trace_events: list[TraceEvent],
        cached_at: float,
    ) -> None:
        self.final_response = final_response
        self.trace_events = trace_events
        self.cached_at = cached_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.cached_at


class AnswerCache:
    def __init__(
        self,
        db_path: Path,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI runs handlers across threadpools.
        # Serialize writes ourselves with a mutex.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS answers (
                key         TEXT PRIMARY KEY,
                payload     TEXT NOT NULL,
                created_at  REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, key: str) -> CachedAnswer | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, created_at FROM answers WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        payload_json, created_at = row
        if time.time() - float(created_at) > self.ttl_seconds:
            # Stale — drop it so the next put replaces cleanly.
            self._delete(key)
            return None
        try:
            payload = json.loads(payload_json)
            fr = FinalResponse.model_validate(payload["final_response"])
            events = [TraceEvent.model_validate(e) for e in payload.get("trace_events", [])]
        except Exception as exc:
            log.warning("cache.decode_failed", key=key, error=str(exc))
            self._delete(key)
            return None
        return CachedAnswer(fr, events, float(created_at))

    def put(
        self,
        key: str,
        final_response: FinalResponse,
        trace_events: list[TraceEvent],
    ) -> None:
        # Skip uncacheable refusals.
        if (
            final_response.refusal_reason is not None
            and final_response.refusal_reason not in _CACHEABLE_REFUSALS
        ):
            return
        payload = json.dumps(
            {
                "final_response": final_response.model_dump(mode="json"),
                "trace_events": [e.model_dump(mode="json") for e in trace_events],
            },
            ensure_ascii=False,
        )
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO answers (key, payload, created_at) VALUES (?, ?, ?)",
                (key, payload, now),
            )
            self._conn.commit()

    def clear(self) -> int:
        """Drop all entries. Returns the count removed."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM answers")
            self._conn.commit()
            return cur.rowcount

    def stats(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM answers"
            ).fetchone()
        count, oldest, newest = row
        return {
            "count": int(count or 0),
            "oldest_age_s": (time.time() - float(oldest)) if oldest else None,
            "newest_age_s": (time.time() - float(newest)) if newest else None,
        }

    def _delete(self, key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM answers WHERE key = ?", (key,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = [
    "AnswerCache",
    "CachedAnswer",
    "DEFAULT_TTL_SECONDS",
    "cache_key",
]
