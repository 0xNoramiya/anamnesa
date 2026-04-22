# Anamnesa — Indonesian Clinical Guideline Retrieval Agent

## Why this exists

I'm Rifqi — emergency physician and general practitioner in Banjarmasin,
South Kalimantan. I built this because I need it. Every shift I hit the
same friction: a clinical scenario I haven't seen in months, the current
Indonesian guideline is buried in a PDF on some Kemenkes or perhimpunan
site, and I'm Ctrl-F'ing through hundreds of pages on my phone while the
patient waits.

Existing commercial clinical decision support tools are English-only,
priced at roughly USD 499 per year (approximately 1.5–2.5 months of an
entry-level Puskesmas GP base salary), and don't cover Indonesian national
guidelines or BPJS Fornas formulary. Most Indonesian doctors outside
tertiary institutions don't use any reference tool — they rely on memory,
WhatsApp groups, and whichever senior happens to be on call.

Anamnesa is my attempt to fix this for myself first. If it's useful for
other Indonesian doctors, that's a bonus.

Built for: Built with Opus 4.7 Claude Code hackathon (Apr 21–27, 2026).
Problem statement: PS1 — "Build From What You Know."

## Product definition

An agentic retrieval and citation system that answers Bahasa Indonesia
clinical queries by pulling from Indonesia's public-domain clinical
guideline corpus, returning grounded answers with inline citations to
exact source pages, with a currency flag on every recommendation, and
an explicit refusal when the corpus is silent or outdated.

Primary user: me. Secondary users: Indonesian GPs and residents,
particularly at FKTP Puskesmas and non-tertiary hospitals.

## Product scope — strict

This is a GUIDELINE RETRIEVAL AND CITATION TOOL. Not clinical decision
support for specific patients. Not a medical device. Every UI surface
and generated answer must reinforce this framing, in Bahasa:

  "Anamnesa membantu dokter menemukan dan mengutip pedoman Indonesia
   yang berlaku. Ini bukan alat diagnosis atau rekomendasi terapi untuk
   pasien individual. Keputusan klinis tetap menjadi tanggung jawab
   dokter."

Out of scope for this week:
- Patient-specific dose calculation
- EMR/HIS integration
- Drug interaction checking
- Imaging interpretation
- Multi-user accounts or authentication
- Mobile app
- Perhimpunan konsensus not adopted as PNPK (copyrighted, deferred)

## Legal foundation

The entire corpus strategy rests on **Pasal 42 UU No. 28/2014 tentang
Hak Cipta**, which removes copyright protection from "peraturan
perundang-undangan" and "keputusan pejabat Pemerintah." Every PNPK,
PPK FKTP, and Kemenkes pedoman is published as Lampiran of a Kepmenkes
and is explicitly declared "bagian tidak terpisahkan" (inseparable
part) of that keputusan. They are therefore public domain under
Indonesian law.

Practical consequences:
- We can host full PDFs, commit them to the public GitHub repo, serve
  them to users, chunk and embed full text, and reproduce passages in
  generated answers.
- Users can download, redistribute, screenshot, print, and share freely.
- Attribution remains good practice (every citation names the source
  document, year, and page) but is not a legal requirement.

For the hackathon build, we scope the corpus to Pasal 42 documents only.
Perhimpunan konsensus that are not formally adopted as PNPK remain
copyrighted and are out of scope for week one.

## Corpus priority (build order)

Day 1 discovery proceeds in this order. Stop when the demo has enough;
do not chase completeness.

1. **PPK FKTP 2015** (Kepmenkes HK.02.02/MENKES/514/2015) — single
   document, ~900+ pages, covers 155 SKDI 4A conditions. This is THE
   GP document in Indonesia. One deep ingestion here gives Anamnesa
   real primary care coverage.
2. **PNPK archive** — scrape all years from kemkes.go.id, ~80–90 PDFs.
3. **Kemenkes Pedoman Program** — TB, malaria, HIV, dengue, imunisasi,
   stunting, COVID-19, PTM, kesehatan jiwa, gizi.
4. **Formularium Nasional** — BPJS-covered drugs and restrictions.
5. **Pedoman operasional FKTP / Puskesmas** — workflow references.

Realistic Track A corpus by end of Day 2: ~110–140 documents covering
250+ conditions, all public domain.

## Honest caveats baked into UI and pitch

- **PPK FKTP 2015 is 11 years old.** Antibiotics, fluid protocols,
  DM/HT targets, and infectious disease recommendations have all moved.
  Anamnesa flags every cited recommendation with its source year and
  warns when >5 years old or superseded by a newer PNPK.
