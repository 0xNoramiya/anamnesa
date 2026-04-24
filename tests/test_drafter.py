"""Tests for `OpusDrafter`.

No real Anthropic calls. A `FakeAnthropic` client is injected via
`anthropic_client=`; it returns scripted `messages.create` responses shaped
like the real SDK's Messages objects (duck-typed attributes).

Test seams:
  - `FakeAnthropic(messages=_FakeMessages(script=...))` — scripts response
    objects in order. Captures every `create(**kwargs)` call on `.calls`.
  - `FakeRetriever` from tests/fakes.py — for both the "intra-drafter
    search" path AND for the optional orchestrator end-to-end check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from agents.drafter import OpusDrafter
from core.refusals import RefusalReason
from core.state import (
    DrafterAnswerDecision,
    DrafterNeedMoreRetrieval,
    DrafterRefuse,
    QueryState,
    RetrievalAttempt,
    RetrievalFilters,
)
from tests.fakes import FakeRetriever, make_chunk, make_normalized


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


def _text_response(text: str = "I have no tool to call, sorry.") -> _FakeResponse:
    return _FakeResponse(
        content=[_FakeTextBlock(text=text)],
        usage=_FakeUsage(input_tokens=10, output_tokens=5),
        stop_reason="end_turn",
    )


def _submit_answer_input() -> dict[str, Any]:
    chunk_text = (
        "Terapi cairan kristaloid 6-7 ml/kg/jam pada DBD derajat II pediatrik."
    )
    return {
        "decision": "answer",
        "answer": {
            "content": (
                "Pada DBD derajat II pediatrik, cairan kristaloid 6-7 ml/kg/jam "
                "[[PPK-FKTP-2015:p412:dbd_tata_laksana]]."
            ),
            "claims": [
                {
                    "claim_id": "c1",
                    "text": (
                        "Pada DBD derajat II pediatrik, cairan kristaloid "
                        "6-7 ml/kg/jam."
                    ),
                    "citation_keys": ["PPK-FKTP-2015:p412:dbd_tata_laksana"],
                },
            ],
            "citations": [
                {
                    "key": "PPK-FKTP-2015:p412:dbd_tata_laksana",
                    "doc_id": "PPK-FKTP-2015",
                    "page": 412,
                    "section_slug": "dbd_tata_laksana",
                    "chunk_text": chunk_text,
                },
            ],
        },
    }


def _make_drafter(
    *,
    client: FakeAnthropic,
    retriever: FakeRetriever | None = None,
    thinking_budget: int = 8000,
) -> OpusDrafter:
    retriever = retriever or FakeRetriever(script=[[make_chunk()]])
    return OpusDrafter(
        retriever=retriever,
        anthropic_client=client,
        model_id="claude-opus-4-7",
        system_prompt="DRAFTER_PROMPT_STUB",
        thinking_budget=thinking_budget,
    )


def _state_with_chunks() -> QueryState:
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
    return state


@pytest.mark.asyncio
async def test_happy_path_answer_decision() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input=_submit_answer_input(),
                    input_tokens=250,
                    output_tokens=120,
                    thinking_tokens=80,
                ),
            ]
        )
    )
    drafter = _make_drafter(client=client)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterAnswerDecision)
    assert result.decision == "answer"
    assert len(result.answer.claims) == 1
    assert result.answer.claims[0].claim_id == "c1"
    assert len(result.answer.citations) == 1
    assert (
        result.answer.citations[0].key == "PPK-FKTP-2015:p412:dbd_tata_laksana"
    )
    assert len(client.messages.calls) == 1
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-4-7"
    # System is a list of blocks so we can attach cache_control to it.
    assert call["system"] == [
        {
            "type": "text",
            "text": "DRAFTER_PROMPT_STUB",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert {t["name"] for t in call["tools"]} == {
        "search_guidelines",
        "get_full_section",
        "submit_decision",
    }
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "xhigh"}


@pytest.mark.asyncio
async def test_need_more_retrieval_decision_with_filter_hints() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input={
                        "decision": "need_more_retrieval",
                        "filter_hints": {
                            "conditions": ["dengue"],
                            "source_types": ["ppk_fktp", "pnpk"],
                            "min_year": 2018,
                            "top_k": 15,
                        },
                        "feedback": "need pediatric-only chunks",
                    },
                )
            ]
        )
    )
    drafter = _make_drafter(client=client)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterNeedMoreRetrieval)
    assert result.decision == "need_more_retrieval"
    assert result.feedback == "need pediatric-only chunks"
    assert result.filter_hints.conditions == ["dengue"]
    assert result.filter_hints.source_types == ["ppk_fktp", "pnpk"]
    assert result.filter_hints.min_year == 2018
    assert result.filter_hints.top_k == 15


@pytest.mark.asyncio
async def test_refuse_corpus_silent_decision() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input={
                        "decision": "refuse",
                        "reason": "corpus_silent",
                    },
                )
            ]
        )
    )
    drafter = _make_drafter(client=client)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterRefuse)
    assert result.reason is RefusalReason.CORPUS_SILENT


@pytest.mark.asyncio
async def test_search_guidelines_then_submit_decision() -> None:
    retriever = FakeRetriever(
        script=[
            [make_chunk(page=413)],
        ]
    )
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="s1",
                    name="search_guidelines",
                    tool_input={
                        "query": "DBD anak derajat II tata laksana cairan",
                        "filters": {
                            "conditions": ["dengue"],
                            "source_types": ["ppk_fktp"],
                            "top_k": 5,
                        },
                    },
                ),
                _tool_use_response(
                    tool_use_id="t2",
                    name="submit_decision",
                    tool_input=_submit_answer_input(),
                ),
            ]
        )
    )
    drafter = _make_drafter(client=client, retriever=retriever)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterAnswerDecision)
    assert len(retriever.calls) == 1
    called_filters = retriever.calls[0]
    assert called_filters.conditions == ["dengue"]
    assert called_filters.source_types == ["ppk_fktp"]
    assert called_filters.top_k == 5

    assert len(client.messages.calls) == 2
    second_call = client.messages.calls[1]
    last_msg = second_call["messages"][-1]
    assert last_msg["role"] == "user"
    block = last_msg["content"][0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "s1"


@pytest.mark.asyncio
async def test_verifier_feedback_rendered_in_initial_user_message() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input=_submit_answer_input(),
                ),
            ]
        )
    )
    drafter = _make_drafter(client=client)

    feedback = "c1 claim about fluid rate not supported by PPK-FKTP-2015:p412"
    await drafter.run(_state_with_chunks(), verifier_feedback=feedback)

    call = client.messages.calls[0]
    first_user_msg = call["messages"][0]
    assert first_user_msg["role"] == "user"
    content = first_user_msg["content"]
    assert "<verifier_feedback>" in content
    assert feedback in content
    assert "RETRY" in content
    assert "<normalized_query>" in content
    assert "<chunks>" in content


@pytest.mark.asyncio
async def test_loop_cap_exceeded_triggers_citations_unverifiable_refusal() -> None:
    # Always return a search_guidelines tool_use; never submit_decision.
    # We need enough scripted responses to exceed MAX_LOOP_ITERATIONS (=8).
    searches = [
        _tool_use_response(
            tool_use_id=f"s{i}",
            name="search_guidelines",
            tool_input={"query": "anything"},
        )
        for i in range(12)
    ]
    retriever = FakeRetriever(script=[[make_chunk()]] * 12)
    client = FakeAnthropic(messages=_FakeMessages(script=searches))
    drafter = _make_drafter(client=client, retriever=retriever)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterRefuse)
    assert result.reason is RefusalReason.CITATIONS_UNVERIFIABLE
    assert len(client.messages.calls) == 8


@pytest.mark.asyncio
async def test_malformed_submit_decision_triggers_citations_unverifiable() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input={"decision": "ponder"},  # not a valid decision
                )
            ]
        )
    )
    drafter = _make_drafter(client=client)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterRefuse)
    assert result.reason is RefusalReason.CITATIONS_UNVERIFIABLE


@pytest.mark.asyncio
async def test_refuse_with_disallowed_reason_collapses_to_citations_unverifiable() -> None:
    # `citations_unverifiable` itself is NOT a Drafter-level refusal reason
    # — only corpus_silent/all_superseded_no_current/patient_specific_request/
    # out_of_medical_scope are allowed.
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input={
                        "decision": "refuse",
                        "reason": "citations_unverifiable",
                    },
                )
            ]
        )
    )
    drafter = _make_drafter(client=client)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterRefuse)
    assert result.reason is RefusalReason.CITATIONS_UNVERIFIABLE


@pytest.mark.asyncio
async def test_claude_ends_turn_without_submission_triggers_refusal() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[_text_response("I'm just thinking out loud here.")]
        )
    )
    drafter = _make_drafter(client=client)

    result = await drafter.run(_state_with_chunks())

    assert isinstance(result, DrafterRefuse)
    assert result.reason is RefusalReason.CITATIONS_UNVERIFIABLE


@pytest.mark.asyncio
async def test_last_usage_populated_after_happy_path() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input=_submit_answer_input(),
                    input_tokens=420,
                    output_tokens=137,
                    thinking_tokens=256,
                )
            ]
        )
    )
    drafter = _make_drafter(client=client)
    assert drafter.last_usage is None

    await drafter.run(_state_with_chunks())

    assert drafter.last_usage is not None
    assert drafter.last_usage["input_tokens"] == 420
    assert drafter.last_usage["output_tokens"] == 137
    assert drafter.last_usage["thinking_tokens"] == 256
    assert drafter.last_usage["model_id"] == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_last_usage_accumulates_across_tool_use_loop() -> None:
    retriever = FakeRetriever(script=[[make_chunk(page=413)]])
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="s1",
                    name="search_guidelines",
                    tool_input={"query": "x"},
                    input_tokens=100,
                    output_tokens=50,
                    thinking_tokens=25,
                ),
                _tool_use_response(
                    tool_use_id="t2",
                    name="submit_decision",
                    tool_input=_submit_answer_input(),
                    input_tokens=200,
                    output_tokens=90,
                    thinking_tokens=40,
                ),
            ]
        )
    )
    drafter = _make_drafter(client=client, retriever=retriever)

    await drafter.run(_state_with_chunks())

    assert drafter.last_usage is not None
    assert drafter.last_usage["input_tokens"] == 300
    assert drafter.last_usage["output_tokens"] == 140
    assert drafter.last_usage["thinking_tokens"] == 65


class _BoomAPIError(Exception):
    """Stand-in for an Anthropic transport failure."""


@pytest.mark.asyncio
async def test_transport_error_propagates() -> None:
    client = FakeAnthropic(messages=_FakeMessages(exc=_BoomAPIError("connection reset")))
    drafter = _make_drafter(client=client)

    with pytest.raises(_BoomAPIError, match="connection reset"):
        await drafter.run(_state_with_chunks())


@pytest.mark.asyncio
async def test_orchestrator_integration_with_opus_drafter() -> None:
    from core.orchestrator import Orchestrator
    from tests.fakes import FakeNormalizer, FakeVerifier, verification_all_supported

    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input=_submit_answer_input(),
                )
            ]
        )
    )
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = OpusDrafter(
        retriever=retriever,
        anthropic_client=client,
        model_id="claude-opus-4-7",
        system_prompt="STUB",
        thinking_budget=0,  # disable thinking for a cleaner request shape
    )

    orch = Orchestrator(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=retriever,
        drafter=drafter,
        verifier=FakeVerifier(script=[verification_all_supported()]),
    )
    state = await orch.run("DBD anak derajat 2, tata laksana cairan awal?")

    assert state.final_response is not None
    assert state.refusal_reason is None
    assert len(state.final_response.citations) == 1
    assert (
        state.final_response.citations[0].key
        == "PPK-FKTP-2015:p412:dbd_tata_laksana"
    )
    # Orchestrator did its retrieval; drafter did NOT add another attempt.
    assert len(state.retrieval_attempts) == 1


def test_constructor_requires_either_client_or_api_key() -> None:
    retriever = FakeRetriever(script=[[]])
    with pytest.raises(ValueError, match="anthropic_client"):
        OpusDrafter(retriever=retriever, system_prompt="stub")


@pytest.mark.asyncio
async def test_thinking_disabled_when_budget_is_zero() -> None:
    client = FakeAnthropic(
        messages=_FakeMessages(
            script=[
                _tool_use_response(
                    tool_use_id="t1",
                    name="submit_decision",
                    tool_input=_submit_answer_input(),
                ),
            ]
        )
    )
    drafter = _make_drafter(client=client, thinking_budget=0)

    await drafter.run(_state_with_chunks())

    call = client.messages.calls[0]
    assert "thinking" not in call
