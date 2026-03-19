# PredictMyGrade

PredictMyGrade is a full-stack Django product mockup for student progress tracking, grade forecasting, study planning, and premium feature upsell flows. It was built as a portfolio project to demonstrate shipping a feature-rich web application with product thinking, backend logic, test coverage, and deployment-ready configuration.

## What This Project Demonstrates

- End-to-end product design rather than a single isolated feature
- Django application architecture with authentication, admin tooling, services, and background-task hooks
- AI-assisted features with safe fallback behaviour when no API key is configured
- Premium feature gating and mock billing flows suitable for demos and local review
- Automated testing across backend and browser-level smoke flows

## Core Features

- Student dashboard with weighted averages, progress summaries, and AI prediction metrics
- Module management for university and GCSE-style workflows
- Study planning tools, goals, deadlines, snapshots, and calendar export
- AI-powered reporting, mentor chat, planning helpers, and what-if forecasting
- Mock premium checkout and cancellation flows for demo and local testing
- Admin tools for analytics, billing visibility, system health, and user management

## Tech Stack

- Python / Django 5
- SQLite for local development, PostgreSQL-ready via `DATABASE_URL`
- django-allauth for authentication and social sign-in
- Stripe integration with mock mode support
- OpenAI Python SDK for AI features
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

- `STRIPE_PUBLIC_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_PRICE_ID_MONTHLY`
- `STRIPE_PRICE_ID_YEARLY`
- `STRIPE_WEBHOOK_SECRET`
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

With `BILLING_MOCK_MODE=1`:

- checkout is simulated locally
- no real payment method is collected
- `/payment/success/` upgrades the signed-in user in-app
- `/billing/cancel/` cancels the mock subscription

To use live Stripe, set `BILLING_MOCK_MODE=0` and provide the Stripe keys and price IDs listed above.

## AI Behavior

- AI features use `OPENAI_API_KEY` when available.
- Some premium assistant and forecast flows fall back to non-live or preview behaviour when no API key is configured.
- Free users still have limited preview behaviour in parts of the assistant flow.

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
