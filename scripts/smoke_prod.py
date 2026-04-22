"""Prod health smoke test.

One-command verification that every critical endpoint + page works.
No external deps — just stdlib urllib. Exits 0 on all-pass, 1 on any
fail; safe to wire into cron or systemd timers later.

    python -m scripts.smoke_prod
    python -m scripts.smoke_prod --base https://anamnesa.kudaliar.id

The POST /api/feedback check writes a single test row with query_id
prefixed `SMOKE-` so it's easy to filter out of the /admin/feedback
view later.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE = "https://anamnesa.kudaliar.id"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""
    latency_ms: int = 0


def _fetch(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    timeout: float = 15.0,
) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")
        return resp.status, text


def _check(name: str, fn) -> Check:
    t0 = time.perf_counter()
    try:
        detail = fn()
        return Check(name, True, detail, int((time.perf_counter() - t0) * 1000))
    except AssertionError as exc:
        return Check(name, False, f"assert: {exc}", int((time.perf_counter() - t0) * 1000))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:120] if exc.fp else ""
        return Check(name, False, f"HTTP {exc.code}: {body}", int((time.perf_counter() - t0) * 1000))
    except Exception as exc:
        return Check(
            name, False, f"{type(exc).__name__}: {exc}",
            int((time.perf_counter() - t0) * 1000),
        )


def run(base: str) -> list[Check]:
    base = base.rstrip("/")
    checks: list[Check] = []

    def page_home() -> str:
        status, body = _fetch(base + "/")
        assert status == 200, f"status {status}"
        assert "Anamnesa" in body, "landing page missing 'Anamnesa'"
        return "200 · 'Anamnesa' present"

    def page_admin() -> str:
        status, _ = _fetch(base + "/admin/feedback")
        assert status == 200, f"status {status}"
        return "200"

    def api_health() -> str:
        status, body = _fetch(base + "/api/health")
        assert status == 200
        j = json.loads(body)
        assert j.get("status") == "ok", f"status field: {j}"
        return f"ok · {j.get('docs_indexed')} docs · {j.get('embedder')}"

    def api_meta() -> str:
        status, body = _fetch(base + "/api/meta")
        assert status == 200
        j = json.loads(body)
        sha = (j.get("version") or {}).get("sha", "?")
        chunks = (j.get("corpus") or {}).get("chunks", 0)
        assert chunks > 0, "corpus.chunks is 0"
        return f"sha={sha[:12]} · {chunks} chunks"

    def api_manifest() -> str:
        status, body = _fetch(base + "/api/manifest")
        assert status == 200
        j = json.loads(body)
        assert j.get("total", 0) > 0
        return f"{j['total']} docs"

    def api_search() -> str:
        # Search is the first endpoint that touches the embedder. If the
        # BGE-M3 model isn't warm yet, the first call can take 60-90s on
        # CPU — generous timeout to cover cold-start, fast on steady-state.
        status, body = _fetch(base + "/api/search?q=DBD+anak&limit=5", timeout=120.0)
        assert status == 200
        j = json.loads(body)
        assert j.get("count", 0) > 0, "search returned zero results for 'DBD anak'"
        return f"{j['count']} matches"

    def api_pdf() -> str:
        # Derive a valid doc_id from search (/api/manifest returns
        # aggregates only). BGE is warm from the prior check by now.
        _, sbody = _fetch(base + "/api/search?q=hipertensi&limit=1", timeout=30.0)
        sj = json.loads(sbody)
        if not sj.get("results"):
            raise AssertionError("no search results to derive a doc_id")
        doc_id = sj["results"][0]["doc_id"]
        # HEAD would be cheaper but FileResponse may not support it; use
        # GET with a Range header to keep bytes transferred minimal.
        req = urllib.request.Request(
            base + f"/api/pdf/{doc_id}",
            headers={"Range": "bytes=0-0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status in (200, 206), f"status {resp.status}"
        return f"pdf/{doc_id} reachable"

    def api_feedback_post() -> str:
        status, body = _fetch(
            base + "/api/feedback",
            method="POST",
            body={
                "query_id": f"SMOKE-{int(time.time())}",
                "query_text": "prod smoke-test ping",
                "rating": "up",
            },
        )
        assert status == 200
        j = json.loads(body)
        assert j.get("stored") is True, f"unexpected body: {j}"
        return f"stored id={j.get('id', '?')[:12]}"

    def api_feedback_stats() -> str:
        status, body = _fetch(base + "/api/feedback/stats")
        assert status == 200
        j = json.loads(body)
        return f"total={j.get('total', 0)}"

    ordered = [
        ("page /", page_home),
        ("page /admin/feedback", page_admin),
        ("GET /api/health", api_health),
        ("GET /api/meta", api_meta),
        ("GET /api/manifest", api_manifest),
        ("GET /api/search", api_search),
        ("GET /api/pdf", api_pdf),
        ("POST /api/feedback", api_feedback_post),
        ("GET /api/feedback/stats", api_feedback_stats),
    ]
    for name, fn in ordered:
        checks.append(_check(name, fn))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    t0 = time.perf_counter()
    checks = run(args.base)
    total_ms = int((time.perf_counter() - t0) * 1000)

    # Print table.
    max_name = max(len(c.name) for c in checks) + 2
    if not args.quiet:
        print(f"Smoke-testing {args.base}")
        print()
    for c in checks:
        icon = "PASS" if c.passed else "FAIL"
        tone = "  " if c.passed else "!!"
        print(f"  {tone} {icon}  {c.name.ljust(max_name)}  {c.latency_ms:>5} ms  {c.detail}")
    passed = sum(1 for c in checks if c.passed)
    failed = len(checks) - passed
    print()
    if failed == 0:
        print(f"All {passed} checks passed in {total_ms} ms.")
        return 0
    print(f"{failed} of {len(checks)} checks FAILED (total {total_ms} ms).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