- **Corpus is not complete.** Clinical scenarios exist where no
  Indonesian guideline covers the question. Anamnesa refuses clearly
  rather than hallucinating an answer.
- **Not a medical device.** Not BPOM-registered. Reference use only.

## Runtime architecture

Query flow:

  user (Bahasa, often colloquial)
    → Query Normalizer (Haiku 4.5) — colloquial → structured query
    → Hybrid Retriever (MCP server `anamnesa-mcp`) — LanceDB + BM25 
      with metadata filters and currency awareness
    → Draft Agent (Opus 4.7, adaptive thinking) — cited Bahasa answer
    → Verifier Agent (Opus 4.7, 1M context) — re-reads cited sections,
      confirms support, catches hallucinated citations
    → Currency Check — overlay year + supersession graph
    → Response to user with inline citations + currency banners

Model routing (cost discipline, $500 hackathon credit budget):
- Haiku 4.5: query normalization, metadata extraction from clean text
- Sonnet 4.6: schema extraction from text PDFs, non-critical batch work
- Opus 4.7 (xhigh): vision PDF extraction, draft answer, verifier,
  anything trust-critical

Build-time: Opus 4.7 xhigh for all Claude Code sessions. Parallel
sub-agents for corpus discovery (one per source) and ingestion (batches
of PDFs).

## Agentic RAG contract

Anamnesa is **agentic RAG, not pipeline RAG**. Agents can loop, retry,
re-retrieve with different filters, reject each other's output, and
refuse when confidence is low. Build agents, not a pipeline.

### Shared state object

Every query produces one `QueryState` object that flows through all
agents and accumulates, never overwrites:

```python
@dataclass
class QueryState:
    query_id: str                       # ULID
    original_query: str                 # raw Bahasa from user
    normalized_query: NormalizedQuery | None
    retrieval_attempts: list[RetrievalAttempt]
    draft_answer: DraftAnswer | None
    verification: VerificationResult | None
    currency_flags: list[CurrencyFlag]
    final_response: FinalResponse | None
    refusal_reason: RefusalReason | None
    trace_events: list[TraceEvent]
    cost_tokens: CostLedger
```

State is append-only per field where possible. This is what makes the
agent trace reconstructible and the system debuggable.

### Agent roster, tools, and authority

**Normalizer (Haiku 4.5)**
- Input: `original_query`
- Tools: none
- Authority: produces `normalized_query` or refuses if query is
  out of medical scope.
- No retries. One shot. If output is malformed, orchestrator refuses.

**Retriever (MCP server `anamnesa-mcp`, not an LLM)**
- Input: `normalized_query` + optional filters
- Tools exposed:
  - `search_guidelines(query: str, filters: RetrievalFilters) -> list[Chunk]`
  - `get_full_section(doc_id: str, section_path: str) -> SectionText`
  - `get_pdf_page_url(doc_id: str, page: int) -> str`
  - `check_supersession(doc_id: str) -> SupersessionInfo`
- Authority: pure retrieval, no LLM judgment.

**Drafter (Opus 4.7, adaptive thinking)**
- Input: `normalized_query` + most recent `RetrievalAttempt`
- Tools: `search_guidelines`, `get_full_section`
- Authority:
  - Decide retrieval was insufficient → request re-retrieval with
    narrower filters (up to 2 additional attempts, 3 total max).
  - Decide corpus is silent on the topic → set refusal_reason and stop.
  - Produce `draft_answer` with inline citations, one citation per claim.
- MUST NOT invent citations. MUST NOT answer without retrieved grounding.

**Verifier (Opus 4.7, 1M context)**
- Input: `draft_answer` + cited sections fetched via `get_full_section`
- Tools: `get_full_section`, `check_supersession`
- Authority:
  - Classify each cited claim: `supported | partial | unsupported`.
  - If any unsupported claim → send draft back to Drafter with specific
    feedback on which claim failed, up to 1 verifier-triggered retry.
  - If retry still has unsupported claims → mark refusal, never ship
    unsupported content to user.
  - Apply currency flags (`current | superseded | aging | withdrawn`)
    to each verified citation.
- MUST NOT modify the draft itself. Verifier judges, Drafter writes.

### Control loop

Orchestrator implements this loop explicitly. No implicit magic:

