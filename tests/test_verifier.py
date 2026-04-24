"""Tests for `OpusVerifier`.

No real Anthropic calls. A `FakeAnthropic` client is injected via
`anthropic_client=`; it returns scripted `messages.create` responses shaped
like the real SDK's Messages objects (duck-typed attributes).

Test seams:
  - `FakeAnthropic(messages=_FakeMessages(script=...))` — scripts response
    objects in order. Captures every `create(**kwargs)` call on `.calls`.
  - `_FakeRetriever` — tiny local retriever stub with scriptable
    `get_full_section` and `check_supersession` for tool dispatch tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from agents.verifier import OpusVerifier
from core.state import (
    QueryState,
    RetrievalAttempt,
    RetrievalFilters,
    VerificationResult,
)
from tests.fakes import make_chunk, make_draft_answer, make_normalized


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class _FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0


@dataclass
class _FakeResponse:
    content: list[Any]
    usage: _FakeUsage
    stop_reason: str = "end_turn"
    id: str = "msg_fake"
    model: str = "claude-opus-4-7"
    role: str = "assistant"
    type: str = "message"


@dataclass
class _FakeMessages:
    script: list[Any] = field(default_factory=list)
    exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        if not self.script:
            raise AssertionError(
                "FakeMessages.create called beyond the end of the scripted responses"
            )
        return self.script.pop(0)


@dataclass
class FakeAnthropic:
    messages: _FakeMessages


class _FakeRetriever:
    """Minimal retriever — satisfies neither Retriever protocol method we
    rely on in Verifier, but exposes the two verifier-facing helpers the
    Verifier dispatches to: `get_full_section` and `check_supersession`.

    Both default to "not available" behaviour if the relevant script is
    omitted; set the script attributes to opt in.
    """

    def __init__(
        self,
        *,
        full_sections: dict[tuple[str, str], dict[str, Any]] | None = None,
        supersessions: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.full_sections = full_sections or {}
        self.supersessions = supersessions or {}
        self.full_section_calls: list[tuple[str, str]] = []
        self.supersession_calls: list[str] = []

    def get_full_section(self, doc_id: str, section_path: str) -> dict[str, Any]:
        self.full_section_calls.append((doc_id, section_path))
        return self.full_sections.get(
            (doc_id, section_path),
            {"error": "section not found"},
        )

    def check_supersession(self, doc_id: str) -> dict[str, Any]:
        self.supersession_calls.append(doc_id)
        return self.supersessions.get(
            doc_id,
            {"status": "unknown", "superseding_doc_id": None, "source_year": 0},
        )


class _MinimalRetriever:
    """Retriever without any of the optional verifier helper methods.

    Used to test the "not available" fall-back branches.
    """


def _tool_use_response(
    *,
    tool_use_id: str,
    name: str,
    tool_input: dict[str, Any],
    input_tokens: int = 100,
    output_tokens: int = 50,
    thinking_tokens: int = 30,
) -> _FakeResponse:
    return _FakeResponse(
        content=[
            _FakeToolUseBlock(id=tool_use_id, name=name, input=tool_input),
        ],
        usage=_FakeUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
        ),
        stop_reason="tool_use",
    )


def _text_response(text: str = "Hmm, still thinking.") -> _FakeResponse:
    return _FakeResponse(
        content=[_FakeTextBlock(text=text)],
        usage=_FakeUsage(input_tokens=10, output_tokens=5),
        stop_reason="end_turn",
    )


def _submit_all_supported() -> dict[str, Any]:
    return {
        "verifications": [
            {
                "claim_id": "c1",
                "status": "supported",
                "reasoning": "Cited chunk on p412 directly supports the claim.",
            }
        ],
        "currency_flags": [
            {
                "citation_key": "PPK-FKTP-2015:p412:dbd_tata_laksana",
                "status": "aging",
                "source_year": 2015,
                "superseding_doc_id": None,
                "note_id": None,
            }
        ],
        "feedback_for_drafter": None,
    }


def _submit_one_unsupported() -> dict[str, Any]:
    return {
        "verifications": [
            {
                "claim_id": "c1",
                "status": "unsupported",
                "reasoning": "Cited chunk is adult section; claim is pediatric.",
            }
        ],
        "currency_flags": [
            {
                "citation_key": "PPK-FKTP-2015:p412:dbd_tata_laksana",
                "status": "aging",
                "source_year": 2015,
                "superseding_doc_id": None,
                "note_id": None,
            }
        ],
        "feedback_for_drafter": "c1: adult vs pediatric mismatch; cite pediatric section.",
    }


def _state_with_draft() -> QueryState:
    nq = make_normalized()
    state = QueryState(original_query="DBD anak derajat 2")
    state.normalized_query = nq
    state.append_retrieval(
        RetrievalAttempt(
            attempt_num=1,
            filters=RetrievalFilters(),
            chunks=[make_chunk()],
            latency_ms=5,
        )
    )
    state.draft_answer = make_draft_answer()
    return state


def _make_verifier(
    *,
    client: FakeAnthropic,
    retriever: Any | None = None,
    thinking_budget: int = 0,
) -> OpusVerifier:
    retriever = retriever if retriever is not None else _FakeRetriever()
    return OpusVerifier(
        retriever=retriever,
        anthropic_client=client,
        model_id="claude-opus-4-7",
        system_prompt="VERIFIER_PROMPT_STUB",
        thinking_budget=thinking_budget,
    )


@pytest.mark.asyncio
async def test_happy_path_all_supported() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_verification",
                    tool_input=_submit_all_supported(),
                )
            ]
        )
    )
    verifier = _make_verifier(client=client)

    result = await verifier.run(_state_with_draft())

    assert isinstance(result, VerificationResult)
    assert result.has_unsupported is False
    assert len(result.verifications) == 1
    assert result.verifications[0].claim_id == "c1"
    assert result.verifications[0].status == "supported"
    assert result.feedback_for_drafter is None
    assert len(result.currency_flags) == 1
    flag = result.currency_flags[0]
    assert flag.citation_key == "PPK-FKTP-2015:p412:dbd_tata_laksana"
    assert flag.status == "aging"
    assert flag.source_year == 2015

    assert len(client.messages.calls) == 1
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-4-7"
    assert call["system"] == [
        {
            "type": "text",
            "text": "VERIFIER_PROMPT_STUB",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert {t["name"] for t in call["tools"]} == {
        "get_full_section",
        "check_supersession",
        "submit_verification",
    }
    # thinking_budget=0 → no thinking key
    assert "thinking" not in call


@pytest.mark.asyncio
async def test_unsupported_claim_sets_feedback() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_verification",
                    tool_input=_submit_one_unsupported(),
                )
            ]
        )
    )
    verifier = _make_verifier(client=client)

    result = await verifier.run(_state_with_draft())

    assert result.has_unsupported is True
    assert result.feedback_for_drafter is not None
    assert "c1" in result.feedback_for_drafter
    assert result.verifications[0].status == "unsupported"


@pytest.mark.asyncio
async def test_tool_use_loop_full_section_then_supersession_then_submit() -> None:
    retriever = _FakeRetriever(
        full_sections={
            ("PPK-FKTP-2015", "bab/dbd/p412/tata_laksana"): {
                "section_text": (
                    "Pada DBD derajat II pediatrik, cairan kristaloid 6-7 ml/kg/jam."
                ),
                "doc_id": "PPK-FKTP-2015",
                "page": 412,
            }
        },
        supersessions={
            "PPK-FKTP-2015": {
                "status": "current",
                "superseding_doc_id": None,
                "source_year": 2015,
            }
        },
    )
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="gfs1",
                    name="get_full_section",
                    tool_input={
                        "doc_id": "PPK-FKTP-2015",
                        "section_path": "bab/dbd/p412/tata_laksana",
                    },
                ),
                _tool_use_response(
                    tool_use_id="cs1",
                    name="check_supersession",
                    tool_input={"doc_id": "PPK-FKTP-2015"},
                ),
                _tool_use_response(
                    tool_use_id="sub1",
                    name="submit_verification",
                    tool_input=_submit_all_supported(),
                ),
            ]
        )
    )
    verifier = _make_verifier(client=client, retriever=retriever)

    result = await verifier.run(_state_with_draft())

    assert result.has_unsupported is False
    assert retriever.full_section_calls == [
        ("PPK-FKTP-2015", "bab/dbd/p412/tata_laksana")
    ]
    assert retriever.supersession_calls == ["PPK-FKTP-2015"]

    assert len(client.messages.calls) == 3
    second = client.messages.calls[1]
    last_msg = second["messages"][-1]
    assert last_msg["role"] == "user"
    block = last_msg["content"][0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "gfs1"

    third = client.messages.calls[2]
    last_msg = third["messages"][-1]
    assert last_msg["content"][0]["tool_use_id"] == "cs1"


@pytest.mark.asyncio
async def test_invariant_coercion_synthesizes_missing_feedback() -> None:
    payload = {
        "verifications": [
            {
                "claim_id": "c1",
                "status": "unsupported",
                "reasoning": "Number mismatch: claim says 6-7 ml/kg/jam, source says 5-10.",
            }
        ],
        "currency_flags": [
            {
                "citation_key": "PPK-FKTP-2015:p412:dbd_tata_laksana",
                "status": "aging",
                "source_year": 2015,
                "superseding_doc_id": None,
                "note_id": None,
            }
        ],
        "feedback_for_drafter": None,  # invariant violated
    }
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_verification",
                    tool_input=payload,
                )
            ]
        )
    )
    verifier = _make_verifier(client=client)

    result = await verifier.run(_state_with_draft())

    assert result.has_unsupported is True
    assert result.feedback_for_drafter is not None
    assert "c1" in result.feedback_for_drafter


@pytest.mark.asyncio
async def test_end_turn_without_submit_fails_closed() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(script=[_text_response("I'm giving up.")])
    )
    verifier = _make_verifier(client=client)
    state = _state_with_draft()

    result = await verifier.run(state)

    assert result.has_unsupported is True
    assert result.feedback_for_drafter is not None
    assert all(v.status == "unsupported" for v in result.verifications)
    assert len(result.verifications) == len(state.draft_answer.claims)  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_loop_cap_exhausted_fails_closed() -> None:
    retriever = _FakeRetriever(
        supersessions={
            "PPK-FKTP-2015": {
                "status": "current",
                "superseding_doc_id": None,
                "source_year": 2015,
            }
        }
    )
    # Keep calling check_supersession forever; never submit.
    spam = [
        _tool_use_response(
            tool_use_id=f"cs{i}",
            name="check_supersession",
            tool_input={"doc_id": "PPK-FKTP-2015"},
        )
        for i in range(20)
    ]
    client = FakeAnthropic(messages=_FakeMessages(script=spam))
    verifier = _make_verifier(client=client, retriever=retriever)

    result = await verifier.run(_state_with_draft())

    assert result.has_unsupported is True
    assert result.feedback_for_drafter is not None
    assert all(v.status == "unsupported" for v in result.verifications)
    # Hard cap at MAX_ITERS=8.
    assert len(client.messages.calls) == 8


@pytest.mark.asyncio
async def test_malformed_submit_input_fails_closed() -> None:
    bad_payload: dict[str, Any] = {
        "verifications": "not_a_list",  # wrong type
        "currency_flags": [],
        "feedback_for_drafter": None,
    }
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_verification",
                    tool_input=bad_payload,
                )
            ]
        )
    )
    verifier = _make_verifier(client=client)

    result = await verifier.run(_state_with_draft())

    assert result.has_unsupported is True
    assert result.feedback_for_drafter is not None
    assert all(v.status == "unsupported" for v in result.verifications)


@pytest.mark.asyncio
async def test_transport_error_propagates() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(exc=RuntimeError("connection reset"))
    )
    verifier = _make_verifier(client=client)

    with pytest.raises(RuntimeError, match="connection reset"):
        await verifier.run(_state_with_draft())


@pytest.mark.asyncio
async def test_last_usage_populated() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_verification",
                    tool_input=_submit_all_supported(),
                    input_tokens=512,
                    output_tokens=128,
                    thinking_tokens=64,
                )
            ]
        )
    )
    verifier = _make_verifier(client=client)
    assert verifier.last_usage is None

    await verifier.run(_state_with_draft())

    assert verifier.last_usage is not None
    assert verifier.last_usage["input_tokens"] == 512
    assert verifier.last_usage["output_tokens"] == 128
    assert verifier.last_usage["model_id"] == "claude-opus-4-7"
    assert verifier.last_usage["iterations"] == 1


@pytest.mark.asyncio
async def test_helper_tools_fallback_when_retriever_lacks_methods() -> None:
    retriever = _MinimalRetriever()
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="gfs1",
                    name="get_full_section",
                    tool_input={"doc_id": "PPK-FKTP-2015", "section_path": "x"},
                ),
                _tool_use_response(
                    tool_use_id="cs1",
                    name="check_supersession",
                    tool_input={"doc_id": "PPK-FKTP-2015"},
                ),
                _tool_use_response(
                    tool_use_id="sub1",
                    name="submit_verification",
                    tool_input=_submit_all_supported(),
                ),
            ]
        )
    )
    verifier = _make_verifier(client=client, retriever=retriever)

    result = await verifier.run(_state_with_draft())

    assert result.has_unsupported is False
    assert len(client.messages.calls) == 3


def test_constructor_requires_either_client_or_api_key() -> None:
    with pytest.raises(ValueError, match="anthropic_client"):
        OpusVerifier(retriever=_FakeRetriever(), system_prompt="stub")


@pytest.mark.asyncio
async def test_thinking_enabled_when_budget_positive() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_verification",
                    tool_input=_submit_all_supported(),
                )
            ]
        )
    )
    verifier = _make_verifier(client=client, thinking_budget=12_000)

    await verifier.run(_state_with_draft())

    call = client.messages.calls[0]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "xhigh"}
