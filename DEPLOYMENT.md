# Deployment & Security Checklist

This project now ships with sane defaults for public hosting (secure cookies, CSP, WhiteNoise, logging). Use this guide as a run-book when deploying to a production host (e.g. DigitalOcean, Railway, Fly.io, Render, Heroku, Azure, etc.).

## 1. Environment configuration

| Variable | Purpose |
| --- | --- |
| `DJANGO_DEBUG=false` | Always set to `false` in Render/production secrets; only enable `true` in local/dev shells. |
| `DJANGO_SECRET_KEY=<strong random>` | Required to protect sessions. |
| `DJANGO_ALLOWED_HOSTS=predictmygrade.com` | Comma separated hostnames that may serve the site (add platform domains or staging as needed). |
| `DJANGO_CSRF_TRUSTED_ORIGINS=https://predictmygrade.com` | Matches HTTPS origins for CSRF protection; include any additional domains you deploy. |
| `DATABASE_URL=postgres://...` | PostgreSQL connection string; the project now refuses to start without it so there is no SQLite fallback. |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis/CloudAMQP connection strings if Celery workers are used. |
| `EMAIL_*` | SMTP credentials for sending transactional mail. |
| `STRIPE_*` | Your live Stripe keys before charging customers. |
| `OPENAI_API_KEY` | Only if AI features are required in production. |
| `PREMIUM_BACKUP_DIR` | Optional path that tells `run_premium_backup` where to persist premium/trial CSV exports (defaults to `backups/` in the repo). |

WhiteNoise is now enabled, so collect static assets (`python manage.py collectstatic --noinput`) and keep `STATICFILES_STORAGE=whitenoise.storage.CompressedManifestStaticFilesStorage` in sync with this repo before bundling assets for Render.

Focus on a live PostgreSQL database for every environment. `db.sqlite3` no longer ships with the repo and the settings guard against falling back to SQLite.

Optional overrides are documented inline in `config/settings.py` (e.g. cookie policies, CSP, logging verbosity).

## 2. Build steps

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py createsuperuser  # once, for admin access
```

When targeting Render (or another host that runs a single shell command), combine the steps so `pip` only sees its options. For example:

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py createsuperuser
```

If you run Celery tasks, provision at least one worker (`celery -A config worker -l info`) and, if you rely on the beat schedule defined in settings, a beat process (`celery -A config beat -l info`).

## 3. Application server

Run Django behind a process manager (or platform supervisor) using WSGI/ASGI. Example systemd service:

```
ExecStart=/path/to/venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
Environment="DJANGO_DEBUG=false"
Environment="DJANGO_ALLOWED_HOSTS=app.example.com"
...
```

Terminate TLS in a reverse proxy (Nginx, Caddy, Traefik, platform load balancer) and forward `X-Forwarded-Proto` so Django respects the `SECURE_PROXY_SSL_HEADER`.

## 4. Security & reliability checklist

- [x] `DEBUG` is `false` and superuser credentials are strong/unique.
- [x] HTTPS enforced via the proxy + `SECURE_SSL_REDIRECT`.
- [x] `collectstatic` has been run (WhiteNoise serves versioned assets).
- [x] Database backups scheduled; secrets stored in a vault or platform config.
- [x] `python manage.py check --deploy` passes.
- [x] Monitoring in place (e.g. health checks, Sentry/Rollbar, server metrics).
- [x] Log retention configured (logs now emit structured lines and mail admins on 500s).
- [x] HTTP response headers include a strong Content-Security-Policy (e.g. `Content-Security-Policy: default-src 'self'; img-src * data:; style-src 'self' 'unsafe-inline';`).

## 5. Backups & monitoring

- Snapshot the managed Postgres instance daily. Use platform backups or `pg_dump`.
- Enable error tracking (Sentry or similar) by installing the SDK and wiring its DSN in settings.
- Use an uptime/SSL monitor (StatusCake, BetterStack, Cronitor, etc.).

Keeping this checklist with the repo ensures every deployment is repeatable and secure. Update it as your infrastructure evolves.
