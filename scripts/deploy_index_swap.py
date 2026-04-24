"""Kill the CPU-bound prod reindex and replace with the pre-built local
index (encoded on GPU in ~minutes vs CPU hours).

Steps:
  1. Kill the reindex process on prod.
  2. Remove any partial /opt/anamnesa/index/lance.
  3. Tar + scp local index/ → prod /opt/anamnesa/index/.
  4. Start anamnesa-backend.
  5. Smoke-check and verify chunk count.
"""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

from scripts.deploy_helper import run, ssh, upload_file

REPO = Path("/home/kudaliar/hackathon/anamnesa")
LOCAL_INDEX = REPO / "index"
REMOTE = "/opt/anamnesa"


def main() -> None:
    c = ssh()
    try:
        run(c, "pkill -f 'scripts.reindex' || true", check=False)
        run(c, "sleep 2 && ps auxf | grep reindex | grep -v grep || echo 'no reindex process'", check=False)

        run(c, "rm -rf /opt/anamnesa/index/lance")
        run(c, "mv /opt/anamnesa/index/bm25.pkl /opt/anamnesa/index/bm25.pkl.bak 2>/dev/null || true", check=False)

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tar_path = Path(tmp.name)
        print(f">>> tarring local index/ → {tar_path}")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(str(LOCAL_INDEX / "bm25.pkl"), arcname="bm25.pkl")
            tar.add(str(LOCAL_INDEX / "lance"), arcname="lance")
        size_mb = tar_path.stat().st_size / 1_048_576
        print(f"    tarball size: {size_mb:.1f} MB")

        upload_file(c, tar_path, "/tmp/anamnesa_index.tar.gz")
        tar_path.unlink(missing_ok=True)

        run(c, "cd /opt/anamnesa/index && tar xzf /tmp/anamnesa_index.tar.gz && ls -la")
        run(c, "rm /tmp/anamnesa_index.tar.gz", check=False)
        run(c, "rm /opt/anamnesa/index/bm25.pkl.bak 2>/dev/null || true", check=False)
        run(c, "chown -R 1000:1000 /opt/anamnesa/index", check=False)

        run(c, "systemctl start anamnesa-backend")
        run(c, "sleep 15 && systemctl is-active anamnesa-backend")
        run(
            c,
            "journalctl -u anamnesa-backend -n 10 --no-pager | grep -E 'boot|chunks|bm25_loaded'",
            check=False,
        )
        run(
            c,
            "curl -fsS -o /dev/null -w 'api_docs=%{http_code}\\n' http://127.0.0.1:8000/docs",
            check=False,
        )
        run(
            c,
            "curl -fsS -o /dev/null -w 'public=%{http_code}\\n' https://anamnesa.kudaliar.id/",
            check=False,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
