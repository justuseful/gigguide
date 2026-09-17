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
| `GIGGUIDE_PATREON_URL`, `GIGGUIDE_KOFI_URL`, `GIGGUIDE_PAYPAL_URL` | Links shown on `/support`. Unset ones are hidden — add them once you've created the accounts |

## Support page

`/support` links out to whichever of Patreon, Ko-fi and PayPal are configured (see env vars
above) so people can help cover hosting costs. No payment processing happens on this site —
it's just outbound links, so there's no card data, webhooks or user accounts to build or secure.
To add a link: create the account on that platform yourself, then set the matching env var in
`/etc/gigguide.env` and `systemctl restart gigguide` (or re-run `deploy/setup.sh`).

## Stories & comments

`/stories` holds longer-form content (Human of Bundjalung interviews, news) - Markdown body,
optional hero image and YouTube video, draft/published state. Public visitors can comment
(name + email, email never shown) with a moderation queue in `/admin/comments`:

- A hidden honeypot field silently discards obvious bots.
- A visitor's first comment is held for review; once you approve one comment from an email
  address, later comments from that address post immediately.
- Comments support one level of replies.
- Consider adding Cloudflare Turnstile (free) to the comment form once the domain/Cloudflare
  step is done, for stronger bot protection than the honeypot alone.

The same `comments` table (`target_type`/`target_id`) already supports gig pages too - wiring
that up later is a small, low-risk addition, not a rebuild.

## Notes

- Page views are counted server-side (see the admin dashboard). If you later make Cloudflare cache
  HTML, switch to Cloudflare Web Analytics, since cached pages never reach the server.
- Public pages are cached for 5 minutes (`Cache-Control: max-age=300`) to keep load low on a 1GB
  box - a browser that already loaded a page (e.g. right after posting a comment) may show a stale
  copy for up to 5 minutes; a hard refresh always shows the current state. Admin pages are never cached.
- Featured gigs (paid placement) are pinned to the top of the guide and highlighted.
- Put Cloudflare in front once a domain is chosen: free SSL, caching and DDoS protection.
