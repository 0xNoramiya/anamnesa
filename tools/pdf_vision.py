"""PDF text + vision extraction with routing.

Anamnesa's ingestion layer has two paths:

1. **Text path (pdfplumber).** Most Kemenkes PDFs (PNPK, many PPK FKTP
   sections, Fornas) carry selectable text. pdfplumber is fast, free, and
   preserves Bahasa verbatim.
2. **Vision path (Opus 4.7).** PPK FKTP 2015 contains scanned pages and
   rasterized tables where pdfplumber pulls nothing. Those pages render to
   PNG and are transcribed by Opus with a Bahasa-preserving system prompt.

`route()` decides per-page which path to use. `extract()` dispatches both
paths and merges the per-page output ordered by 1-indexed page number, so
downstream chunking and `Chunk.page` values align with `pdfinfo` and MCP
`get_pdf_page_url` tool URLs.

This module intentionally has no import-time side effects. The Anthropic
client is built inside `extract_vision` via `_anthropic_client_factory`,
which tests monkeypatch to avoid real API calls.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import fitz  # PyMuPDF
import pdfplumber
import structlog
from pydantic import BaseModel, ConfigDict, Field

log = structlog.get_logger("anamnesa.pdf_vision")

# Opus 4.7 default for trust-critical vision transcription (see CLAUDE.md
# "Model routing"). Callers can override via `model_id`.
DEFAULT_VISION_MODEL = "claude-opus-4-7"

# Rough token accounting (200 DPI A4 image ~= 1600 input tokens; prompt adds
# ~1500; output budget per page ~1200). Used for the aggregate cost estimate;
# NOT authoritative — the Anthropic API response carries the real number.
_IMAGE_TOKENS_PER_PAGE = 1600
_PROMPT_TOKENS_PER_PAGE = 1500
_OUTPUT_TOKENS_PER_PAGE = 1200

# Small, bounded retry for transient Anthropic failures (429 / 529 overloaded).
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1.5

VISION_SYSTEM_PROMPT = (
    "Anda adalah asisten OCR klinis untuk Anamnesa. Tugas Anda adalah "
    "menyalin isi halaman PDF pedoman klinis Indonesia dalam Bahasa "
    "Indonesia, SECARA VERBATIM, tanpa menerjemahkan ke bahasa Inggris.\n\n"
    "Aturan wajib:\n"
    "1. Pertahankan istilah klinis Indonesia apa adanya (DBD, tata laksana, "
    "anamnesis, pemeriksaan fisik, kriteria rujukan, tatalaksana, dosis, "
    "gagal jantung, dst). JANGAN terjemahkan ke bahasa Inggris.\n"
    "2. Pertahankan singkatan Indonesia yang umum dipakai dokter (DBD, TB, "
    "HT, DM, PPOK, ISPA, dst) persis seperti di dokumen.\n"
    "3. Ubah tabel menjadi tabel markdown; pertahankan header dan nilai apa "
    "adanya. Jangan meringkas atau mengubah angka.\n"
    "4. Pertahankan heading, nomor bagian, bullet, dan urutan paragraf "
    "sesuai dengan halaman sumber.\n"
    "5. Jika ada bagian halaman yang tidak terbaca, tulis '[tidak terbaca]' "
    "pada posisi tersebut. JANGAN menebak atau merekayasa isi.\n"
    "6. JANGAN menambahkan komentar, ringkasan, atau catatan Anda sendiri. "
    "Keluarkan hanya hasil transkripsi halaman.\n"
)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class PageSource(StrEnum):
    TEXT = "text"
    VISION = "vision"


class PageText(BaseModel):
    """Per-page extracted text with provenance of the extraction path."""

    model_config = ConfigDict(frozen=True)

    page: int  # 1-indexed, matches Chunk.page and pdfinfo
    text: str
    chars: int
    source: PageSource


class ExtractionPlan(BaseModel):
    """Routing decision: which pages go through pdfplumber vs Opus vision."""

    model_config = ConfigDict(frozen=True)

    total_pages: int
    pages_for_text: list[int]
    pages_for_vision: list[int]


class ExtractionReport(BaseModel):
    """Aggregate stats for one PDF extraction."""

    model_config = ConfigDict(frozen=True)

    total_pages: int
    text_pages: int
    vision_pages: int
    chars_total: int
    vision_cost_tokens_est: int


class ExtractionResult(BaseModel):
    """Merged per-page output + aggregate report."""

    model_config = ConfigDict(frozen=True)

    pages: list[PageText] = Field(default_factory=list)
    report: ExtractionReport


# ---------------------------------------------------------------------------
# Anthropic client seam — tests monkeypatch this to avoid real API calls.
# ---------------------------------------------------------------------------


class _AnthropicClient(Protocol):
    messages: Any


def _anthropic_client_factory(api_key: str) -> _AnthropicClient:
    """Build a real Anthropic client. Tests monkeypatch this symbol."""
    import anthropic  # local import: keep import-time side effects out of module load

    return anthropic.Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _non_whitespace_len(s: str) -> int:
    return sum(1 for c in s if not c.isspace())


def route(pdf_path: Path, *, text_threshold_chars_per_page: int = 250) -> ExtractionPlan:
    """Inspect the PDF and decide per-page between text and vision.

    Rule: if pdfplumber pulls at least `text_threshold_chars_per_page`
    non-whitespace characters from a page, the page is routed to the text
    path. Otherwise the page is routed to the vision path. Threshold is
    conservative (err toward vision on ambiguous pages — the cost of a
    Ctrl-F miss downstream is much higher than one extra Opus call).
    """
    pages_for_text: list[int] = []
    pages_for_vision: list[int] = []
    total: int

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            chars = _non_whitespace_len(text)
            if chars >= text_threshold_chars_per_page:
                pages_for_text.append(idx)
                decision = "text"
            else:
                pages_for_vision.append(idx)
                decision = "vision"
            log.info(
                "route_decision",
                pdf=str(pdf_path),
                page=idx,
                non_ws_chars=chars,
                threshold=text_threshold_chars_per_page,
                decision=decision,
            )

    return ExtractionPlan(
        total_pages=total,
        pages_for_text=pages_for_text,
        pages_for_vision=pages_for_vision,
    )


# ---------------------------------------------------------------------------
# Text path (pdfplumber)
# ---------------------------------------------------------------------------


def extract_text(pdf_path: Path, pages: Sequence[int] | None = None) -> list[PageText]:
    """pdfplumber fast path. Returns `PageText` per requested page.

    `pages` is a list of 1-indexed page numbers. `None` means all pages.
    """
    out: list[PageText] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        wanted = list(pages) if pages is not None else list(range(1, total + 1))
        for page_num in wanted:
            if page_num < 1 or page_num > total:
                raise PdfVisionError(
                    f"page {page_num} out of range (pdf has {total} pages)"
                )
            text = pdf.pages[page_num - 1].extract_text() or ""
            out.append(
                PageText(
                    page=page_num,
                    text=text,
                    chars=len(text),
                    source=PageSource.TEXT,
                )
            )
            log.info(
                "extract_text_page",
                pdf=str(pdf_path),
                page=page_num,
                chars=len(text),
            )
    return out


# ---------------------------------------------------------------------------
# Vision path (PyMuPDF render + Anthropic messages API)
# ---------------------------------------------------------------------------


def _render_page_png(pdf_path: Path, page_num: int, dpi: int) -> bytes:
    """Render a single 1-indexed page to a PNG byte string at the given DPI."""
    doc = fitz.open(str(pdf_path))
    try:
        if page_num < 1 or page_num > doc.page_count:
            raise PdfVisionError(
                f"page {page_num} out of range (pdf has {doc.page_count} pages)"
            )
        page = doc.load_page(page_num - 1)
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    finally:
        doc.close()


def _transcribe_page_with_retry(
    client: _AnthropicClient,
    *,
    png_bytes: bytes,
    model_id: str,
) -> tuple[str, dict[str, int]]:
    """Call Anthropic messages.create with small retry on transient failure."""
    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    user_content: list[dict[str, Any]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": b64,
            },
        },
        {
            "type": "text",
            "text": (
                "Transkripsikan halaman ini secara verbatim dalam Bahasa "
                "Indonesia. Ikuti aturan di system prompt."
            ),
        },
    ]

    last_err: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model=model_id,
                max_tokens=_OUTPUT_TOKENS_PER_PAGE,
                system=VISION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            text = _join_text_blocks(resp.content)
            usage = _extract_usage(getattr(resp, "usage", None))
            return text, usage
        except Exception as exc:
            last_err = exc
            retriable = _is_retriable(exc)
            log.warning(
                "vision_call_error",
                attempt=attempt,
                retriable=retriable,
                error=str(exc),
            )
            if not retriable or attempt == _MAX_RETRIES:
                break
            time.sleep(_BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    assert last_err is not None
    raise PdfVisionError(f"Anthropic vision call failed: {last_err}") from last_err


def _is_retriable(exc: Exception) -> bool:
    """Crude retriability check covering 429 / 529 / connection timeout."""
    status = getattr(exc, "status_code", None)
    if status in (408, 409, 425, 429, 500, 502, 503, 504, 529):
        return True
    name = type(exc).__name__.lower()
    return any(tag in name for tag in ("overload", "timeout", "connection", "ratelimit"))


def _join_text_blocks(blocks: Any) -> str:
    parts: list[str] = []
    for block in blocks or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(getattr(block, "text", "") or "")
    return "\n".join(parts).strip()


def _extract_usage(usage: Any) -> dict[str, int]:
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0}
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }


def extract_vision(
    pdf_path: Path,
    pages: Sequence[int],
    *,
    model_id: str = DEFAULT_VISION_MODEL,
    api_key: str,
    dpi: int = 200,
) -> list[PageText]:
    """Render each page to PNG and send to Anthropic for Bahasa transcription."""
    if not pages:
        return []
    client = _anthropic_client_factory(api_key)
    out: list[PageText] = []
    for page_num in pages:
        png_bytes = _render_page_png(pdf_path, page_num, dpi=dpi)
        text, usage = _transcribe_page_with_retry(
            client,
            png_bytes=png_bytes,
            model_id=model_id,
        )
        out.append(
            PageText(
                page=page_num,
                text=text,
                chars=len(text),
                source=PageSource.VISION,
            )
        )
        log.info(
            "extract_vision_page",
            pdf=str(pdf_path),
            page=page_num,
            chars=len(text),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
    return out


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def extract(
    pdf_path: Path,
    *,
    api_key: str | None = None,
    model_id: str = DEFAULT_VISION_MODEL,
    dpi: int = 200,
    text_threshold_chars_per_page: int = 250,
) -> ExtractionResult:
    """Route, dispatch text + vision, merge, and emit an aggregate report."""
    plan = route(pdf_path, text_threshold_chars_per_page=text_threshold_chars_per_page)

    text_pages = (
        extract_text(pdf_path, pages=plan.pages_for_text) if plan.pages_for_text else []
    )

    vision_pages: list[PageText] = []
    if plan.pages_for_vision:
        if api_key is None:
            raise PdfVisionError(
                "api_key required: PDF has vision-routed pages but no Anthropic key given. "
                f"pages_for_vision={plan.pages_for_vision}"
            )
        vision_pages = extract_vision(
            pdf_path,
            plan.pages_for_vision,
            model_id=model_id,
            api_key=api_key,
            dpi=dpi,
        )

    merged = sorted([*text_pages, *vision_pages], key=lambda p: p.page)
    chars_total = sum(p.chars for p in merged)
    vision_cost = len(plan.pages_for_vision) * (
        _IMAGE_TOKENS_PER_PAGE + _PROMPT_TOKENS_PER_PAGE + _OUTPUT_TOKENS_PER_PAGE
    )

    report = ExtractionReport(
        total_pages=plan.total_pages,
        text_pages=len(plan.pages_for_text),
        vision_pages=len(plan.pages_for_vision),
        chars_total=chars_total,
        vision_cost_tokens_est=vision_cost,
    )
    log.info(
        "extract_report",
        pdf=str(pdf_path),
        total_pages=report.total_pages,
        text_pages=report.text_pages,
        vision_pages=report.vision_pages,
        chars_total=report.chars_total,
        vision_cost_tokens_est=report.vision_cost_tokens_est,
    )
    return ExtractionResult(pages=merged, report=report)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PdfVisionError(RuntimeError):
    """Raised on PDF read / routing / vision-call failure."""
