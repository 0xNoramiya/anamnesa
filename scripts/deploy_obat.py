"""Ship the /obat drug lookup feature to prod.

- Git pull so prod has the new files (server/main.py, web/*)
- Restart backend (picks up new /api/drug-lookup endpoint)
- Rebuild frontend (picks up new /obat route + Sidebar tweaks)
- Restart frontend, smoke-check
"""

from scripts.deploy_helper import ssh, run


def main() -> None:
    c = ssh()
    try:
        run(c, "cd /opt/anamnesa && git fetch origin main")
        run(c, "cd /opt/anamnesa && git reset --hard origin/main")
        run(c, "cd /opt/anamnesa && git log -1 --oneline")

        run(c, "systemctl restart anamnesa-backend")
        run(c, "sleep 3 && systemctl is-active anamnesa-backend")

        # Smoke-check the new endpoint directly against the backend port.
        run(
            c,
            "curl -fsS 'http://127.0.0.1:8000/api/drug-lookup?q=metformin&limit=2' "
            "| head -c 200",
            check=False,
        )

        run(
            c,
            "cd /opt/anamnesa/web && "
            "export PATH=\"$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node | tail -1)/bin:$PATH\" && "
            "npm run build 2>&1 | tail -15",
            timeout=600,
        )
        run(c, "systemctl restart anamnesa-frontend")
        run(c, "sleep 3 && systemctl is-active anamnesa-frontend")

        # Public-facing smoke: /obat should 200 through Caddy.
        run(
            c,
            "curl -fsS -o /dev/null -w 'obat=%{http_code}\\n' "
            "https://anamnesa.kudaliar.id/obat",
            check=False,
        )
        run(
            c,
            "curl -fsS -o /dev/null -w 'api=%{http_code}\\n' "
            "'https://anamnesa.kudaliar.id/api/drug-lookup?q=parasetamol'",
            check=False,
        )
    finally:
        c.close()


if __name__ == "__main__":
    main()
