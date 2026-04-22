# Anamnesa

**Built for:** Built-with-Opus-4.7 Claude Code hackathon, 21–27 April 2026
**Problem statement:** PS1 — *Build From What You Know*
**Demo:** https://anamnesa.kudaliar.id
**Repo:** https://github.com/0xNoramiya/anamnesa
**Author:** Rifqi — emergency physician / GP, Banjarmasin, South Kalimantan

---

## The one-liner

Indonesian clinical-guideline retrieval agent that answers Bahasa
queries with verified citations to Indonesia's public-domain Kemenkes
corpus, flags outdated recommendations, and refuses cleanly when the
corpus is silent.

---

## Why it exists

I'm an ED physician in Banjarmasin. Every shift I hit the same friction:
a clinical scenario I haven't seen in months, the current Indonesian
guideline is buried in a Kemenkes PDF, and I'm Ctrl-F'ing through 900
pages on my phone while the patient waits.

The tools that exist — UpToDate, DynaMed, AMBOSS — are **English-only,
~USD 499/year**, roughly 1.5–2.5× a Puskesmas GP's monthly base salary.
None of them cover Indonesian national guidelines or BPJS Fornas. Most
Indonesian doctors outside tertiary centers use no reference tool at
all. They rely on memory, WhatsApp groups, and whoever's on call.

Anamnesa is my attempt to replace that 3am Ctrl-F session.

---

## Headline claims (measured, not estimated)

| | |
|---|---|
| **Eval pass rate** | **20 / 20 (100%)** on 20 ED/GP scenarios drawn from my actual shifts |
| **Hallucinated citations** | **0** across every run to date |
| **Corpus ingested** | **80 documents, 8,864 structured chunks** — PPK FKTP 2015 + 2022 (both Lampiran I condition PPKs **and** Lampiran II procedural skills) + 78 PNPKs from the Kemenkes archive |
| **Retrieval quality** | Hybrid BGE-M3 (1,024-dim multilingual) + rank-bm25, reciprocal-rank fusion, 1M-context Verifier re-read |
| **Legal basis** | UU No. 28/2014 Pasal 42 — every cited document is Kepmenkes-adopted and therefore public domain |

---

## What it does

### Mode 1 — Cari Cepat (fast search)

pasal.id-style live search straight over the indexed corpus. **No LLM,
~50 ms per query, $0 cost.** Matching chunks stream back grouped by
document with hit counts. Click a result → the PDF opens at the exact
page in a modal viewer. Use it when you just need to know *which
guideline says X* and read it yourself.

### Mode 2 — Mode Agen (agentic RAG)

Full four-agent pipeline for synthesis:

1. **Normalizer** (Haiku 4.5) — turns colloquial Bahasa into a
   structured query; refuses clearly when out of medical scope or when
   the user asks for per-patient dosing decisions.
2. **Retriever** — MCP-tool-exposed LanceDB + BM25 hybrid; no LLM.
3. **Drafter** (Opus 4.7, adaptive thinking, xhigh effort) — composes a
   cited Bahasa answer via tool-use. Can self-loop with narrower
   retrieval if the initial chunks are insufficient. **MUST NOT invent
   citations.**
4. **Verifier** (Opus 4.7, 1M context) — independently re-reads every
   cited chunk, classifies each claim as `supported | partial |
   unsupported`, calls `check_supersession` on every `doc_id` to attach
   a currency flag (`current | aging | superseded | withdrawn`).
   If any claim is unsupported the Drafter gets **one** retry; after
   that the whole answer is refused.

Every agent event streams to the UI as a live trace while the user
watches — normalizer → retriever → drafter → verifier, colour-coded
per agent. Without this panel, the agentic work is invisible and the
product looks like a ChatGPT clone.

Total wall-clock on a typical Mode Agen query: ~150 seconds. Cost:
$0.40–0.80 per answer at Opus rates.

---

## Three demo queries that land cleanly

Try these on https://anamnesa.kudaliar.id — switch to **Mode Agen** for
#1 and #2, **Cari Cepat** for #3.

1. **Colloquial Bahasa → grounded answer**
   > "Bayi baru lahir tidak menangis, apnea, HR <100. Langkah resusitasi awal dalam 60 detik pertama?"

   Returns a 6-citation answer grounded in PNPK Asfiksia 2019 + PNPK
   Resusitasi & Stabilisasi BBLR 2018, walking the Menit-Emas algorithm
   with specific FiO₂ targets (21% ≥36 wk gestation; 21–30% <35 wk),
   EKG preferred over pulse ox when LJ is weak, VTP indications (apnea
   OR gasping OR LJ <100/menit). Opens with an honest aging caveat
   because both source PNPKs are ≥5 years old.

