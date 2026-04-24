"""Tests for `HaikuNormalizer`.

These tests never call Anthropic. A `FakeAnthropic` client is injected via
the `anthropic_client=` seam; it returns scripted `messages.create`
responses matching the real SDK's duck-typed shape (object with
`.content[0].text` and `.usage.{input,output}_tokens`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from agents.base import NormalizerRefusal
from agents.normalizer import HaikuNormalizer
from core.refusals import RefusalReason
from core.state import NormalizedQuery, QueryState


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class _FakeResponse:
    content: list[_FakeTextBlock]
    usage: _FakeUsage
    id: str = "msg_fake"
    model: str = "claude-haiku-4-5-20251001"
    role: str = "assistant"
    stop_reason: str = "end_turn"
    type: str = "message"


@dataclass
class _FakeMessages:
    response: _FakeResponse | None = None
    exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        assert self.response is not None, "FakeMessages called without a scripted response"
        return self.response


@dataclass
class FakeAnthropic:
    messages: _FakeMessages


def _scripted_client(
    *,
    text: str,
    input_tokens: int = 42,
    output_tokens: int = 21,
) -> FakeAnthropic:
    return FakeAnthropic(
        messages=_FakeMessages(
            response=_FakeResponse(
                content=[_FakeTextBlock(text=text)],
                usage=_FakeUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            )
        )
    )


def _make_normalizer(client: FakeAnthropic) -> HaikuNormalizer:
    return HaikuNormalizer(
        anthropic_client=client,
        model_id="claude-haiku-4-5-20251001",
        system_prompt="SYSTEM_PROMPT_STUB",  # avoid reading the real file
    )


def _state(query: str) -> QueryState:
    return QueryState(original_query=query)


@pytest.mark.asyncio
async def test_happy_path_returns_normalized_query_with_expected_fields() -> None:
    scripted = json.dumps(
        {
            "action": "normalize",
            "structured_query": "Tatalaksana cairan awal DBD derajat II pada anak",
            "condition_tags": ["dengue", "pediatric"],
            "intent": "tatalaksana",
            "patient_context": "pediatric",
            "keywords_id": ["DBD", "anak", "cairan", "kristaloid"],
            "keywords_en": ["dengue", "pediatric", "fluid resuscitation"],
            "red_flags": [],
        }
    )
    client = _scripted_client(text=scripted, input_tokens=128, output_tokens=64)
    normalizer = _make_normalizer(client)

    result = await normalizer.run(_state("DBD anak derajat 2, tata laksana cairan awal gimana?"))

    assert isinstance(result, NormalizedQuery)
    assert result.intent == "tatalaksana"
    assert result.patient_context == "pediatric"
    assert "dengue" in result.condition_tags
    assert "pediatric" in result.condition_tags
    assert "DBD" in result.keywords_id
    assert "dengue" in result.keywords_en
    assert "Tatalaksana" in result.structured_query  # Bahasa preserved

    [call] = client.messages.calls
    assert call["model"] == "claude-haiku-4-5-20251001"
    assert call["max_tokens"] == 800
    assert call["system"] == "SYSTEM_PROMPT_STUB"
    assert call["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_out_of_scope_query_returns_out_of_medical_scope_refusal() -> None:
    scripted = json.dumps({"action": "refuse", "reason": "out_of_medical_scope"})
    client = _scripted_client(text=scripted)
    normalizer = _make_normalizer(client)

    result = await normalizer.run(_state("Resep nasi goreng yang enak dong"))

    assert isinstance(result, NormalizerRefusal)
    assert result.reason == RefusalReason.OUT_OF_MEDICAL_SCOPE


@pytest.mark.asyncio
async def test_patient_specific_query_returns_patient_specific_refusal() -> None:
    scripted = json.dumps({"action": "refuse", "reason": "patient_specific_request"})
    client = _scripted_client(text=scripted)
    normalizer = _make_normalizer(client)

    result = await normalizer.run(
        _state("Pasien saya hamil 28 minggu, aman nggak dikasih amoksisilin 500mg?")
    )

    assert isinstance(result, NormalizerRefusal)
    assert result.reason == RefusalReason.PATIENT_SPECIFIC_REQUEST


@pytest.mark.asyncio
async def test_invalid_json_yields_malformed_refusal() -> None:
    client = _scripted_client(text="this is not JSON at all")
    normalizer = _make_normalizer(client)

    result = await normalizer.run(_state("DBD dewasa tata laksana"))

    assert isinstance(result, NormalizerRefusal)
    assert result.reason == RefusalReason.NORMALIZER_MALFORMED


@pytest.mark.asyncio
async def test_valid_json_missing_structured_query_yields_malformed() -> None:
    # `action: normalize` but missing the required `structured_query` field.
    scripted = json.dumps(
        {
            "action": "normalize",
            "intent": "tatalaksana",
            "patient_context": "adult",
        }
    )
    client = _scripted_client(text=scripted)
    normalizer = _make_normalizer(client)

    result = await normalizer.run(_state("anything"))

    assert isinstance(result, NormalizerRefusal)
    assert result.reason == RefusalReason.NORMALIZER_MALFORMED


@pytest.mark.asyncio
async def test_unknown_action_yields_malformed() -> None:
    scripted = json.dumps({"action": "ponder", "structured_query": "x"})
    client = _scripted_client(text=scripted)
    normalizer = _make_normalizer(client)

    result = await normalizer.run(_state("anything"))

    assert isinstance(result, NormalizerRefusal)
    assert result.reason == RefusalReason.NORMALIZER_MALFORMED


@pytest.mark.asyncio
async def test_refusal_with_unknown_reason_yields_malformed() -> None:
    # `action: refuse` but the reason isn't one we allow from the Normalizer.
    scripted = json.dumps({"action": "refuse", "reason": "corpus_silent"})
    client = _scripted_client(text=scripted)
    normalizer = _make_normalizer(client)

    result = await normalizer.run(_state("anything"))

    assert isinstance(result, NormalizerRefusal)
    assert result.reason == RefusalReason.NORMALIZER_MALFORMED


class _BoomAPIError(Exception):
    """Stand-in for an Anthropic transport failure."""


@pytest.mark.asyncio
async def test_anthropic_client_exception_propagates_not_swallowed() -> None:
    client = FakeAnthropic(messages=_FakeMessages(exc=_BoomAPIError("connection reset")))
    normalizer = _make_normalizer(client)

    with pytest.raises(_BoomAPIError, match="connection reset"):
        await normalizer.run(_state("DBD anak"))


@pytest.mark.asyncio
async def test_last_usage_populated_after_call() -> None:
    scripted = json.dumps(
        {
            "action": "normalize",
            "structured_query": "Dosis dewasa amoksisilin pneumonia",
            "condition_tags": ["community_acquired_pneumonia"],
            "intent": "dosage",
            "patient_context": "adult",
            "keywords_id": ["amoksisilin", "pneumonia"],
            "keywords_en": ["amoxicillin", "community acquired pneumonia"],
            "red_flags": [],
        }
    )
    client = _scripted_client(text=scripted, input_tokens=300, output_tokens=90)
    normalizer = _make_normalizer(client)

    assert normalizer.last_usage is None

    await normalizer.run(_state("dosis amoks dewasa untuk CAP"))

    assert normalizer.last_usage is not None
    assert normalizer.last_usage["input_tokens"] == 300
    assert normalizer.last_usage["output_tokens"] == 90
    assert normalizer.last_usage["model_id"] == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_last_usage_populated_even_when_malformed() -> None:
    client = _scripted_client(text="garbage", input_tokens=10, output_tokens=5)
    normalizer = _make_normalizer(client)

    result = await normalizer.run(_state("x"))

    assert isinstance(result, NormalizerRefusal)
    assert result.reason == RefusalReason.NORMALIZER_MALFORMED
    assert normalizer.last_usage == {
        "input_tokens": 10,
        "output_tokens": 5,
        "model_id": "claude-haiku-4-5-20251001",
    }


def test_constructor_requires_either_client_or_api_key() -> None:
    with pytest.raises(ValueError, match="anthropic_client"):
        HaikuNormalizer(system_prompt="stub")
