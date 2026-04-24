# Anamnesa

**Indonesian clinical-guideline retrieval agent.** Anamnesa answers clinical questions written in Indonesian with inline citations to the public-domain Ministry of Health corpus — primary-care practice guidelines, national clinical protocols, and the national BPJS formulary. Every cited recommendation carries a currency flag, so a reader can tell at a glance whether a source is current, aging, or superseded by a newer edition. When the corpus does not cover a question, Anamnesa refuses rather than hallucinates.

| | |
|---|---|
| **Live demo** | [anamnesa.kudaliar.id](https://anamnesa.kudaliar.id) |
| **Built for** | [Built-with-Opus-4.7 Claude Code hackathon](https://www.anthropic.com/), 21–27 April 2026 |

---

## How a query flows

When a user asks a question, the orchestrator creates a single `QueryState` object that flows through the pipeline and accumulates everything the system learns along the way — the normalized query, each retrieval attempt, the draft answer, the verification result, the final trace, and the token-cost ledger. Every intermediate decision is recorded, which is what makes the answer reconstructible after the fact and what lets the UI stream reasoning live instead of showing a spinner.

**The Normalizer** (Haiku 4.5) reads the raw question, which is often colloquial and usually terse, and produces a structured query object that names the intent, the condition, the patient population, and the clinical setting. This step is one-shot with no retries. If the question is out of medical scope, or if it asks for a patient-specific decision such as a dose for a particular patient, the Normalizer refuses here and the pipeline stops.

**The Retriever** takes that structured query and runs it against the corpus. Retrieval is hybrid: BGE-M3 semantic vectors over more than nine thousand chunks, plus rank-bm25 lexical search, fused by reciprocal-rank fusion with metadata filters for condition, population, and document type. No language model is involved in retrieval, which keeps this step deterministic, fast, and auditable. The Retriever is packaged as an `anamnesa-mcp` MCP server, and the language-model agents reach it only through that tool boundary — they never touch the vector store or the file system directly.

**The Drafter** (Opus 4.7, adaptive thinking, `high` effort) receives the top-ranked chunks and composes an Indonesian answer with inline numeric citations. It can decide that its initial chunks were insufficient and ask the Retriever for another pass with narrower filters, but it is never allowed to emit a claim without a supporting citation. If the Drafter concludes the corpus genuinely does not support an answer, it produces a refusal with a reason code rather than reaching for training-set medical knowledge.

**The Verifier** (Opus 4.7, 1M context, `high` effort) is an independent pass over the draft. It re-fetches every cited chunk, classifies each claim as `supported`, `partial`, or `unsupported`, and calls `check_supersession` on every document to attach a currency flag — `current`, `aging`, or `superseded by <newer doc>`. If any claim comes back unsupported, the Drafter gets exactly one retry with pointed feedback about which claim failed. If the retry also fails verification, the entire answer is refused rather than shipped with a footnote.

All four stages emit structured trace events that stream to the browser over Server-Sent Events, so the user watches the reasoning unfold. A budget layer sits above the orchestrator and enforces hard caps on retrieval attempts, Drafter calls, Verifier calls, total tokens, and wall-clock time; a runaway query cannot exhaust the cost budget.

---

## Beyond the agent pipeline

Not every question needs an agent. Two lightweight endpoints sit next to the agent pipeline for the cases where the full pipeline would be overkill:

| Mode | Endpoint | Cost | Latency | When to use |
|---|---|---|---|---|
| **Fast search** | `GET /api/search` | $0 (no LLM) | ~50 ms | "Which guideline says X?" |
| **Drug lookup** | `GET /api/drug-lookup` | $0 (no LLM) | ~30 ms | "Is amoxicillin covered by the national formulary?" |
| **Agent mode** | `POST /api/query` → SSE `/api/stream/{id}` | ~$0.40–0.80 | ~130 s live / ~0 s cached | "Synthesize an answer across multiple guidelines and cite it" |

Fast search hits the Retriever directly and returns ranked chunks with enough surrounding context to identify the source. Drug lookup queries the BPJS national formulary by drug name, ATC code, or indication, and returns coverage details without ever invoking a language model. Both endpoints are read-only and designed for sub-100 ms interactive response.

A 24-hour SQLite answer cache sits in front of agent mode, keyed on the canonical raw query text. Repeat questions land on the cache in roughly zero milliseconds instead of re-running the four-agent pipeline, and the UI surfaces a small badge showing that a cached answer is being displayed and how long ago it was computed. The cache is a simple correctness win — repeated queries produce identical answers, so there is no reason to burn the budget recomputing them.

---

## Multi-turn conversations

Clinical reasoning is rarely a single question. A follow-up like *what about pediatric patients?* — asked after an adult-dose answer — would be incomprehensible to a retriever without context, so the Normalizer receives both the prior turn (query plus answer) and the terse follow-up, and rewrites the pair into a fully-qualified standalone structured query before retrieval runs. The rest of the pipeline continues normally, and the new retrieval often lands on a different guideline better suited to the new population.

Threads persist to the browser's local storage with a 24-hour TTL and a five-turn cap, so an accidental reload does not lose the thread of a consultation. A restored-session banner appears quietly when the user returns to an in-progress conversation.

---

## What the reader sees

The interface is designed so a clinician can read an answer fast and verify it even faster.

Inline numeric citations in the answer body are clickable: selecting one scrolls to the matching reference card at the bottom of the answer and flashes both ends of the citation. Reference cards link directly into the exact PDF page in the source guideline, opened in an in-app PDF viewer so the user never leaves the thread. Each reference carries its currency flag next to the document identifier, so a recommendation from a 2015 edition that has been superseded by a 2022 edition is flagged visibly before the reader acts on it.

Every answer offers three export actions — copy to clipboard, download as Markdown, and share via WhatsApp. WhatsApp is the primary channel Indonesian clinicians use to trade references in practice, so the export matches the existing workflow rather than fighting it. A thumbs-up / thumbs-down feedback widget writes to a SQLite feedback store, and an `/admin/feedback` dashboard auto-refreshes every thirty seconds to surface negative signals for triage.

When the system refuses with a `corpus_silent` code — meaning the Retriever + Drafter concluded no guideline in the corpus covers the question — the UI does not stop at the refusal text. It also renders the three closest near-miss chunks the Retriever did find, so the user can see the boundary for themselves and decide whether to rephrase the question or whether the refusal was genuine.

---

## Trust contract

The agent system prompts and the orchestrator together enforce these rules end-to-end:

- **No answer without inline citation.** If retrieval returns nothing, the Drafter refuses.
- **No fallback on model-internal medical knowledge.** When the corpus is silent, the answer is silent. Provenance over plausibility.
- **No softened refusals.** An unfounded clinical answer is worse than a plain "no Indonesian guideline exists for this scenario."
- **No patient-specific dosing decisions.** Patient-specific questions are redirected to guideline-level information that the clinician then applies to the patient in front of them.
- **No translation of guideline content.** The corpus is Indonesian; answers stay in Indonesian so the language of the recommendation always matches the language of its source.

---

## Results

| | |
|---|---|
| Documents in corpus | **81** |
| Structured chunks | **9,083** |
| Eval scenarios | **23** |
| Pass rate | **23 / 23 (100%)** |
| Hallucinated citations | **0** |
| Wall-clock, agent mode | ~130 s live / ~0 s cached |
| Wall-clock, fast search and drug lookup | ~50 ms |
| Test suite | 165 passing, ruff clean |

---

## Quickstart

Requirements: Python 3.12, Node 20+, an Anthropic API key, and optionally a CUDA GPU for the BGE-M3 reindex (CPU works, just slower).

```bash
git clone https://github.com/0xNoramiya/anamnesa.git
cd anamnesa
uv venv --python 3.12
uv pip install -e ".[dev,embeddings]"

cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-…, ANAMNESA_EMBEDDER=bge-m3

# Build the retrieval index (~3 min on a modern GPU)
.venv/bin/python -m scripts.reindex --embedder bge-m3 --yes

# Backend (terminal 1)
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000

# Frontend (terminal 2)
cd web && npm install && npm run dev
# open http://localhost:3000
```

Crawled PDFs are not committed to keep the repo light. Re-run the crawler (see `agents/prompts/crawler.md`) or copy the cache from a peer if you want the in-app PDF viewer to open source pages.

**Run the evaluation suite:**

```bash
.venv/bin/python -m eval.run_eval --max-concurrent 2 \
    --output-md eval/results/run.md \
    --output-json eval/results/run.json
```

**Run the MCP server** for Claude Desktop or Claude Code:

```bash
python -m mcp.anamnesa_mcp
# Configure via claude_desktop_config.json — see the /mcp documentation page.
```

---

## Architecture

```
┌─ web/ (Next.js 14 · App Router · Tailwind) ────────────┐
│  Landing · Chat (multi-turn) · Drugs · Search          │
│  Guideline · History · Favorites · Agent-track         │
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

The Next.js frontend talks to the FastAPI backend over REST for the read-only endpoints and Server-Sent Events for the streaming agent pipeline. The backend's lifespan hook builds the orchestrator and its agents once at boot — loading BGE-M3, opening LanceDB, and warming rank-bm25 — so the first request pays no warm-up cost. Every agent query runs as a background `asyncio` task that writes trace events into a queue the SSE handler drains and pushes to the browser as they arrive.

The `core` package holds the orchestrator and the retrieval stack, with `state.py` defining every data type that flows through the pipeline. The `agents` package holds the three language-model-backed agents, their tool-use loops, and the system prompts that encode the trust contract. The `mcp` package exposes the retrieval layer as a FastMCP server with four tools, which is what the in-process agents call and what Claude Desktop / Claude Code see when the MCP server is wired up externally.

For the full design specification — refusal states, exact budget guardrails, trace event shapes, Indonesian-language conventions — see [`CLAUDE.md`](./CLAUDE.md).

---

## License

- **Code:** MIT.
- **Corpus** (chunks in `catalog/processed/`): public domain.
