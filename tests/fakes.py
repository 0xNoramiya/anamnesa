"""Test doubles for agents and retriever.

Deterministic, scriptable fakes used by orchestrator tests. These are
test code, not production; real agents live under `agents/` and speak to
Anthropic / MCP.
"""

from __future__ import annotations

from collections.abc import Sequence

from agents.base import NormalizerRefusal, NormalizerResult
from core.refusals import RefusalReason
from core.state import (
    Chunk,
    Citation,
    Claim,
    ClaimVerification,
    CurrencyFlag,
    DraftAnswer,
    DrafterAnswerDecision,
    DrafterNeedMoreRetrieval,
    DrafterRefuse,
    DrafterResult,
    NormalizedQuery,
    QueryState,
    RetrievalAttempt,
    RetrievalFilters,
    VerificationResult,
)

# ---------------------------------------------------------------------------
# Canned builders
# ---------------------------------------------------------------------------


def make_normalized(text: str = "DBD derajat II pediatrik tatalaksana") -> NormalizedQuery:
    return NormalizedQuery(
        structured_query=text,
        condition_tags=["dengue", "pediatric"],
        intent="tatalaksana",
        patient_context="pediatric",
        keywords_id=["DBD", "anak", "cairan"],
        keywords_en=["dengue", "pediatric", "fluid"],
    )


def make_chunk(*, doc_id: str = "PPK-FKTP-2015", page: int = 412) -> Chunk:
    return Chunk(
        doc_id=doc_id,
        page=page,
        section_slug="dbd_tata_laksana",
        section_path=f"bab/dbd/p{page}/tata_laksana",
        text="Terapi cairan kristaloid 6-7 ml/kg/jam pada DBD derajat II pediatrik.",
        year=2015,
        source_type="ppk_fktp",
        score=0.92,
    )


def make_draft_answer() -> DraftAnswer:
    cite = Citation(
        key="PPK-FKTP-2015:p412:dbd_tata_laksana",
        doc_id="PPK-FKTP-2015",
        page=412,
        section_slug="dbd_tata_laksana",
        chunk_text="Terapi cairan kristaloid 6-7 ml/kg/jam pada DBD derajat II pediatrik.",
    )
    claim = Claim(
        claim_id="c1",
        text="Pada DBD derajat II pediatrik, cairan kristaloid 6-7 ml/kg/jam.",
        citation_keys=[cite.key],
    )
    return DraftAnswer(
        content=f"Pada DBD derajat II pediatrik, cairan kristaloid 6-7 ml/kg/jam [[{cite.key}]].",
        claims=[claim],
        citations=[cite],
    )


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeNormalizer:
    def __init__(self, result: NormalizerResult) -> None:
        self.result = result
        self.calls = 0

    async def run(self, state: QueryState) -> NormalizerResult:
        self.calls += 1
        return self.result


class FakeRetriever:
    """Returns a fixed list of chunks per call, cycling through a script."""

    def __init__(self, script: Sequence[list[Chunk]]) -> None:
        self.script = list(script)
        self.calls: list[RetrievalFilters] = []

    async def search(
        self,
        query: NormalizedQuery,
        filters: RetrievalFilters,
        *,
        attempt_num: int,
    ) -> RetrievalAttempt:
        self.calls.append(filters)
        chunks = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        return RetrievalAttempt(
            attempt_num=attempt_num,
            filters=filters,
            chunks=chunks,
            latency_ms=5,
        )


class FakeDrafter:
    """Returns a scripted sequence of DrafterResult values, one per call."""

    def __init__(self, script: Sequence[DrafterResult]) -> None:
        self.script = list(script)
        self.calls = 0
        self.last_feedback: str | None = None

    async def run(
        self,
        state: QueryState,
        *,
        verifier_feedback: str | None = None,
    ) -> DrafterResult:
        self.last_feedback = verifier_feedback
        if self.calls >= len(self.script):
            raise AssertionError(
                f"FakeDrafter called more times ({self.calls + 1}) than scripted "
                f"({len(self.script)})"
            )
        out = self.script[self.calls]
        self.calls += 1
        return out


class FakeVerifier:
    """Returns a scripted sequence of VerificationResult values."""

    def __init__(self, script: Sequence[VerificationResult]) -> None:
        self.script = list(script)
        self.calls = 0

    async def run(self, state: QueryState) -> VerificationResult:
        if self.calls >= len(self.script):
            raise AssertionError(
                f"FakeVerifier called more times ({self.calls + 1}) than scripted "
                f"({len(self.script)})"
            )
        out = self.script[self.calls]
        self.calls += 1
        return out


# ---------------------------------------------------------------------------
# Drafter/Verifier result builders
# ---------------------------------------------------------------------------


def drafter_answer() -> DrafterAnswerDecision:
    return DrafterAnswerDecision(answer=make_draft_answer())


def drafter_need_more(feedback: str = "need narrower", top_k: int = 10) -> DrafterNeedMoreRetrieval:
    return DrafterNeedMoreRetrieval(
        filter_hints=RetrievalFilters(top_k=top_k, conditions=["dengue"]),
        feedback=feedback,
    )


def drafter_refuse(reason: RefusalReason = RefusalReason.CORPUS_SILENT) -> DrafterRefuse:
    return DrafterRefuse(reason=reason)


def verification_all_supported() -> VerificationResult:
    return VerificationResult(
        verifications=[
            ClaimVerification(claim_id="c1", status="supported", reasoning="Exact match on p412."),
        ],
        currency_flags=[
            CurrencyFlag(
                citation_key="PPK-FKTP-2015:p412:dbd_tata_laksana",
                status="aging",
                source_year=2015,
            )
        ],
    )


def verification_unsupported(
    feedback: str = "c1 not supported in cited text",
) -> VerificationResult:
    return VerificationResult(
        verifications=[
            ClaimVerification(claim_id="c1", status="unsupported", reasoning="Not in source."),
        ],
        feedback_for_drafter=feedback,
    )


def normalizer_refusal(
    reason: RefusalReason = RefusalReason.OUT_OF_MEDICAL_SCOPE,
) -> NormalizerRefusal:
    return NormalizerRefusal(reason=reason)
