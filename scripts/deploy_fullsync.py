"""Full sync: fetch all 7 unsynced commits to prod, reindex LanceDB to
include PPK FKTP 2022 Lampiran II's 621 procedural-skill chunks,
restart services.

Downtime: backend down for ~5-10 min during reindex. Frontend stays up
but will 504 on /api/query until backend returns.
"""

from __future__ import annotations

from scripts.deploy_helper import ssh, run


def main() -> None:
    c = ssh()
    try:
        # 1. Resync the working tree to origin/main. Prod's tree has
        # uncommitted files from our earlier scp deploys that are
        # identical to what just landed on origin — reset --hard is
        # safe and easier than reconciling.
        run(c, "cd /opt/anamnesa && git fetch origin main")
        run(c, "cd /opt/anamnesa && git reset --hard origin/main")
        run(c, "cd /opt/anamnesa && git log -1 --oneline")

        # 2. Stop backend so it doesn't read a half-rebuilt index.
        run(c, "systemctl stop anamnesa-backend")

        # 3. Rebuild the LanceDB + BM25 index. --yes skips the
        # drop-existing confirmation prompt. Embedder read from .env.
        run(
            c,
            "cd /opt/anamnesa && "
            "ANAMNESA_EMBEDDER=bge-m3 "
            ".venv/bin/python -m scripts.reindex --embedder bge-m3 --yes 2>&1 | tail -40",
            timeout=1800,
        )

        # 4. Bring backend back, warm up, smoke-check.
        run(c, "systemctl start anamnesa-backend")
        run(c, "sleep 15 && systemctl is-active anamnesa-backend")
        run(
            c,
            "curl -fsS -o /dev/null -w 'docs=%{http_code}\\n' http://127.0.0.1:8000/docs",
            check=False,
        )
        run(
            c,
            "journalctl -u anamnesa-backend -n 8 --no-pager | grep -E 'boot|chunks'",
            check=False,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
