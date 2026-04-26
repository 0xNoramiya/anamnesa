# Anamnesa

**Indonesian clinical-guideline retrieval agent.** Anamnesa answers clinical questions written in Indonesian with inline citations to the public-domain Ministry of Health corpus. Every cited recommendation carries a currency flag (`current` / `aging` / `superseded`). When the corpus does not cover a question, Anamnesa refuses rather than hallucinates.

[![Watch the demo](https://img.youtube.com/vi/DJyzwe3ibCI/maxresdefault.jpg)](https://youtu.be/DJyzwe3ibCI)

| | |
|---|---|
| **Demo video** | [youtu.be/DJyzwe3ibCI](https://youtu.be/DJyzwe3ibCI) |
| **Live demo** | [anamnesa.kudaliar.id](https://anamnesa.kudaliar.id) |
| **Built for** | Built-with-Opus-4.7 Claude Code hackathon · 21–27 April 2026 |

---

## The problem

- Indonesia's national clinical guidelines, protocols, and BPJS formulary are published as long government PDFs.
- A primary-care clinician mid-consult often has only one option: open the PDF on a phone and Ctrl-F through hundreds of pages.
- Commercial CDS tools solve the interface problem but are English-only and skip Indonesian guidelines and the national formulary.
- Anamnesa is the missing retrieval layer — typed Indonesian question in, Indonesian answer out, citation to the exact page.

---

## How a query flows

Every query produces one append-only `QueryState` that flows through four stages:

- **Normalizer (Haiku 4.5)** — one-shot. Reads the colloquial question, emits a structured query (intent · condition · population · setting). Refuses out-of-scope or patient-specific questions here.
- **Retriever (MCP server, no LLM)** — hybrid: BGE-M3 semantic vectors over 9,000+ chunks + rank-bm25 lexical, fused by reciprocal-rank fusion with metadata filters. Deterministic, fast, auditable. Agents reach it only through the `anamnesa-mcp` tool boundary.
- **Drafter (Opus 4.7, adaptive thinking, `high` effort)** — composes an Indonesian answer with inline citations. Can request up to 2 retries with narrower filters. Cannot emit a claim without a supporting citation.
- **Verifier (Opus 4.7, 1M context, `high` effort)** — re-fetches every cited chunk, classifies each claim `supported` / `partial` / `unsupported`, attaches currency flags. Sends one revision back to the Drafter on failure; refuses outright if the retry also fails.

All four stages emit `TraceEvent`s that stream to the browser via SSE. A budget layer caps retrieval attempts, agent calls, total tokens, and wall-clock — a runaway query cannot exhaust the budget.

---

## Beyond the agent pipeline

Lightweight read-only endpoints handle queries that don't need the full agent loop:

| Mode | Endpoint | Cost | Latency | When to use |
|---|---|---|---|---|
| **Fast search** | `GET /api/search` | $0 | ~50 ms | "Which guideline says X?" |
| **Drug lookup** | `GET /api/drug-lookup` | $0 | ~30 ms | "Is amoxicillin in Fornas?" |
| **Agent mode** | `POST /api/query` → SSE | ~$0.40–0.80 | ~130 s live / ~0 s cached | Synthesize across guidelines |

- 24-hour SQLite **answer cache** keyed on canonical query text — repeat queries return in ~0 ms.
- Drug lookup queries the BPJS formulary by name, ATC code, or indication — no LLM ever invoked.

---

## Multi-turn conversations

- Follow-ups like *"and for pediatric patients?"* would be incomprehensible to a stateless retriever.
- Normalizer receives the prior turn (query + answer) plus the terse follow-up and rewrites them into a fully-qualified standalone query before retrieval runs.
- Threads persist to browser localStorage with 24 h TTL and a 5-turn cap. A subtle banner restores in-progress conversations on reload.

---

## What the reader sees

- **Inline numeric citations** are clickable — scrolls to the matching reference card and flashes both ends.
- **Reference cards** open the exact PDF page in an in-app PDF.js viewer, so the user never leaves the thread.
- **Currency flags** sit beside every doc id — a 2015 recommendation superseded by a 2022 edition is flagged before the reader acts.
- **Three exports** per answer: clipboard, Markdown, WhatsApp. WhatsApp matches the channel Indonesian clinicians actually use.
- **Thumbs-up / down** writes to a SQLite feedback store; `/admin/feedback` auto-refreshes for triage.
- **Refusal explorer** — when the system refuses with `corpus_silent`, the UI also renders the three closest near-miss chunks so the user can see the boundary.

---

## Trust contract

- **No answer without inline citation** — if retrieval is empty, the Drafter refuses.
- **No fallback on training-set medical knowledge** — when the corpus is silent, the answer is silent.
- **No softened refusals** — an unfounded answer is worse than a clear "no Indonesian guideline exists for this scenario."
- **No patient-specific dosing** — patient-specific questions redirect to guideline-level information.
- **No translation of guideline content** — the corpus is Indonesian; answers stay Indonesian.

---

## Results

| | |
|---|---|
| Documents in corpus | **81** |
| Structured chunks | **9,083** |
| Eval scenarios | **23** |
| Pass rate | **23 / 23 (100%)** |
| Hallucinated citations | **0** |
| Wall-clock, agent mode | ~130 s live · ~0 s cached |
| Wall-clock, fast search & drug lookup | ~50 ms |
| Test suite | 165 passing · ruff clean |

---

## Quickstart

Requirements: Python 3.12, Node 20+, an Anthropic API key. CUDA GPU is optional (CPU works, slower).

```bash
git clone https://github.com/0xNoramiya/anamnesa.git
cd anamnesa
uv venv --python 3.12
uv pip install -e ".[dev,embeddings]"

cp .env.example .env
# ANTHROPIC_API_KEY=sk-…, ANAMNESA_EMBEDDER=bge-m3

# Build the retrieval index (~3 min on a modern GPU)
.venv/bin/python -m scripts.reindex --embedder bge-m3 --yes

# Backend (terminal 1)
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000

# Frontend (terminal 2)
cd web && npm install && npm run dev
# open http://localhost:3000
```

Crawled PDFs are not committed (light repo). Re-crawl via `agents/prompts/crawler.md` or copy the cache from a peer to enable the in-app PDF viewer.

**Run the eval suite:**
```bash
.venv/bin/python -m eval.run_eval --max-concurrent 2 \
    --output-md eval/results/run.md --output-json eval/results/run.json
```

**Run the MCP server** (Claude Desktop / Claude Code):
```bash
python -m mcp.anamnesa_mcp
# wire it via claude_desktop_config.json — see the /mcp page in the app
```

---

## Architecture

```
┌─ web/ (Next.js 14 · Tailwind · shadcn/ui) ─────────────┐
│  Landing · Chat (multi-turn) · Drugs · Search          │
│  Guideline · History · Favorites · Agent trace         │
└─────────────────────────┬──────────────────────────────┘
                          │  fetch / SSE
┌─ server/ (FastAPI) ─────┴──────────────────────────────┐
│  Lifespan boots Orchestrator once (BGE-M3, LanceDB,    │
│  agent clients). Per-query asyncio task → SSE queue.   │
│  /api/health /api/meta /api/search /api/query          │
│  /api/stream /api/drug-lookup /api/feedback /…         │
└─────────────────────────┬──────────────────────────────┘
┌─ core/ ─────────────────┴──────────────────────────────┐
│  orchestrator · QueryState · HybridRetriever           │
│  embeddings (BGE-M3) · LanceDB chunk store · manifest  │
└────────────────────────────────────────────────────────┘
┌─ agents/ ──────────────────────────────────────────────┐
│  normalizer (Haiku 4.5) · drafter / verifier (Opus 4.7)│
│  prompts/ — system prompts encoding the trust contract │
└────────────────────────────────────────────────────────┘
┌─ mcp/ ─────────────────────────────────────────────────┐
│  FastMCP server: search_guidelines · get_full_section  │
│  get_pdf_page_url · check_supersession                 │
└────────────────────────────────────────────────────────┘
```

- **Backend lifespan** loads BGE-M3, opens LanceDB, warms rank-bm25 — first request pays no warm-up cost.
- **Streaming** — every agent query runs as an asyncio background task writing into a queue the SSE handler drains.
- **Tool boundary** — agents only reach retrieval through the FastMCP server, so the same tools work in-process and from Claude Desktop / Claude Code.

For the full spec (refusal states, budget guardrails, trace event shapes, Bahasa conventions) see [`CLAUDE.md`](./CLAUDE.md).

---

## Tech stack

- **Frontend** — Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, PDF.js, native SSE.
- **Backend** — Python 3.12 · FastAPI · Uvicorn · Pydantic v2 · structlog · sse-starlette.
- **Retrieval** — LanceDB · BGE-M3 (sentence-transformers) · rank-bm25 · CPU-capable at query time.
- **Agents** — Anthropic Python SDK · Haiku 4.5 · Opus 4.7 (1M ctx for Verifier) · FastMCP for the tool boundary.
- **Storage** — SQLite (cache + feedback) · file-locked JSON manifest for the corpus catalog.
- **Ingestion** — pdfplumber · PyMuPDF · httpx + BeautifulSoup · uv · ruff · mypy · pytest + pytest-asyncio.

---

## License

- **Code** — MIT.
- **Corpus** (chunks in `catalog/processed/`) — public domain.
