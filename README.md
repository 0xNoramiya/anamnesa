# Anamnesa

**Indonesian clinical-guideline retrieval agent.** Answers Bahasa Indonesia clinical questions with inline citations to the public-domain Kemenkes corpus (PPK FKTP, PNPK, Fornas). Every recommendation carries a currency flag. When the corpus is silent, Anamnesa refuses rather than hallucinates.

| | |
|---|---|
| **Live demo** | [anamnesa.kudaliar.id](https://anamnesa.kudaliar.id) |
| **Built for** | [Built-with-Opus-4.7 Claude Code hackathon](https://www.anthropic.com/), 21–27 April 2026 |

---

## What it does

### Query surfaces

| Mode | Endpoint | Cost | Latency | When to use |
|---|---|---|---|---|
| **Cari Cepat** (fast search) | `GET /api/search` | $0 (no LLM) | ~50 ms | "Which guideline says X?" |
| **Mode Agen** (agentic RAG) | `POST /api/query` → SSE `/api/stream/{id}` | ~$0.40–0.80 | ~130 s live / ~0 s cached | "Synthesize + cite + flag" |
| **Pencarian Fornas** (BPJS drug lookup) | `GET /api/drug-lookup` | $0 (no LLM) | ~30 ms | "Is amoksisilin covered by BPJS?" |

### Mode Agen pipeline

Four agents run under a budget-guarded control loop, each emitting structured trace events streamed live to the UI:

1. **Normalizer** (Haiku 4.5) — colloquial Bahasa → structured query. Refuses on out-of-scope or patient-specific decision requests.
2. **Retriever** — hybrid BGE-M3 vector + rank-bm25 with reciprocal-rank fusion and metadata filters. No LLM. Exposed via the `anamnesa-mcp` MCP server; agents access it only through that tool boundary.
3. **Drafter** (Opus 4.7, adaptive thinking, `high` effort) — composes a cited Bahasa answer via tool-use. Narrows retrieval on its own if initial chunks are insufficient. Never invents citations.
4. **Verifier** (Opus 4.7, 1M context, `high` effort) — independently re-reads every cited chunk, classifies each claim `supported | partial | unsupported`, and calls `check_supersession` on every `doc_id` to attach a currency flag. One Drafter retry on unsupported claims; after that, the answer is refused.

### Multi-turn conversations

A follow-up like *"dan kalau anak?"* is condensed back into a standalone clinical query before retrieval. The Normalizer receives both the prior turn and the terse follow-up, produces a properly-scoped structured query, and the pipeline continues normally. Threads persist to `localStorage` (24 h TTL, 5 turns).

### Answer UX

- Inline `[N]` citations scroll-and-flash to reference cards on click; bidirectional hover highlights cite ↔ ref pairs.
- Per-answer **Salin** / **Unduh .md** / **Bagikan (WhatsApp)**.
- 24 h SQLite answer cache keyed on the canonical raw query.
- 👍 / 👎 feedback written to SQLite; `/admin/feedback` dashboard auto-refreshes every 30 s.
- On a `corpus_silent` refusal the UI renders the top 3 near-miss chunks the Retriever *did* find.

---

## By the numbers

| | |
|---|---|
| Documents in corpus | **81** |
| Structured chunks | **9,083** |
| Eval scenarios | **23** |
| Pass rate | **23 / 23 (100%)** |
| Hallucinated citations | **0** |
| Wall-clock, Mode Agen | ~130 s live / ~0 s cached |
| Wall-clock, Cari Cepat / Fornas | ~50 ms |
| Test suite | 165 passing, ruff clean |

---

## Quickstart

Requirements: Python 3.12, Node 20+, an Anthropic API key, optionally a CUDA GPU for BGE-M3 reindex.

```bash
git clone https://github.com/0xNoramiya/anamnesa.git
cd anamnesa
uv venv --python 3.12
uv pip install -e ".[dev,embeddings]"

cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY, ANAMNESA_EMBEDDER=bge-m3

# Build the retrieval index (~3 min on a modern GPU)
.venv/bin/python -m scripts.reindex --embedder bge-m3 --yes

# Backend (terminal 1)
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000

# Frontend (terminal 2)
cd web && npm install && npm run dev
# open http://localhost:3000
```

Crawled PDFs are not committed to keep the repo light. Re-run the crawler (see `agents/prompts/crawler.md`) or copy the cache from a peer if you want the in-app PDF viewer to open source pages.

**Eval:**

```bash
.venv/bin/python -m eval.run_eval --max-concurrent 2 \
    --output-md eval/results/run.md \
    --output-json eval/results/run.json
```

**MCP server (for Claude Desktop / Claude Code):**

```bash
python -m mcp.anamnesa_mcp
# Configure via claude_desktop_config.json — see the /mcp page.
```

---

## Architecture

```
┌─ web/ (Next.js 14 · App Router · Tailwind) ────────────┐
│  Landing · Chat (multi-turn) · Obat · Pencarian        │
│  Guideline · Riwayat · Favorit · Agent-track           │
│  Docs: Legal · MCP · API                               │
└─────────────────────────┬──────────────────────────────┘
                          │  fetch / SSE
┌─ server/ (FastAPI) ─────┴──────────────────────────────┐
│  Lifespan builds Orchestrator once (BGE-M3, LanceDB,   │
│  agent clients). Per-query asyncio task writes         │
│  TraceEvents into a queue the SSE handler drains.      │
│                                                        │
│  REST endpoints: /api/health /api/meta /api/manifest   │
│  /api/search /api/query /api/stream /api/drug-lookup   │
│  /api/drug-mentions /api/feedback /api/guideline       │
└─────────────────────────┬──────────────────────────────┘
                          │
┌─ core/ ─────────────────┴──────────────────────────────┐
│ orchestrator.py ── control loop, budget guardrails     │
│ state.py        ── QueryState, Chunk, Citation, …      │
│ retrieval.py    ── HybridRetriever (vector + BM25)     │
│ embeddings.py   ── HashEmbedder, BGEEmbedder           │
│ chunk_store.py  ── LanceDB wrapper                     │
│ manifest.py     ── catalog/manifest.json schema        │
│ text_cleanup.py ── PDF-watermark cleanup (renderer     │
│                    + retrieval boundary)               │
└────────────────────────────────────────────────────────┘
┌─ agents/ ──────────────────────────────────────────────┐
│ normalizer.py  ── Haiku 4.5, one-shot JSON             │
│ drafter.py     ── Opus 4.7 tool-use loop               │
│ verifier.py    ── Opus 4.7 tool-use loop (1M context)  │
│ prompts/       ── system prompts for every agent       │
└────────────────────────────────────────────────────────┘
┌─ mcp/ ─────────────────────────────────────────────────┐
│ anamnesa_mcp.py ── FastMCP server exposing 4 tools:    │
│    search_guidelines · get_full_section                │
│    get_pdf_page_url  · check_supersession              │
│ client.py       ── LocalRetriever for in-process use   │
└────────────────────────────────────────────────────────┘
```

The [`CLAUDE.md`](./CLAUDE.md) file is the design spec the build anchored to — read it for the full contract (refusal states, budget guardrails, trace event shapes, Bahasa conventions).

---

## Trust contract

Baked into every agent's system prompt:

- **No answer without inline citation.** If retrieval is empty, refuse.
- **No fallback on model-internal medical knowledge** when the corpus is silent. Provenance over plausibility.
- **No softened refusals.** An unfounded clinical answer is worse than *"tidak ada pedoman untuk skenario ini."*
- **No patient-specific dosing decisions.** Patient-specific questions are redirected to guideline-level information.
- **No translation of guideline content.** The Bahasa corpus ships Bahasa answers.

---

## License

- **Code:** MIT.
- **Corpus** (chunks in `catalog/processed/`): public domain.
