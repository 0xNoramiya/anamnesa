"""Ship the Opus high/high speed config to prod.

- Upload the three touched files (drafter, verifier, server/main)
- Append ANAMNESA_DRAFTER_EFFORT=high + ANAMNESA_VERIFIER_EFFORT=high
  to /opt/anamnesa/.env (idempotent — skip if already set)
- Restart anamnesa-backend, smoke-check
"""

from pathlib import Path

from scripts.deploy_helper import run, ssh, upload_file

REPO = Path("/home/kudaliar/hackathon/anamnesa")
REMOTE = "/opt/anamnesa"

FILES = [
    "agents/drafter.py",
    "agents/verifier.py",
    "server/main.py",
]


def main() -> None:
    c = ssh()
    try:
        for rel in FILES:
            upload_file(c, REPO / rel, f"{REMOTE}/{rel}")

        # Idempotent: `grep -q` + append avoids duplicate lines on re-runs.
        run(
            c,
            "grep -q '^ANAMNESA_DRAFTER_EFFORT=' /opt/anamnesa/.env "
            "|| echo 'ANAMNESA_DRAFTER_EFFORT=high' >> /opt/anamnesa/.env",
        )
        run(
            c,
            "grep -q '^ANAMNESA_VERIFIER_EFFORT=' /opt/anamnesa/.env "
            "|| echo 'ANAMNESA_VERIFIER_EFFORT=high' >> /opt/anamnesa/.env",
        )
        run(c, "grep -E '^ANAMNESA_(DRAFTER|VERIFIER)_EFFORT' /opt/anamnesa/.env")

        run(c, "systemctl restart anamnesa-backend")
        run(c, "sleep 2 && systemctl is-active anamnesa-backend")
        run(
            c,
            "curl -fsS -o /dev/null -w 'api_docs=%{http_code}\\n' "
            "http://127.0.0.1:8000/docs",
            check=False,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
