"""Agent and Retriever protocols.

Per CLAUDE.md the Drafter and Verifier reach retrieval only via the
`anamnesa-mcp` MCP server — they never touch the vector store, file system,
or PDF cache directly. These protocols enforce that boundary at the type
level: orchestrator wires a `Retriever` into each agent, agents cannot
import storage layers themselves.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.refusals import RefusalReason
from core.state import (
    DrafterResult,
    NormalizedQuery,
    QueryState,
    RetrievalAttempt,
    RetrievalFilters,
    VerificationResult,
)


class NormalizerRefusal:
    """Return this from a Normalizer when the query is out of medical scope."""

    __slots__ = ("reason",)

    def __init__(self, reason: RefusalReason) -> None:
        self.reason = reason


NormalizerResult = NormalizedQuery | NormalizerRefusal


@runtime_checkable
class Normalizer(Protocol):
    """Haiku 4.5 — colloquial Bahasa → structured query.

    One shot. No retries. Orchestrator refuses if output is malformed.
    """

    async def run(self, state: QueryState) -> NormalizerResult: ...


@runtime_checkable
class Retriever(Protocol):
    """MCP client for the `anamnesa-mcp` server — pure retrieval, no LLM."""

    async def search(
        self,
        query: NormalizedQuery,
        filters: RetrievalFilters,
        *,
        attempt_num: int,
    ) -> RetrievalAttempt: ...


@runtime_checkable
class Drafter(Protocol):
    """Opus 4.7 — produces a cited Bahasa answer OR requests more retrieval OR refuses."""

    async def run(
        self,
        state: QueryState,
        *,
        verifier_feedback: str | None = None,
    ) -> DrafterResult: ...


@runtime_checkable
class Verifier(Protocol):
    """Opus 4.7 / 1M — judges draft claims against retrieved sources.

    MUST NOT modify the draft itself. Verifier judges, Drafter writes.
    """

    async def run(self, state: QueryState) -> VerificationResult: ...