2. **Aging + superseded flag working together**
   > "Pasien TB paru dewasa baru BTA positif. Rejimen OAT lini pertama dan durasi?"

   Returns 2RHZE/4RH grounded in PNPK TB 2019 (flagged **aging**) —
   with an explicit currency banner. When a 2015 PPK FKTP chunk also
   surfaces, the Verifier's `check_supersession` marks it **superseded**
   by PPK FKTP 2022, and the draft leans on the 2022 equivalent
   instead.

3. **Corpus silent → clean refusal** (Mode Agen)
   > "Skor HAS-BLED untuk menilai risiko perdarahan pada pasien fibrilasi atrium non-valvular — komponen dan interpretasi menurut pedoman Indonesia?"

   Returns a clear Bahasa refusal: *"Anamnesa tidak menemukan pedoman
   Indonesia yang relevan untuk skenario ini."* HAS-BLED is a real
   clinical score the model knows from training — but it's not in any
   Indonesian PNPK, and Anamnesa's trust contract is to refuse rather
   than fall back on model-internal knowledge. **This is the killer
   feature.** The product's value is provenance, not plausibility.

---

## What this isn't

- **Not a medical device.** Not BPOM-registered. Reference use only.
- **Not patient-specific decision support.** Anamnesa provides
  guideline references, not "should I give this dose to this patient."
  If the query mentions "pasien saya" or "boleh saya kasih" it refuses.
- **Not complete.** 80 documents is broad but not exhaustive; the
  perhimpunan konsensus not adopted as PNPK are copyrighted and
  explicitly deferred.
- **Not a replacement for clinical judgment.** Every answer carries a
  disclaimer to that effect.

---

## Architecture one-liner

Next.js 14 → FastAPI → Orchestrator (budget-guarded, async) → {Haiku
Normalizer · LanceDB+BM25 Retriever via `anamnesa-mcp` · Opus Drafter
(tool-use loop) · Opus Verifier (1M ctx tool-use loop)} → SSE back to
the browser. Prompt caching on system blocks; BGE-M3 lazy-loaded on
CUDA in dev, CPU in prod. Everything behind nginx + Let's Encrypt on
a VPS.

---

## Open work (7-day build has edges)

- **Cost.** Currently $0.40–$0.80/query, over CLAUDE.md's stated $0.20
  target. Achievable by Haiku'ing some Verifier partials and aggressive
  prompt caching. Not done for the hackathon.
- **Watermark bleed.** Some PDFs carry diagonal rotated watermarks
  that pdfplumber interleaves into text, producing cosmetic slug noise
  on Lampiran II chunks. Body-text content still recoverable; the
  PyMuPDF rotated-char filter that cleaned Lampiran I should be
  retrofitted here.
- **q010 apnea-of-prematurity.** The corpus genuinely lacks a PNPK for
  this condition with caffeine/methylxanthine dosing. Currently
  correctly refused. Would be a great addition if the perhimpunan
  konsensus route opens up.

---

## Stack

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind, Fraunces +
  IBM Plex. Pasal.id-style palette (paper cream → civic blue, status
  badges for regulation currency).
- **Backend:** FastAPI 0.136, Pydantic v2, structlog, sse-starlette.
- **Retrieval:** LanceDB 0.14 + rank-bm25 + sentence-transformers BGE-M3.
- **Agents:** Anthropic Python SDK 0.40, Opus 4.7 (adaptive thinking +
  xhigh effort) for Drafter + Verifier, Haiku 4.5 for Normalizer.
- **Corpus:** 79 Pasal-42 PDFs from kemkes.go.id + IDI Semarang,
  committed to GitHub as structured chunks (PDFs themselves gitignored
  to keep the repo light — regenerable via `agents/prompts/crawler.md`).
- **Deploy:** Ubuntu 22.04, nginx (SSE-safe proxy config), systemd
  services, Let's Encrypt auto-renew, no Cloudflare proxy (100-second
  timeout would cut Mode Agen streams short).
- **Tests:** 120 passing. Ruff clean.

---

## Links

- **Live demo:** https://anamnesa.kudaliar.id
- **Source:** https://github.com/0xNoramiya/anamnesa
- **Eval status:** [EVAL_STATUS.md](./EVAL_STATUS.md)
- **Design doc:** [CLAUDE.md](./CLAUDE.md) — the single source of
  truth the Claude Code build agent anchored to throughout the week.
