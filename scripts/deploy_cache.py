"""Ship the answer-cache feature to prod.

- Upload core/cache.py (new), core/state.py, core/orchestrator.py,
  server/main.py
- Upload web/lib/types.ts + web/components/AnswerPanel.tsx
- Rebuild frontend, restart both services
- Smoke-check
"""

from pathlib import Path

from scripts.deploy_helper import ssh, run, upload_file

REPO = Path("/home/kudaliar/hackathon/anamnesa")
REMOTE = "/opt/anamnesa"

FILES = [
    "core/cache.py",
    "core/state.py",
    "core/orchestrator.py",
    "server/main.py",
    "web/lib/types.ts",
    "web/components/AnswerPanel.tsx",
]


def main() -> None:
    c = ssh()
    try:
        for rel in FILES:
            upload_file(c, REPO / rel, f"{REMOTE}/{rel}")

        run(c, "mkdir -p /opt/anamnesa/catalog/cache && ls -la /opt/anamnesa/catalog/cache | head")

        run(c, "systemctl restart anamnesa-backend")
        run(c, "sleep 3 && systemctl is-active anamnesa-backend")

        run(
            c,
            "cd /opt/anamnesa/web && "
            "export PATH=\"$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node | tail -1)/bin:$PATH\" && "
            "npm run build 2>&1 | tail -15",
            timeout=600,
        )
        run(c, "systemctl restart anamnesa-frontend")
        run(c, "sleep 3 && systemctl is-active anamnesa-frontend")

        # Confirm cache DB gets created on next query; for now just boot log.
        run(
            c,
            "journalctl -u anamnesa-backend -n 6 --no-pager | grep -E 'boot|cache'",
            check=False,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
