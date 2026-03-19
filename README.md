# PredictMyGrade

PredictMyGrade is a portfolio Django product mockup for student progress tracking, grade forecasting, study planning, and premium upsell journeys. It is intended for demonstration and local review only, not as a live student service or production SaaS.

## Mock-Only Status

- This repository should be treated as a demo/portfolio build.
- Billing and subscription flows are simulated only.
- The app contains real Django plumbing such as authentication, database persistence, and optional integration hooks, but those exist to support the mock product experience locally.
- Nothing in this repository should be presented as a live commercial, legal, or compliance-ready platform without further work.

## What This Project Demonstrates

- End-to-end product design rather than a single isolated feature
- Django application architecture with authentication, admin tooling, services, and background-task hooks
- AI-assisted demo flows with safe fallback behaviour when no API key is configured
- Premium feature gating and mock billing flows suitable for demos and local review
- Automated testing across backend and browser-level smoke flows

## Core Features

- Student dashboard with weighted averages, progress summaries, and prediction-style demo metrics
- Module management for university and GCSE-style workflows
- Study planning tools, goals, deadlines, snapshots, and calendar export
- AI-assisted reporting, mentor chat, planning helpers, and what-if forecasting demos
- Mock premium checkout and cancellation flows for demo and local testing
- Admin tools for analytics, billing visibility, system health, and user management

## Tech Stack

- Python / Django 5
- SQLite for local development, PostgreSQL-ready via `DATABASE_URL`
- django-allauth for local/demo authentication flows
- Mock billing flow for demo-only premium upsell behaviour
- OpenAI Python SDK for optional local AI integration
- Playwright for end-to-end smoke tests

## Architecture Notes

- `core/` contains the main product logic: models, views, forms, services, tasks, and tests
- `config/` holds Django settings, URL routing, and deployment configuration
- `templates/` and `static/` provide the server-rendered frontend
- `e2e/` contains Playwright smoke coverage for key user journeys

## Local Setup

1. Create and activate a virtual environment.
2. Install Python dependencies.
3. Copy `.env.example` to `.env`.
4. Run migrations.
5. Start the development server.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Environment Variables

Required:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL`

Local development can use SQLite:

```env
DATABASE_URL=sqlite:///db.sqlite3
```

Useful local defaults:

- `DJANGO_DEBUG=true`
- `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,testserver`
- `BILLING_MOCK_MODE=1`
- `OPENAI_API_KEY=`
- `OPENAI_CHAT_MODEL=gpt-4o-mini`
- `AI_CHAT_DAILY_LIMIT=20`
- `ONBOARDING_SAMPLE_DATA_ENABLED=true`

Optional integrations:

- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`
- `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`

## Main Routes

- `/` and `/dashboard/`
- `/modules/`
- `/what-if/`
- `/reports/ai/`
- `/pricing/`
- `/upgrade/`
- `/manage-subscription/`
- `/settings/`
- `/admin/hub/`

## Demo Notes

This repository is mock-first:

- billing and checkout are simulated locally
- no real payment method is collected
- `/payment/success/` upgrades the signed-in user in-app for demo purposes
- `/billing/cancel/` cancels the mock subscription
- authentication and saved records exist for local testing and portfolio walkthroughs
- optional AI behaviour can call OpenAI if `OPENAI_API_KEY` is configured, but otherwise falls back to preview/demo behaviour
- legal and privacy pages should be treated as placeholder portfolio content unless reviewed and replaced for a real launch

## AI Behavior

- AI features use `OPENAI_API_KEY` only when you explicitly configure it.
- Some premium assistant and forecast flows fall back to non-live or preview behaviour when no API key is configured.
- Free users still have limited preview behaviour in parts of the assistant flow.
- If you want the project to remain strictly mock-only, leave `OPENAI_API_KEY` blank.

## Testing

Backend test suite:

```powershell
$env:DJANGO_SECRET_KEY='dev-secret-key'
$env:DATABASE_URL='sqlite:///db.sqlite3'
$env:DJANGO_DEBUG='true'
python manage.py check
python manage.py test
```

Playwright smoke tests:

```powershell
npm install
npm run test:e2e
```

The Playwright config boots Django on `http://127.0.0.1:8001` with mock billing and a local SQLite database. Session state used by the tests is generated automatically during `globalSetup`.

## Deployment

Production deployment guidance lives in [DEPLOYMENT.md](DEPLOYMENT.md).

In short:

- use `DJANGO_DEBUG=false`
- use a strong `DJANGO_SECRET_KEY`
- set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`
- prefer PostgreSQL in hosted environments
- run `python manage.py collectstatic --noinput` before serving the app
