# Anamnesa Eval — current state

**Last update: 2026-04-22, post-expansion.**

## Headline

**23 / 23 passing (100%)** on the eval suite defined in `eval/queries.py`.
**0 hallucinated citations** across every live run to date.

## How it's measured

`.venv/bin/python -m eval.run_eval --max-concurrent 2` runs each query
through the live orchestrator (Normalizer → Retriever → Drafter →
Verifier), with automated scoring of refusal shape, citation
integrity (every `doc_id` must be in `catalog/manifest.json` — no
hallucination), source-type match, doc-id overlap against expected
docs, currency-flag presence, and keyword hits. Details and results
are in `eval/run_eval.py` and written to `eval/results/` per run
(gitignored).

## Category breakdown

| Category | Pass | Note |
|---|---|---|
| Grounded (must cite, accurate) | 17 / 17 | includes 3 Lampiran II procedural skills |
| Aging (doc ≥5 y old → flag) | 3 / 3 | |
| Absent (not in corpus → refuse) | 3 / 3 | |

## Timeline

- **13 / 20 baseline** (original run, 25-doc corpus): 0 hallucinations.
- **17 / 20 (85%)** after Normalizer refusal-scope tightening +
  cross-language keyword expansion.
- **19 / 20 (95%)** after q010 reclassified to `absent` (apnea of
  prematurity is legitimately out of corpus scope; refusal is the
  correct behavior, not a failure).
- **20 / 20 (100%)** after ingesting PPK FKTP 2022 + 54 remaining
  PNPKs: `q011 preeklampsia berat` now grounds cleanly on
  `pnpk-komplikasi-kehamilan-2017` (preeklampsia sub-PNPK) +
  `ppk-fktp-2022` (p727, p728 current-guideline) + optional
  `pnpk-anestesiologi-terapi-intensif-2022` for MgSO4 anesthetic
  context.
- **23 / 23 (100%)** after adding q021-q023 for Lampiran II
  procedural-skill retrieval (cuci-tangan 7-langkah, RJP kompresi-ventilasi,
  pemasangan kateter Foley). The RJP query correctly routes to EITHER
  `ppk-fktp-2022 lampiran_2` OR `pnpk-anestesiologi-terapi-intensif-2022`
  depending on context framing; `expected_doc_ids_any_of` lists both.

## Corpus at 20/20

- **80 documents ingested** across `ppk_fktp` (2 editions — 2015
  superseded by 2022, both Lampiran I+II now) and `pnpk` (78).
  Total **8,864 chunks**.
- **BGE-M3 / LanceDB** retrieval index with rank-bm25 sidecar,
  reciprocal-rank fusion, 1,024-dim vectors.
- Live on `https://anamnesa.kudaliar.id` with Let's Encrypt TLS.

## Cost envelope (Mode Agen, per query, on expanded corpus)

- Normalizer (Haiku 4.5): ~$0.004.
- Drafter (Opus 4.7 adaptive thinking + xhigh effort): ~$0.20 – 0.40.
- Verifier (Opus 4.7 adaptive thinking): ~$0.20 – 0.40.
- **Total typical: $0.40 – 0.80.** Over CLAUDE.md's $0.20 target but
  acceptable for the hackathon demo shape.

## Skill coverage (Lampiran II, added 2026-04-22)

`ppk-fktp-2022` now also indexes **Lampiran II — Panduan Keterampilan
Klinis**: 19 skill categories × ~194 individual skills × ~5 sub-sections
each = **621 new chunks** (hand hygiene, aseptic/antiseptic prinsip,
APD, RJP, pemasangan kateter urin, NGT, hecting, drainase abses, dll.).
Retrieval now answers procedural queries that the earlier Lampiran-I-
only index could not. Total ppk-fktp-2022 chunk count: **2,500**.
Corpus-wide: **8,864 chunks** across 80 documents.

## What's still gated on manual work

- Perhimpunan konsensus not adopted as PNPK — copyrighted, out of
  Pasal 42 scope.
