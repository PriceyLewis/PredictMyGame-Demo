# PredictMyGrade Dashboard Enhancements

## Premium AI Mentoring
- Weekly AI Digest card (Generate Weekly Digest button) uses OpenAI when `OPENAI_API_KEY` is set.
- Mentor chat now factors in study plans, planned modules, and looming deadlines.

## Smart Insights
- Smart Alerts surface urgent workload and trend warnings.
- Benchmark Snapshot compares your weighted average with the wider cohort.
- Progress Streak tracks consecutive days with saved snapshots.

## Achievements & Milestones
- Automatically unlock badges for progress (average milestones, streaks, module mastery, etc.).
- View achievements at `/milestones/` and share public cards with unique tokens.
- Achievement data feeds into the dashboard bootstrap for instant celebrations.

## What-If Simulator
- Tune study hours and target averages with live sliders to compare projected vs goal outcomes.
- See per-scenario recommendations that highlight how many extra hours you need and where to focus.
- Compare side-by-side scenario summaries, auto-generate an action plan, and export it as JSON for follow-up.

## Data Hygiene Shortcuts
- Upcoming deadlines include a one-click "Done" action.
- Recent modules list supports inline grade edits (0-100) without leaving the dashboard.

## Adaptive Prediction Engine
- Both free and premium forecasts now train on in-app data using regularised regression with richer features (trend, workload, engagement).
- Premium predictions ingest difficulty, variance, and scheduling signals to deliver tighter confidence bands.
- Confidence scores are calibrated from model residuals and surfaced in API responses and dashboard widgets.
- Models retrain themselves weekly via the Celery beat schedule (`config/settings.py:325-345`), and the dashboard now reports the `AIModelStatus.last_retrained_at` timestamp alongside the current RMSE so you can see when the adaptive models last refreshed (`core/templates/core/dashboard.html:1154-1173`).

