"""Ship the Fornas ingest to prod.

1. rsync fresh index/ (lance + bm25 rebuilt locally on GPU)
2. commit + push the new processed JSON + manifest + ingester script
3. git pull on prod
4. Restart anamnesa-backend so it picks up the new 9,083-chunk index
"""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

from scripts.deploy_helper import ssh, run, upload_file

REPO = Path("/home/kudaliar/hackathon/anamnesa")


def main() -> None:
    c = ssh()
    try:
        # Tar + upload the fresh index. ~80 MB compressed.
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tar_path = Path(tmp.name)
        print(f">>> tarring local index/ → {tar_path}")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(str(REPO / "index" / "bm25.pkl"), arcname="bm25.pkl")
            tar.add(str(REPO / "index" / "lance"), arcname="lance")
        print(f"    {tar_path.stat().st_size / 1_048_576:.1f} MB")
        upload_file(c, tar_path, "/tmp/anamnesa_index.tar.gz")
        tar_path.unlink(missing_ok=True)

        # Stop backend → swap index → start backend
        run(c, "systemctl stop anamnesa-backend")
        run(c, "rm -rf /opt/anamnesa/index/lance /opt/anamnesa/index/bm25.pkl")
        run(c, "cd /opt/anamnesa/index && tar xzf /tmp/anamnesa_index.tar.gz && ls -la")
        run(c, "rm /tmp/anamnesa_index.tar.gz")
        run(c, "chown -R 1000:1000 /opt/anamnesa/index")
        # No git pull — prod already has the processed JSON (we ran the
        # ingester there directly) and the same manifest that we pulled
        # back + reindexed against. Backend just needs to restart so the
        # new chunks + manifest are loaded.
        run(c, "systemctl start anamnesa-backend")
        run(c, "sleep 15 && systemctl is-active anamnesa-backend")
        run(
            c,
            "journalctl -u anamnesa-backend -n 8 --no-pager | grep -E 'boot|chunks|bm25_loaded'",
            check=False,
        )
        # Smoke: a Fornas-weighted query
        run(
            c,
            "curl -fsS 'http://127.0.0.1:8000/api/search?q=parasetamol%20fornas&limit=3' | head -c 400",
            check=False,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
