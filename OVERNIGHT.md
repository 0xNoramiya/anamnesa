# Overnight autonomous loop — 2026-04-22 → 04-23

Rifqi said *"continue reimprove with /loop while I asleep"* at ~22:00 local
on 2026-04-22. What follows is what happened between then and ~06:00 the
next morning. Every iteration implemented one bounded change, ran tests,
committed, pushed to GitHub, and deployed to prod before scheduling the
next wake-up.

Skip to the bottom if you just want the final state.

## Shipped iterations

Each bullet links to its commit. All changes are on `main`, pushed to
`0xNoramiya/anamnesa`, and deployed to `https://anamnesa.kudaliar.id`.

**UX improvements** (most demo-visible)

- **Mobile PDF + Mode Agen progress + speed config** (`67ca3a1`) — iOS
  Safari can't render PDFs in iframes, so mobile swaps to a tappable
  "Open in new tab" card. Mode Agen phase indicator gains an elapsed
  timer + per-agent phase dots + heartbeat traces from Drafter/Verifier
  inner loops. Opus 4.7 effort dropped from `xhigh` to `high` after a
  130-vs-222s A/B (`scripts/bench_agentic.py`) — ~42% speedup, citations
  held.
- **Answer cache** (`d867ce5`) — SQLite at `catalog/cache/answers.db`,
  24h TTL, keyed on the canonicalized raw user query (Haiku's normalized
  form is stochastic and would kill hit rate). Hits skip every LLM
  call including the Normalizer. Second run of the same query: ~0 s,
  $0. UI badge "Dari cache · X menit lalu".
- **Why refused** (`b0665a2`) — on `corpus_silent` /
  `all_superseded_no_current` / `citations_unverifiable` refusals the
  UI renders the top 3 near-miss chunks the Retriever *did* find so
  the user knows the corpus was searched.
- **Client query history** (`ea508cb`) — localStorage of the last 20
  query+answer pairs; tap to restore without re-running.
- **Markdown export** (`e7f18c0`) — per-answer "Salin" + "Unduh .md"
  with `[N]` citations → `[^N]` footnotes and a Referensi section with
  verbatim chunk-text quotes.
- **Per-citation "Salin kutipan"** (`ff01fdd`) — individual reference
  cards can be copied as a standalone Markdown block.
- **Clickable inline citations** (`d722bbe`) — `[N]` markers scroll-
  and-flash to their reference card on click; native Cmd/Ctrl-click
  still opens in a new tab.
- **Trace sidebar phase groups** (`cae1c6b`) — consecutive same-agent
  events collapse into a single row with total latency; current phase
  stays expanded.
- **Bidirectional cite↔ref hover** (`8cd6abf`) — hovering a `[N]` in
  the prose halos the matching reference card; hovering a card halos
  all matching `[N]` markers.
- **Keyboard shortcuts** (`95e8834`) — `/` focuses the query input
  (skipped when typing elsewhere); `Cmd/Ctrl+Enter` submits.
- **Fast Search arrow-key nav** (`2152393`) — ↑/↓ through results,
  Enter opens PDF at top hit. Active row gets a civic border.

**Backend + infra**

- **`/api/meta` + provenance footer** (`6dc4a15`) — endpoint returns
  git SHA + corpus stats + live cache stats + legal basis. Footer on
  every page fetches + renders it; SHA links to the GitHub commit.
- **Feedback thumbs** (`27afdb1`) — SQLite at
  `catalog/cache/feedback.db`. `POST /api/feedback {query_id,
  query_text, rating, note?}` writes; `GET /api/feedback/stats` reads.
  UI shows 👍 / 👎 bar under every successful answer with an optional
  note field that auto-opens on 👎. localStorage memo per query_id so
  refresh preserves the vote.
- **`/admin/feedback` dashboard** (`18e16e6`) — auto-refreshing table
  of the latest 20 entries + satisfaction %. Use it to spot corpus
  gaps.
- **Smoke-filter on stats** (`0754ef7`) — `/api/feedback/stats` hides
  `SMOKE-*` query_ids by default; admin page has a toggle to show them.

**Writing**

- **PITCH.md** (`abbf836`) — 23/23 eval, ~130s live / 0s cached,
  "Answer UX layer" section covering everything above.
- **README.md** (`9b83fe3`) — matches deployed state (80 docs, 8864
  chunks, 147 tests, Opus high).

**Ops**

- **Prod sync + local-GPU index swap** (earlier) — pushed 7 unsynced
  commits to prod, killed a 110-min CPU-bound reindex, rsync'd the
  locally-GPU-built index in ~45s instead.
- **`scripts/smoke_prod.py`** (`32c9c2f`) — single-command all-
  surface health check. Tolerates BGE-M3 cold-load on the first
  `/api/search` hit (120s timeout).

## Final state

| | |
|---|---|
| Commits shipped this session | 19 |
| Tests | 147 passing, 0 skipped, ruff clean |
| Eval | 23/23 (no change — tonight was UX, not retrieval) |
| Wall-clock (Mode Agen) | ~130 s live / ~0 s on cache hit |
| Prod | Backend active · `/api/meta` sha matches HEAD · smoke 9/9 PASS |

## Stuff I deliberately didn't do

- **Real token streaming** — I prototyped it (`scripts/probe_real_drafter.py`,
  deleted) and measured: with adaptive thinking + `high` effort, Opus
  does ~76 s of silent thinking then bursts 4,500 chars in 0.4 s via
  `input_json_delta`. Streaming gives the user nothing visible.
  Conclusion: kill the plan, spend the complexity budget elsewhere.
- **Bundling the Verifier model down to Sonnet** — benchmarked at
  iter-2. Sonnet took an extra tool-use iteration and netted *slower*
  than Opus high. Skipped.
- **Shareable answer URL** — would need server-side answer persistence
  with a public read path; non-trivial for a hackathon, no clear user.
- **Dark mode** — scope vs value was wrong.
- **Fornas ingestion** — too big for one loop iteration.

## Things worth a look when you're awake

1. **Test the hover link-up in Mode Agen** — it's the one UX thing I
   can't verify without a browser. Hover `[N]` in the answer prose,
   watch the reference card halo.
2. **Try the export** — "Unduh .md" on any answer and paste the file
   into a Markdown renderer. The `[^N]` footnotes should work.
3. **/admin/feedback** — currently has some SMOKE-* entries from my
   smoke test (hidden by default; flip the toggle to see them). Real
   user thumbs will land as you and others use the app.
4. **Cost watch** — the cache means repeat queries are free. A typical
   day pattern (doctor re-asks "DBD anak" three times across a shift)
   is now one $0.60 hit and two $0 hits instead of three $0.60s.

## Things that remain on the Open Work list

- **Watermark bleed** on Lampiran II chunks — cosmetic slug noise;
  body-text content is still recoverable.
- **Cost-per-query** — still $0.40–0.60 when cache misses. Haiku'ing
  simpler Verifier partials is the next big lever.
- **q010 apnea-of-prematurity** — genuine corpus gap; refusal is
  correct and the "why refused" card now makes that visible.

— autonomous loop, 2026-04-23
