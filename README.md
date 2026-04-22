# Anamnesa

**Indonesian clinical-guideline retrieval agent.** Answers Bahasa Indonesia
clinical queries with grounded citations to Indonesia's public-domain
guideline corpus (PPK FKTP, PNPK, Kemenkes pedoman program). Every
recommendation carries a currency flag. When the corpus is silent,
Anamnesa refuses cleanly rather than hallucinating.

Built for **Built-with-Opus-4.7 Claude Code hackathon (21–27 April 2026)**,
Problem Statement 1 — *Build From What You Know.* Primary user and
original author: Rifqi, emergency physician / GP in Banjarmasin,
South Kalimantan.

---

## Why this exists

Existing English-only clinical decision support tools cost ~USD 499/year
— roughly 1.5–2.5× an entry-level Puskesmas GP's monthly base salary —
and don't cover Indonesian national guidelines. Most Indonesian doctors
outside tertiary centers rely on memory, WhatsApp groups, and whoever's
on call. Anamnesa replaces the 3am phone-Ctrl-F session through a
Kemenkes PDF with a cited, currency-flagged answer in a web UI built
for a physician reading it on shift.

Legal basis: **UU No. 28/2014 Pasal 42** removes copyright from
*peraturan perundang-undangan* and *keputusan pejabat Pemerintah*.
Every PNPK, PPK FKTP, and Kemenkes pedoman is a Lampiran of a Kepmenkes
and therefore public domain. The corpus, manifest, and processed chunks
are committed to this repo.

---

## What it does

Two surfaces:

| Mode | Path | Cost | Latency | Use for |
|---|---|---|---|---|
| **Cari Cepat** (fast search) | `GET /api/search?q=…` | $0 (no LLM) | ~50 ms | "Which PDF says X?" |
| **Mode Agen** (agentic RAG) | `POST /api/query` + SSE `/api/stream/{id}` | ~$0.40–0.60 | ~150 s | "Synthesize + cite + flag currency" |

Mode Agen runs four agents in a controlled loop:

1. **Normalizer** — Haiku 4.5. Colloquial Bahasa → structured query.
2. **Retriever** — Hybrid BGE-M3 (vector) + rank-bm25, reciprocal-rank
   fusion. No LLM.
3. **Drafter** — Opus 4.7 with adaptive thinking + xhigh effort.
   Composes a cited Bahasa answer via tool-use (`search_guidelines`,
   `get_full_section`, `submit_decision`).
4. **Verifier** — Opus 4.7 with 1M ctx. Re-reads every cited chunk,
   classifies claims `supported | partial | unsupported`, attaches
   currency flags (`current | aging | superseded | withdrawn`). Fails
   closed on malformed output.

Every event from every agent streams into the UI as a live trace.

---

## Current state (2026-04-22)

**Corpus:** 79 PDFs crawled (PPK FKTP 2015 + 78 PNPKs from kemkes.go.id).
25 ingested → **2,461 chunks** committed to `catalog/processed/`.

**Retrieval:** LanceDB + rank-bm25, BGE-M3 (1024-dim) vectors on CUDA.

**Eval:** 20 queries drawn from Banjarmasin ED/GP scenarios.
**19/20 pass (95%)**, **0 hallucinated citations** across all runs.
Breakdown: `grounded 11/14 · aging 3/3 · absent 3/3`.

The one remaining failure (`q011` preeklampsia) is a known retrieval-
granularity issue on the concatenated 4-sub-PNPK
`pnpk-komplikasi-kehamilan-2017`, not a hallucination.

**Demo scenarios from CLAUDE.md:**
- ✅ Colloquial Bahasa → cited answer (`q001` neonatal Menit-Emas)
- ✅ Aging guideline correctly flagged (`q016` TB OAT 2019 paduan 2RHZE/4RH)
- ✅ Absent-corpus refusal (`q019` HAS-BLED score)

**Tests:** 120 passing. Ruff clean.

---

