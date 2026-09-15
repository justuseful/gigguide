# Humans of Bundjalung Gig Guide

Live music listings for Byron Bay and the Northern Rivers. Flask + SQLite, built to run on a
free-tier 1GB VM with video hosted on YouTube (embedded on gig pages) rather than served locally.

## Run locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
export GIGGUIDE_ADMIN_PASSWORD=change-me
.venv/bin/flask --app wsgi seed --samples          # starter venues + sample gigs
.venv/bin/flask --app wsgi run
```

Site: http://127.0.0.1:5000 · Admin: http://127.0.0.1:5000/admin (user `admin`).
Tests: `python tests/test_smoke.py`.

## Deploy / update (Ubuntu 24.04)

```bash
curl -fsSL https://raw.githubusercontent.com/<user>/gigguide/main/deploy/setup.sh -o setup.sh
REPO_URL=https://github.com/<user>/gigguide.git sudo -E bash setup.sh
```

The script is idempotent: first run installs nginx, gunicorn (systemd unit `gigguide`), a 1GB
swapfile, a nightly SQLite backup, and generates `/etc/gigguide.env` with a random admin
password; later runs just `git pull`, install requirements and restart.

- Code: `/opt/gigguide/app` · Data (DB, uploads, backups): `/var/lib/gigguide`
- Admin credentials: `sudo cat /etc/gigguide.env`
- Logs: `journalctl -u gigguide -f`

## Environment variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Session signing key (required in production) |
| `GIGGUIDE_ADMIN_USER` / `GIGGUIDE_ADMIN_PASSWORD` | Admin login (HTTP Basic). Admin is disabled if no password is set |
| `GIGGUIDE_DATA_DIR` | Where the SQLite DB and uploads live (default `./data`) |
| `GIGGUIDE_SITE_NAME`, `GIGGUIDE_SITE_TAGLINE`, `GIGGUIDE_TIMEZONE` | Branding and local time zone |

## Notes

- Page views are counted server-side (see the admin dashboard). If you later make Cloudflare cache
  HTML, switch to Cloudflare Web Analytics, since cached pages never reach the server.
- Featured gigs (paid placement) are pinned to the top of the guide and highlighted.
- Put Cloudflare in front once a domain is chosen: free SSL, caching and DDoS protection.