```
1. state = QueryState(original_query=user_input)
2. state.normalized_query = Normalizer.run(state)
   if normalized_query is refusal → emit refusal, stop.
3. loop up to MAX_RETRIEVAL_ATTEMPTS (=3):
     attempt = Retriever.search(normalized_query, filters)
     state.retrieval_attempts.append(attempt)
     draft = Drafter.run(state)
     if draft.decision == "need_more_retrieval":
        adjust filters per Drafter's hints, continue loop
     elif draft.decision == "refuse":
        state.refusal_reason = draft.reason; emit refusal, stop
     else:
        state.draft_answer = draft; break
   else:
     emit refusal "retrieval budget exhausted", stop
4. state.verification = Verifier.run(state)
   if verification.has_unsupported and retries_left:
      return to step 3 with Verifier's feedback, retries_left -= 1
   if verification.has_unsupported and no retries_left:
      emit refusal "cannot verify citations", stop
5. state.currency_flags = Verifier.attach_currency_flags(state)
6. state.final_response = assemble(state)
7. emit response + full trace_events
```

### Budget guardrails (hard stops, non-negotiable)

Per query:
- MAX_RETRIEVAL_ATTEMPTS = 3
- MAX_DRAFTER_CALLS = 3
- MAX_VERIFIER_CALLS = 2
- MAX_TOTAL_TOKENS_PER_QUERY = 150,000
- MAX_WALL_CLOCK_PER_QUERY = 30 seconds

Abort cleanly on exceeding any limit. Log. Refuse with generic reason.
These exist so one bad query cannot eat 10% of the budget.

### Refusal is always a valid terminal state

At every agent, refusal is a first-class output, not an error path.
An unfounded clinical answer is worse than a clear "Anamnesa tidak
menemukan pedoman Indonesia untuk skenario ini."

Refusal reasons (enum, surfaced to user in Bahasa):
- `out_of_medical_scope`
- `corpus_silent`
- `all_superseded_no_current`
- `citations_unverifiable`
- `patient_specific_request`
- `retrieval_budget_exhausted`
- `token_budget_exhausted`

### Trace events for observability

Every agent emits structured `TraceEvent` objects appended to
`state.trace_events`:

```python
TraceEvent(
    timestamp: datetime,
    agent: Literal["normalizer", "retriever", "drafter",
                   "verifier", "orchestrator"],
    event_type: str,
    payload: dict,
    tokens_used: int,
    latency_ms: int,
)
```

The web frontend's agent trace sidebar renders these events live. This
is not optional — without it, the demo looks like a chat UI and the
agentic work is invisible to judges.

### Tool boundary

Drafter and Verifier access the retrieval layer only via the
`anamnesa-mcp` MCP server. They do not touch the vector store, file
system, or PDF cache directly. Tool schemas are defined once in
`mcp/anamnesa_mcp.py` and referenced by all agent prompts via include.

### What counts as "agentic" vs "just a pipeline"

This design is agentic because:
1. Drafter can decide retrieval failed and request narrower re-retrieval.
2. Verifier can reject a draft and trigger revision with specific 
   feedback.
3. Either agent can unilaterally refuse when confidence is insufficient.
4. The orchestrator loop has real branching, not fixed sequence.

If you find yourself building a linear pipeline where each step hands
off to the next with no judgment, stop and re-read this section.