## Environment Variables
- `DJANGO_DEBUG` (optional, defaults to `false` for safety; set to `true` locally when developing).
- `DJANGO_SECRET_KEY` (required; generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` and store only in envs/secret stores).
- `DJANGO_ALLOWED_HOSTS` (comma separated list of domains for host header validation such as `predictmygrade.com`).
- `DJANGO_CSRF_TRUSTED_ORIGINS` (comma separated origins such as `https://predictmygrade.com`; include any additional served domains).
- `DATABASE_URL` (required; PostgreSQL connection string including credentials and host; the app refuses to start without it because SQLite is no longer supported).
- **Render tip:** create secrets for the above vars and point `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS=predictmygrade.com`, and `DJANGO_CSRF_TRUSTED_ORIGINS=https://predictmygrade.com` to the production domain.
- `DATABASE_CONN_MAX_AGE` / `DATABASE_SSL_REQUIRE` (connection pooling & TLS enforcement; SSL defaults to `true` when `DJANGO_DEBUG=false`).
- `OPENAI_API_KEY` (required for Premium AI features).
- `OPENAI_CHAT_MODEL` (optional, defaults to `gpt-4o-mini`).
- `AI_CHAT_DAILY_LIMIT` (optional, defaults to `20`).
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (required for Google login).
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` (required for GitHub login).
- `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` / `MICROSOFT_TENANT_ID` (required for Microsoft login; set tenant to your Azure tenant ID or `common`).
- `WHAT_IF_HOUR_BOOST` (optional, defaults to `0.65` study-hour gain in the what-if simulator).
- `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID_MONTHLY`, `STRIPE_PRICE_ID_YEARLY`, `STRIPE_WEBHOOK_SECRET` (billing flows).
- `ANALYTICS_SCRIPT_URL` (optional; consent manager injects this URL only after visitors accept analytics cookies).
- `ANALYTICS_DATA_LAYER` (optional, defaults to `dataLayer`; change if your analytics snippet expects a different global).
- `ONBOARDING_SAMPLE_DATA_ENABLED` (optional, defaults to `true`; disable to skip seeding sample dashboard data for new accounts).
- `PREMIUM_BACKUP_DIR` (optional; path where `run_premium_backup` writes backup CSVs, defaults to `backups/` in the project root).

## Database (PostgreSQL)
1. Install PostgreSQL 14+ locally (or point to a managed instance) and create a database/user, for example:
   - `createdb predictmygrade`
   - `createuser predictmygrade --pwprompt`
   - `psql -c "GRANT ALL PRIVILEGES ON DATABASE predictmygrade TO predictmygrade;"`
2. Update `.env` with a managed Postgres URL such as `postgresql://predictmygrade:<password>@localhost:5432/predictmygrade`. The app now refuses to start without this variable to avoid accidental SQLite usage or leaked credentials.
3. `DATABASE_CONN_MAX_AGE` controls persistent connections (seconds). Keep it high (e.g., 600) for Render/Heroku style pools and lower it for short-lived dev shells.
4. TLS is enforced automatically when `DJANGO_DEBUG=false`. Override `DATABASE_SSL_REQUIRE=false` only for vetted local setups where you control the connection.

-## Security Defaults
- Production (`DJANGO_DEBUG=false`) forces `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and HSTS (`SECURE_HSTS_SECONDS=31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`, `SECURE_HSTS_PRELOAD=True`) directly in settings, so there are no separate `DJANGO_SECURE_*` env overrides.
- `SECURE_PROXY_SSL_HEADER` trusts `X-Forwarded-Proto` so HTTPS termination on Render/Heroku keeps redirects accurate.
- CSRF trusted origins must be supplied via `DJANGO_CSRF_TRUSTED_ORIGINS`; localhost/http variants are only appended while developing.
- `SESSION_COOKIE_SAMESITE` and `CSRF_COOKIE_SAMESITE` default to `Lax` in settings; change these in `config/settings.py` if you need cross-site embeds.
- Secrets (Stripe, OpenAI, SMTP, OAuth) are never stored in code—load them via `.env`, Render secret files, or your secret manager.
- WhiteNoise serves compressed/fingerprinted static assets via `STATICFILES_STORAGE=whitenoise.storage.CompressedManifestStaticFilesStorage` once you run `collectstatic`.

## Analytics & Cookie Consent Hooks
- The cookie banner emits a `pmg:analytics-toggle` event whenever a visitor toggles analytics cookies so you can hook in bespoke trackers.
- `window.PMGConsent.acceptAnalytics()` / `.declineAnalytics()` offer programmatic controls for custom UI or testing.
- When `ANALYTICS_SCRIPT_URL` is set, the script tag is injected only after consent and removed again if the visitor opts out.

## Secret Management & Render
1. Copy `.env.example` to `.env` for local development and fill in the values (the file stays out of git via `.gitignore`).
2. When deploying on Render, create a Secret File that contains the same key/value pairs, mount it (e.g. `/etc/secrets/predictmygrade.env`), and add an environment variable called `RENDER_ENV_FILE` that points to that path.
3. You can still use Render's built-in environment variables; the loader in `config/settings.py` only fills values that are missing so anything set in the dashboard wins automatically.

## Brand Assets
- Primary logo: `static/img/predictmygrade-logo.(png|jpg|svg)` — swap these with the final lockup exported in light/dark variants.
- Favicon/Icon set: `static/img/predictmygrade-icon-*.png` and `static/img/predictmygrade-favicon.svg` — generated variants for common resolutions (32–512px).
- Social image: `static/img/predictmygrade-social.png` (1200×630) — controls OpenGraph/Twitter previews.
- Web manifest: `static/manifest.webmanifest` — updates install metadata including theme colors.
- After updating the artwork, run `python manage.py collectstatic` to refresh fingerprinted files before deployment.

## Retraining
Run `python manage.py retrain_ai` or `python manage.py seed_data` to rebuild cached adaptive models from the latest data.

## Third-Party Authentication
- Export the OAuth variables above in the shell that runs Django.

## Manual Verification
1. **Admin premium toggle**
   - Visit `/admin/analytics/` while signed in as a staff user.
   - In the *Quick admin controls* card, enter a target user ID and submit the form.
   - Confirm the toast/status message reflects the new plan and refresh `/admin/users/` to verify the badge updated.
2. **AI reports PDF export**
   - Open `/reports/ai/` with a user who has summaries.
   - Click *Export PDF* and wait for the button to return to the ready state.
   - Ensure the browser downloads `PredictMyGrade_AI_Report.pdf` and that the toast confirmation appears.
- Run `python manage.py sync_social_apps` to create or update SocialApp entries for Google, GitHub, and Microsoft.
- Configure each provider with the redirect URIs `http(s)://<domain>/accounts/<provider>/login/callback/` (add both localhost and production domains).
- Verify `/accounts/login/` renders provider buttons and completes sign-in for each provider.

## Scheduled Jobs (Render free tier)
- Celery is disabled for the free Render web services, so run these management commands via Render cron jobs (or your scheduler of choice) instead of relying on workers:
  * `python manage.py retrain_ai`
  * `python manage.py generate_ai_summaries`
  * `python manage.py send_weekly_report`
  * `python manage.py run_premium_backup`
  * `python manage.py capture_daily_progress_snapshot`
- Each cmd writes structured logs and touches the same models/services that the old Celery beat tasks did, so the dashboards stay fresh even without workers.
- Keep `CELERY_BROKER_URL=memory://`/`CELERY_RESULT_BACKEND=cache+memory://` in place if you ever flip back to a worker-enabled deployment.

## Billing & Premium Access
- Stripe keys are required for checkout flows and premium toggles; add them to the environment before serving `/upgrade/`.
- Premium gating respects free-trial status (`UserProfile.start_free_trial`) and explicit upgrades; tests cover report access for both free and premium users.

## Tests
- Run `python manage.py test core.tests.test_dashboard core.tests.test_auth core.tests.test_admin core.tests.test_what_if` to validate dashboard APIs, premium gating, admin analytics access, domain restrictions, and the enhanced what-if simulator.
