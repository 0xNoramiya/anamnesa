"""Structured trace events emitted by every agent.

Rendered live by the web frontend's agent trace sidebar. Without these,
the demo looks like a chat UI and the agentic work is invisible to judges.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgentName = Literal[
    "normalizer",
    "retriever",
    "drafter",
    "verifier",
    "orchestrator",
]


class TraceEvent(BaseModel):
    """One structured event in the agent trace."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent: AgentName
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
    latency_ms: int = 0


def trace(
    agent: AgentName,
    event_type: str,
    *,
    payload: dict[str, Any] | None = None,
    tokens_used: int = 0,
    latency_ms: int = 0,
) -> TraceEvent:
    return TraceEvent(
        agent=agent,
        event_type=event_type,
        payload=payload or {},
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )
