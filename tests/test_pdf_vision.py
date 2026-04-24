"""Tests for `tools.pdf_vision` — PDF text + vision extraction.

TDD spine for the ingestion layer. Verifies:
- `route()` correctly partitions a synthetic PDF into text-friendly pages
  and vision-required pages.
- `extract_text()` returns non-empty per-page text for the embedded-text
  page, with accurate char counts.
- `extract()` merges both paths with the Anthropic client patched out
  through the module-level `_anthropic_client_factory` seam. No real
  API calls happen in tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pytest

from tools import pdf_vision
from tools.pdf_vision import (
    ExtractionResult,
    PageText,
    extract,
    extract_text,
    route,
)

_TEXT_PAGE_CONTENT = (
    "Demam Berdarah Dengue (DBD) adalah penyakit yang disebabkan oleh virus dengue. "
    "Tanda dan gejala utama meliputi demam tinggi mendadak, nyeri kepala, nyeri "
    "retro-orbital, mialgia, artralgia, ruam, serta manifestasi perdarahan seperti "
    "petekie dan epistaksis. Pada pemeriksaan fisik dapat ditemukan hepatomegali dan "
    "tanda-tanda kebocoran plasma. Tata laksana DBD derajat II pada anak meliputi "
    "pemberian cairan kristaloid 6-7 ml/kg/jam sebagai terapi inisial, dengan evaluasi "
    "klinis dan hematokrit berkala. Kriteria rujukan termasuk syok, perdarahan masif, "
    "atau penurunan kesadaran yang tidak dapat ditangani di FKTP."
)


def _build_synthetic_pdf(path: Path) -> None:
    """Build a 2-page PDF: page 1 embedded text, page 2 rasterized image.

    Page 2 contains a bitmap-rendered image only — pdfplumber sees (near-)
    no text, simulating a scanned page that should be routed to vision.
    """
    doc = fitz.open()

    page1 = doc.new_page(width=595, height=842)  # A4
    rect = fitz.Rect(50, 50, 545, 792)
    page1.insert_textbox(rect, _TEXT_PAGE_CONTENT, fontsize=11, fontname="helv")

    # Page 2: rasterize a small image of some text into the page so pdfplumber
    # finds nothing selectable. Render the text page as a pixmap, then embed
    # it as an image on page 2.
    pix = page1.get_pixmap(dpi=72)
    img_bytes = pix.tobytes("png")
    page2 = doc.new_page(width=595, height=842)
    page2.insert_image(fitz.Rect(50, 50, 545, 792), stream=img_bytes)

    doc.save(str(path))
    doc.close()


class _FakeMessage:
    def __init__(self, text: str) -> None:
        class _Block:
            def __init__(self, t: str) -> None:
                self.type = "text"
                self.text = t

        self.content = [_Block(text)]
        self.usage = type(
            "U", (), {"input_tokens": 1200, "output_tokens": 800, "cache_read_input_tokens": 0}
        )()


class _FakeMessages:
    def __init__(self, transcription: str) -> None:
        self._transcription = transcription
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return _FakeMessage(self._transcription)


class _FakeAnthropic:
    def __init__(self, transcription: str) -> None:
        self.messages = _FakeMessages(transcription)


def test_route_sends_text_page_to_text_and_scanned_page_to_vision(tmp_path: Path) -> None:
    pdf = tmp_path / "synthetic.pdf"
    _build_synthetic_pdf(pdf)

    plan = route(pdf, text_threshold_chars_per_page=250)

    # Page 1 carries real text; page 2 is a rasterized image with ~nothing.
    assert plan.pages_for_text == [1]
    assert plan.pages_for_vision == [2]
    assert plan.total_pages == 2


def test_route_threshold_lower_bound_treats_low_text_as_vision(tmp_path: Path) -> None:
    """Set an absurdly high threshold so even the text page routes to vision."""
    pdf = tmp_path / "synthetic.pdf"
    _build_synthetic_pdf(pdf)

    plan = route(pdf, text_threshold_chars_per_page=100_000)

    assert plan.pages_for_text == []
    assert sorted(plan.pages_for_vision) == [1, 2]


def test_extract_text_returns_embedded_text_for_text_page(tmp_path: Path) -> None:
    pdf = tmp_path / "synthetic.pdf"
    _build_synthetic_pdf(pdf)

    pages = extract_text(pdf, pages=[1])

    assert len(pages) == 1
    page = pages[0]
    assert page.page == 1
    # pdfplumber reconstructs the textbox layout; allow substring match on key
    # Bahasa fragments rather than exact whitespace equality.
    assert "DBD" in page.text or "Demam Berdarah Dengue" in page.text
    assert "kristaloid" in page.text
    assert page.chars == len(page.text)
    assert page.source == "text"


def test_extract_text_returns_near_empty_for_scanned_page(tmp_path: Path) -> None:
    pdf = tmp_path / "synthetic.pdf"
    _build_synthetic_pdf(pdf)

    pages = extract_text(pdf, pages=[2])

    assert len(pages) == 1
    # Rasterized page: non-whitespace char count should be well under the
    # default routing threshold.
    non_ws = sum(1 for c in pages[0].text if not c.isspace())
    assert non_ws < 250


def test_extract_merges_text_and_vision_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "synthetic.pdf"
    _build_synthetic_pdf(pdf)

    canned = (
        "Halaman 2 (vision) — Tata laksana DBD derajat II: cairan kristaloid "
        "6-7 ml/kg/jam. Evaluasi hematokrit berkala."
    )
    fake = _FakeAnthropic(canned)

    def _factory(api_key: str) -> _FakeAnthropic:
        return fake

    monkeypatch.setattr(pdf_vision, "_anthropic_client_factory", _factory)

    result = extract(
        pdf,
        api_key="sk-test-not-real",
        text_threshold_chars_per_page=250,
    )

    assert isinstance(result, ExtractionResult)
    assert [p.page for p in result.pages] == [1, 2]

    page1 = result.pages[0]
    assert page1.source == "text"
    assert "kristaloid" in page1.text

    page2 = result.pages[1]
    assert page2.source == "vision"
    assert "kristaloid" in page2.text
    assert "vision" in page2.text.lower()

    assert len(fake.messages.calls) == 1
    call = fake.messages.calls[0]
    assert call["model"].startswith("claude-opus-4")
    assert "system" in call
    assert "Bahasa" in call["system"] or "bahasa" in call["system"].lower()
    content_parts = call["messages"][0]["content"]
    types = {part.get("type") for part in content_parts}
    assert "image" in types
    assert "text" in types

    report = result.report
    assert report.total_pages == 2
    assert report.text_pages == 1
    assert report.vision_pages == 1
    assert report.chars_total > 0
    assert report.vision_cost_tokens_est > 0


def test_extract_without_api_key_but_no_vision_pages_skips_anthropic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If every page routes to text, extract() must NOT require an api_key."""
    pdf = tmp_path / "text_only.pdf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(
        fitz.Rect(50, 50, 545, 792), _TEXT_PAGE_CONTENT, fontsize=11, fontname="helv"
    )
    doc.save(str(pdf))
    doc.close()

    def _boom(api_key: str) -> Any:
        raise AssertionError("Anthropic client must not be constructed when no vision pages.")

    monkeypatch.setattr(pdf_vision, "_anthropic_client_factory", _boom)

    result = extract(pdf, api_key=None, text_threshold_chars_per_page=250)

    assert result.report.vision_pages == 0
    assert result.report.text_pages == 1
    assert [p.source for p in result.pages] == ["text"]


def test_page_text_is_one_indexed_and_ordered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pages must be 1-indexed and the merged list ordered by page number."""
    pdf = tmp_path / "synthetic.pdf"
    _build_synthetic_pdf(pdf)

    fake = _FakeAnthropic("canned vision")
    monkeypatch.setattr(pdf_vision, "_anthropic_client_factory", lambda _k: fake)

    result = extract(pdf, api_key="x", text_threshold_chars_per_page=250)

    pages = [p.page for p in result.pages]
    assert pages == sorted(pages)
    assert pages[0] == 1
    assert all(isinstance(p, PageText) for p in result.pages)