## Run locally

Requirements: Python 3.12, Node 20+, an Anthropic API key, and
optionally a CUDA GPU for faster BGE-M3 reindex.

```bash
git clone https://github.com/0xNoramiya/anamnesa.git
cd anamnesa
uv venv --python 3.12
uv pip install -e ".[dev,embeddings]"

cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, ANAMNESA_EMBEDDER=bge-m3,
# ANAMNESA_MAX_WALL_CLOCK_SECONDS=450

# Build the retrieval index (BGE-M3, ~3 min on a modern GPU)
.venv/bin/python -m scripts.reindex --embedder bge-m3 --yes

# The crawled PDFs are not in git. If you want the in-app PDF viewer to
# work, you need to re-run the crawler or scp the cache over:
# git show agents/prompts/crawler.md

# Boot the backend (terminal 1)
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000

# Boot the frontend (terminal 2)
cd web
npm install
npm run dev
# open http://localhost:3000
```

Eval:

```bash
.venv/bin/python -m eval.run_eval --max-concurrent 2 \
    --output-md eval/results/run.md \
    --output-json eval/results/run.json
```

---

## Architecture

```
┌─ web/ (Next.js 14 + Tailwind + App Router) ────────┐
│  Fast search  ──GET /api/search──┐                 │
│  Mode Agen    ──POST /api/query──┤                 │
│                 └──SSE  /api/stream/{id}           │
│  PDF viewer   ──GET /api/pdf/{doc_id}              │
└────────────────────────┬───────────────────────────┘
                         │
┌─ server/ (FastAPI) ────┴───────────────────────────┐
│  Lifespan builds Orchestrator once (BGE-M3, HF     │
│  cache, agent clients). Per-query: asyncio task    │
│  writes TraceEvents into a queue the SSE handler   │
│  drains.                                           │
└────────────────────────┬───────────────────────────┘
                         │
┌─ core/ ────────────────┴───────────────────────────┐
│ orchestrator.py ── control loop, budget guardrails │
│ state.py        ── QueryState, Chunk, Citation…    │
│ retrieval.py    ── HybridRetriever (vector + BM25) │
│ embeddings.py   ── HashEmbedder, BGEEmbedder       │
│ chunk_store.py  ── LanceDB wrapper                 │
│ manifest.py     ── catalog/manifest.json schema    │
└─ agents/ ──────────────────────────────────────────┐
│ normalizer.py ── Haiku 4.5, one-shot JSON          │
│ drafter.py    ── Opus 4.7 tool-use loop            │
│ verifier.py   ── Opus 4.7 tool-use loop            │
│ prompts/      ── crawler.md ingester.md            │
│                  normalizer.md drafter.md          │
│                  verifier.md                       │
└─ tools/, scripts/, eval/, tests/, mcp/ ────────────┘
```

---

## What NOT to do (baked into the system prompts)

- No answer without inline citation.
- No fallback on model-internal medical knowledge when corpus is silent.
- No softening refusals to seem helpful.
- No patient-specific dosing decisions.
- No translation of guideline content to English.

---

## Honest caveats

- **PPK FKTP 2015 is 11 years old.** Anamnesa flags every cited
  recommendation with its source year and marks `aging` when >5 years
  old. Antibiotics, fluid protocols, DM/HT targets, and infectious-
  disease recommendations have all moved.
- **Corpus is not complete.** 25 of 79 crawled PDFs ingested so far —
  prioritizing ED/GP conditions. Clinical scenarios exist where no
  Indonesian guideline covers the question. Anamnesa refuses rather
  than hallucinating.
- **Not a medical device.** Not BPOM-registered. Reference use only.

---

## License

Code: MIT. Corpus (PNPK / PPK FKTP chunks in `catalog/processed/`):
public domain under UU 28/2014 Pasal 42.

---

## Contact

Rifqi — emergency physician, Banjarmasin. GitHub: [@0xNoramiya](https://github.com/0xNoramiya).
