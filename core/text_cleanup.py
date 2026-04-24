"""Render-time cleanup of PDF-extraction noise in guideline chunks.

Kemenkes guideline PDFs carry a vertical "KEMENTERIAN KESEHATAN"
watermark. pdfplumber inlines each watermark glyph as noise:

  - Single-letter lines interleaved with prose ("K", "N", "R", "E"…)
  - Glyphs spliced into the middle of words: "pasti" → "pastAi",
    "kontribusi" → "kontEribusi", "angka" → "anAgka".
  - Header lines carrying a trailing/leading watermark:
    "BAB I E" where only "BAB I" is the real heading.
  - Page-number footers ("-25-") and URL footers
    ("jdih.kemkes.go.id") injected between paragraphs.

Critical constraint: many medical-dense tokens look like splices but
ARE the canonical form:

  - mmHg, mEq, kPa, cGy, mOsm — clinical units
  - NaCl, HBsAg, HBeAg, CrCl — standard abbreviations
  - BRAFV600E, HOX11L2, PIK3CA, ERBB2 — gene/mutation codes
  - 2HRZE/4H3R3 — TB OAT regimen codes

The alpha splice rule therefore only fires when the containing
ALPHABETIC word (digits treated as boundaries) is ≥6 chars AND has
exactly one uppercase letter. The earlier digit-cap-digit rule was
dropped entirely after a catalog audit showed 200 medical-code false
positives vs 5 legitimate watermark year fixes.

This cleanup runs at two boundaries:

  1. Guideline HTML/Markdown renderers in server/main.py, so human
     readers see clean prose.
  2. Retriever responses in core/retrieval.py, so the Drafter agent
     doesn't quote watermark noise into generated answers.

Raw catalog chunks stay untouched — a future re-ingestion pipeline
using column-aware PDF extraction can eventually replace this
heuristic layer.
"""
from __future__ import annotations

import re

_OCR_SPLICE_ALPHA_RE = re.compile(r"([a-z])([A-Z])([a-z])")
_OCR_PAGE_FOOTER_RE = re.compile(r"^\s*-\s*\d+\s*-\s*$")
_OCR_URL_FOOTER_RE = re.compile(r"^\s*(?:www\.)?[a-z]+\.kemkes\.go\.id\s*$", re.I)
_OCR_LONE_CAP_RE = re.compile(r"^\s*[A-Z]\s*$")
_OCR_MULTI_BLANK_RE = re.compile(r"\n{3,}")
# Trailing/leading cap: "BAB I E" → "BAB I". Excludes I/V/X/L/C/D/M so roman
# numerals on legitimate section headers survive.
_OCR_TRAILING_CAP_RE = re.compile(r" ([A-HJKN-UW-Z])$", re.M)
_OCR_LEADING_CAP_RE = re.compile(r"^([A-HJKN-UW-Z]) ", re.M)


def _fix_word_splice(s: str) -> str:
    """Remove watermark-letter splices from Indonesian prose.

    Skips medical abbreviations by requiring the containing alphabetic word
    (digits treated as boundaries) to be ≥6 chars AND have exactly one
    uppercase letter.
    """

    def walk_word(start: int, end: int) -> tuple[int, int]:
        ws = start
        while ws > 0 and s[ws - 1].isalpha():
            ws -= 1
        we = end
        while we < len(s) and s[we].isalpha():
            we += 1
        return ws, we

    def sub(match: re.Match[str]) -> str:
        ws, we = walk_word(match.start(), match.end())
        word = s[ws:we]
        cap_count = sum(1 for ch in word if ch.isupper())
        if cap_count != 1 or len(word) < 6:
            return match.group(0)
        return match.group(1) + match.group(3)

    return _OCR_SPLICE_ALPHA_RE.sub(sub, s)


def clean_guideline_text(s: str) -> str:
    """Strip PDF-extraction noise from a single chunk's text.

    Cheap, pure, deterministic — safe to call on every retrieval.
    """
    if not s:
        return s
    s = _fix_word_splice(s)
    out: list[str] = []
    for line in s.splitlines():
        # Trim dangling watermark letters first so "-25- N" (footer + watermark)
        # becomes "-25-" and is then caught by the footer drop-check below.
        for _ in range(3):
            new_line = _OCR_TRAILING_CAP_RE.sub("", line)
            new_line = _OCR_LEADING_CAP_RE.sub("", new_line)
            if new_line == line:
                break
            line = new_line
        if _OCR_PAGE_FOOTER_RE.match(line):
            continue
        if _OCR_URL_FOOTER_RE.match(line):
            continue
        if _OCR_LONE_CAP_RE.match(line):
            continue
        out.append(line)
    cleaned = "\n".join(out)
    cleaned = _OCR_MULTI_BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()


_ROMAN_NUMERALS = frozenset(
    {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"}
)
_VOWELS = frozenset("aeiou")
# Short medical acronyms with vowels that would otherwise miss the all-consonant
# rule. Kept small — adding too many risks collisions with Indonesian words
# ("anak", "obat").
_MEDICAL_ACRONYMS = frozenset({
    "hiv", "aids", "tbc", "icu", "igd", "oat", "ppi", "nsaid", "ppk",
    "ppok", "dbd", "dss", "ska", "stemi", "nstemi",
})


def _beautify_segment(seg: str) -> str:
    """Title-case a slug segment; upper-case roman numerals, all-consonant 2-5
    char tokens (DBD, TB, PGK), and listed medical acronyms (HIV, ICU, IGD)."""
    s = seg.strip()
    if not s:
        return ""
    lo = s.lower()
    if lo in _ROMAN_NUMERALS:
        return lo.upper()
    if lo in _MEDICAL_ACRONYMS:
        return lo.upper()
    if 2 <= len(lo) <= 5 and lo.isalpha() and not any(ch in _VOWELS for ch in lo):
        return lo.upper()
    return s.capitalize()


def beautify_slug(slug: str) -> str:
    """Turn a system slug 'latar-belakang' into 'Latar Belakang'.

    Returns '' for junk slugs (single letter, or short fragments from the
    watermark-letter extraction bug) so the renderer can skip emitting a header.
    """
    s = slug.strip()
    if not s:
        return ""
    lo = s.lower()
    # Whitelist standalone roman numerals (≤2 chars: "i", "v", "x") that would
    # otherwise be dropped by the junk-filter below.
    if lo in _ROMAN_NUMERALS:
        return lo.upper()
    if len(s) <= 2 and "-" not in s and "_" not in s:
        return ""
    parts = re.split(r"[-_]", s)
    return " ".join(_beautify_segment(p) for p in parts if p)
