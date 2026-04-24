"""Ship the 'why refused' hint to prod."""

from __future__ import annotations

from scripts.deploy_helper import run, ssh


def main() -> None:
    c = ssh()
    try:
        run(c, "cd /opt/anamnesa && git fetch origin main && git reset --hard origin/main")
        run(c, "cd /opt/anamnesa && git log -1 --oneline")

        run(c, "systemctl restart anamnesa-backend")
        run(c, "sleep 10 && systemctl is-active anamnesa-backend")

        run(
            c,
            "cd /opt/anamnesa/web && "
            "export PATH=\"$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node | tail -1)/bin:$PATH\" && "
            "npm run build 2>&1 | tail -12",
            timeout=600,
        )
        run(c, "systemctl restart anamnesa-frontend")
        run(c, "sleep 3 && systemctl is-active anamnesa-frontend")

        run(c, "curl -fsS -o /dev/null -w 'api=%{http_code}\\n' http://127.0.0.1:8000/docs", check=False)
        run(c, "curl -fsS -o /dev/null -w 'public=%{http_code}\\n' https://anamnesa.kudaliar.id/", check=False)
    finally:
        c.close()


if __name__ == "__main__":
    main()
