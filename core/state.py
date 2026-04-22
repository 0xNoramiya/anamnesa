"""Shared state and domain types for the agentic retrieval loop.

`QueryState` is the single object that flows through every agent.
Fields accumulate rather than overwrite wherever possible so the trace
remains reconstructible end-to-end.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from ulid import ULID

from core.refusals import RefusalReason
from core.trace import TraceEvent

# ---------------------------------------------------------------------------
# Source-level metadata
# ---------------------------------------------------------------------------

SourceType = Literal[
    "ppk_fktp",          # Pedoman Praktik Klinis FKTP (Kepmenkes 514/2015)
    "pnpk",              # Pedoman Nasional Pelayanan Kedokteran
    "kemkes_program",    # Kemenkes program pedoman (TB, malaria, HIV, etc.)
    "fornas",            # Formularium Nasional
    "pedoman_fktp_ops",  # FKTP operational / Puskesmas workflow
    "other",
]

CurrencyStatus = Literal[
    "current",           # no newer guideline from same authority on same topic
    "superseded",        # newer guideline exists
    "aging",             # >5 years old, no newer version found
    "unknown",           # supersession graph couldn't resolve
    "withdrawn",         # actively retracted
]

Intent = Literal[
    "diagnosis",
    "tatalaksana",
    "dosage",
    "workup",
    "monitoring",
    "rujukan",
    "other",
]

PatientContext = Literal[
    "adult",
    "pediatric",
    "pregnant",
    "geriatric",
    "unspecified",
]


# ---------------------------------------------------------------------------
# Normalizer output
# ---------------------------------------------------------------------------


class NormalizedQuery(BaseModel):
    """Structured restatement of the user's Bahasa query."""

    model_config = ConfigDict(frozen=True)

    structured_query: str
    condition_tags: list[str] = Field(default_factory=list)
    intent: Intent = "other"
    patient_context: PatientContext = "unspecified"
    keywords_id: list[str] = Field(default_factory=list)
    keywords_en: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class RetrievalFilters(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_ids: list[str] | None = None
    source_types: list[SourceType] | None = None
    conditions: list[str] | None = None
    min_year: int | None = None
    max_year: int | None = None
    section_types: list[str] | None = None
    top_k: int = 10


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    page: int
    section_slug: str
    section_path: str
    text: str
    year: int
    source_type: SourceType
    score: float
    retrieval_method: Literal["vector", "bm25", "hybrid"] = "hybrid"
    source_url: str | None = None


class RetrievalAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempt_num: int
    filters: RetrievalFilters
    chunks: list[Chunk] = Field(default_factory=list)
    latency_ms: int = 0
    drafter_feedback: str | None = None


# ---------------------------------------------------------------------------
# Drafter output (discriminated union)
# ---------------------------------------------------------------------------


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str                       # e.g. "PPK-FKTP-2015:p412:dbd_tata_laksana"
    doc_id: str
    page: int
    section_slug: str
    chunk_text: str                # the grounding text (verbatim Bahasa)


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str                  # e.g. "c1"
    text: str                      # Bahasa claim text
    citation_keys: list[str]


class DraftAnswer(BaseModel):
    """Drafter's composed answer. Every claim must map to >=1 citation."""

    model_config = ConfigDict(frozen=True)

    content: str                   # Bahasa draft, contains inline [[key]]
    claims: list[Claim]
    citations: list[Citation]


class DrafterAnswerDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    decision: Literal["answer"] = "answer"
    answer: DraftAnswer


class DrafterNeedMoreRetrieval(BaseModel):
    model_config = ConfigDict(frozen=True)
    decision: Literal["need_more_retrieval"] = "need_more_retrieval"
    filter_hints: RetrievalFilters
    feedback: str = ""             # why the Drafter wants another pass


class DrafterRefuse(BaseModel):
    model_config = ConfigDict(frozen=True)
    decision: Literal["refuse"] = "refuse"
    reason: RefusalReason


DrafterResult = Annotated[
    DrafterAnswerDecision | DrafterNeedMoreRetrieval | DrafterRefuse,
    Field(discriminator="decision"),
]


# ---------------------------------------------------------------------------
# Verifier output
# ---------------------------------------------------------------------------


class CurrencyFlag(BaseModel):
    model_config = ConfigDict(frozen=True)

    citation_key: str
    status: CurrencyStatus
    source_year: int
    superseding_doc_id: str | None = None
    note_id: str | None = None


class ClaimVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    status: Literal["supported", "partial", "unsupported"]
    reasoning: str


class VerificationResult(BaseModel):
    """Output of the Verifier. Verifier judges; never rewrites the draft."""

    model_config = ConfigDict(frozen=True)

    verifications: list[ClaimVerification]
    currency_flags: list[CurrencyFlag] = Field(default_factory=list)
    feedback_for_drafter: str | None = None  # non-null iff a retry is requested

    @property
    def has_unsupported(self) -> bool:
        return any(v.status == "unsupported" for v in self.verifications)


# ---------------------------------------------------------------------------
# Final response + cost ledger
# ---------------------------------------------------------------------------


class CostLedger(BaseModel):
    input_tokens: dict[str, int] = Field(default_factory=dict)
    output_tokens: dict[str, int] = Field(default_factory=dict)
    thinking_tokens: dict[str, int] = Field(default_factory=dict)
    total_tokens: int = 0
    wall_clock_ms: int = 0
    model_calls: dict[str, int] = Field(default_factory=dict)

    def add(
        self,
        agent: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        thinking_tokens: int = 0,
    ) -> None:
        self.input_tokens[agent] = self.input_tokens.get(agent, 0) + input_tokens
        self.output_tokens[agent] = self.output_tokens.get(agent, 0) + output_tokens
        self.thinking_tokens[agent] = (
            self.thinking_tokens.get(agent, 0) + thinking_tokens
        )
        self.total_tokens += input_tokens + output_tokens + thinking_tokens
        self.model_calls[agent] = self.model_calls.get(agent, 0) + 1


class FinalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_id: str
    answer_markdown: str           # Bahasa, with inline [[key]] citations
    citations: list[Citation]
    currency_flags: list[CurrencyFlag]
    disclaimer_id: str = "anamnesa.disclaimer.v1"
    refusal_reason: RefusalReason | None = None  # set iff this is a refusal
    from_cache: bool = False       # True iff replayed from the answer cache
    cached_age_s: float | None = None  # cache entry age at replay time


# ---------------------------------------------------------------------------
# QueryState — the central shared object
# ---------------------------------------------------------------------------


def _new_query_id() -> str:
    return str(ULID())


class QueryState(BaseModel):
    """Shared state object passed through every agent.

    Fields accumulate during the orchestrator loop. Agents MUST append to
    `retrieval_attempts` and `trace_events` rather than overwriting.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query_id: str = Field(default_factory=_new_query_id)
    original_query: str

    normalized_query: NormalizedQuery | None = None
    retrieval_attempts: list[RetrievalAttempt] = Field(default_factory=list)
    draft_answer: DraftAnswer | None = None
    verification: VerificationResult | None = None
    currency_flags: list[CurrencyFlag] = Field(default_factory=list)

    final_response: FinalResponse | None = None
    refusal_reason: RefusalReason | None = None

    trace_events: list[TraceEvent] = Field(default_factory=list)
    cost: CostLedger = Field(default_factory=CostLedger)

    # --- accumulator helpers (orchestrator uses these, not agents) ---

    def append_trace(self, event: TraceEvent) -> None:
        self.trace_events.append(event)

    def append_retrieval(self, attempt: RetrievalAttempt) -> None:
        self.retrieval_attempts.append(attempt)

    @property
    def latest_retrieval(self) -> RetrievalAttempt | None:
        return self.retrieval_attempts[-1] if self.retrieval_attempts else None