## Repository layout

  anamnesa/
    catalog/
      cache/{SOURCE}/*.pdf          # public domain PDFs, cached locally
      processed/{SOURCE}/*.json     # structured records
      manifest.json                 # source registry + document records
    index/
      lance/                        # vector index
      bm25.pkl
    mcp/
      anamnesa_mcp.py               # retrieval MCP server
    agents/
      prompts/
        crawler.md
        ingester.md
        normalizer.md
        drafter.md
        verifier.md
    tools/
      manifest_append.py            # file-locked JSON append
      supersession.py               # cluster + resolve outdated guidelines
      pdf_vision.py                 # Opus 4.7 vision extraction helper
    eval/
      queries.yaml                  # 20 eval queries, my ED scenarios
      run_eval.py
      results/
    web/                            # Next.js frontend
    scripts/
      discover.py
      ingest.py
      build_index.py
    .env.example
    CLAUDE.md                       # this file
    README.md

## Tech stack

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind + shadcn/ui,
  PDF.js for inline source viewer, SSE for agent trace streaming
- **Backend:** FastAPI (Python 3.12), Anthropic Python SDK, Pydantic v2,
  structlog, Uvicorn
- **MCP server:** official MCP SDK, LanceDB, rank_bm25, BGE-M3
  embeddings via sentence-transformers (local) or Voyage AI (API)
- **Metadata:** DuckDB for supersession graph queries
- **Ingestion:** pdfplumber for text PDFs, Opus 4.7 vision for
  scanned/table-heavy PDFs, httpx + BeautifulSoup for crawling
- **Dev:** uv, ruff, mypy, Docker Compose
- **Deployment:** self-hosted VPS with Caddy as reverse proxy
  (automatic HTTPS, SSE-compatible)
- **Domain:** anamnesa.kudaliar.id
- **Observability:** structlog JSON logs, Sentry free tier for errors

## Coding standards

- Python 3.12, ruff + mypy strict where practical
- Type hints on all function signatures
- Structured logging (structlog) — no bare print in production paths
- Errors loud, not swallowed. Sub-agent failures must surface to
  orchestrator.
- No mocked data in committed code. If a step needs data that doesn't
  exist, raise NotImplementedError with a clear message.
- Secrets via .env, never hardcoded. .env gitignored, .env.example
  committed.

## Bahasa Indonesia conventions

- User-facing strings: Bahasa Indonesia, formal register (Anda, not kamu)
- Medical terms: the form Indonesian doctors actually use. "Gagal
  jantung" not "heart failure". "DBD" is fine and often preferred in
  clinical context over "demam berdarah dengue".
- Code comments, variable names, commit messages: English
- Doc IDs, tags, condition codes: English snake_case for machine use
- Optional EN toggle on UI chrome (buttons, labels) for judges, but
  clinical content stays in Bahasa

## Citation format

Inline citation in draft answers:
  [[doc_id:page:section_slug]]

Example:
  "Pada DBD derajat II pediatrik, terapi cairan kristaloid inisial 6-7 
   ml/kg/jam [[IDAI-2014-DBD-001:p23:tata_laksana_derajat_ii]]."

Every cited claim MUST map to a real page in a real document in the
catalog. Hallucinated citations are the single worst failure mode —
the verifier agent exists specifically to catch these.

## Currency and supersession

Every citation displayed carries a currency flag:
- `current` — no newer guideline from same authority on same topic
- `superseded` — newer guideline exists; show both, recommend newer
- `aging` — >5 years old, no newer version found, caveat shown
- `unknown` — supersession graph couldn't resolve
- `withdrawn` — actively retracted

Never display a cited recommendation without its currency flag.

## Refusal paths (explicit, never silent)

The draft agent MUST refuse clearly in Bahasa in these cases:
1. No Indonesian guideline covers the query → state it. Optionally offer
   an international reference as supplement, with explicit "bukan
   pedoman Indonesia" caveat.
2. All retrieved guidelines are superseded and no current version
   exists → state it, do not answer from outdated content.
3. Query asks for patient-specific decision ("berapa dosis untuk pasien
   ini") → redirect: "Ini keputusan klinis individual. Anamnesa
   menyediakan pedoman, bukan rekomendasi per-pasien."
4. Query is out of medical scope → polite redirect.

Refusal is better than hallucination. Always.

## Success metrics (hackathon demo)

- Catalog: ≥100 guideline records across ≥6 sources
- PPK FKTP 2015 fully ingested and queryable at condition granularity
- Eval: 20 queries drawn from my actual ED scenarios; ≥85% cited 
  correctly; 0 hallucinated citations
- End-to-end latency: <15s per query at xhigh
- Cost per query: <$0.20 USD
- Three demo queries that land cleanly:
  - Bahasa colloquial input correctly normalized → cited answer
  - Outdated guideline correctly flagged as aging / superseded
  - Absent guideline correctly refused instead of hallucinated

## What NOT to do

- Do not answer without inline citations. If retrieval is empty, refuse.
- Do not fall back on model-internal medical knowledge when the corpus
  is silent. Anamnesa's value is provenance, not plausibility.
- Do not soften refusals to seem helpful. In clinical context, an
  unfounded answer is worse than "tidak ada pedoman untuk skenario ini."
- Do not add patient-specific reasoning mid-build. Scope lock matters.
- Do not skip the verifier to save tokens. Trust layer, non-negotiable.
- Do not translate guideline content to English. Preserve original Bahasa.
- Do not chase corpus completeness over demo quality. 100 docs indexed
  well beats 300 indexed badly.
- Do not add copyrighted perhimpunan konsensus this week. Week one is
  Pasal 42 corpus only.

## Reference

- Hackathon brief: Built with Opus 4.7, Apr 21–27 2026, PS1 "Build From
  What You Know"
- Legal basis: UU No. 28/2014 Pasal 42 (public domain for peraturan 
  perundang-undangan and keputusan pejabat Pemerintah)
- PPK FKTP legal basis: Kepmenkes HK.02.02/MENKES/514/2015
- PNPK archive: kemkes.go.id/id/media/subfolder/pedoman/pedoman-nasional-pelayanan-kedokteran-pnpk
