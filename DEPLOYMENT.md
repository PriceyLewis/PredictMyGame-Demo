# Optional Deployment Notes

This repository is a portfolio/demo project. It is not presented as a production-ready service, and this file should not be read as an endorsement to launch it publicly without substantial additional work.

## Purpose Of This File

These notes exist only as developer reference material for anyone exploring how the Django app could be run outside local development. They are not a security checklist, compliance statement, or launch runbook.

## Current Repo Reality

- The project is designed first for local review and portfolio demonstration.
- Billing is mock-only in this codebase.
- Some app behaviour is real Django plumbing, including authentication, persistence, and exports.
- Optional AI requests can call external APIs only if a reviewer explicitly configures them.
- Legal, privacy, and cookie content in the UI are placeholder/demo content and would need full replacement before any real launch.

## If You Run It Outside Local Development

Treat that as a separate engineering project. At minimum you would need to verify and redesign:

- hosting and infrastructure choices
- secrets management
- database operations and backups
- logging, monitoring, and incident handling
- email delivery and domain ownership
- security review and penetration testing
- legal terms, privacy policy, and consent flows
- support processes and ownership
- age gating, moderation, and abuse handling where relevant

## Minimal Technical Starting Point

If you only want to experiment in a non-public environment, the current codebase still expects normal Django setup steps such as:

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py createsuperuser
```

You would also need to configure environment variables such as:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `OPENAI_API_KEY` only if you intentionally want external AI calls

## Recommendation

For this portfolio repository, keep usage local unless you are deliberately converting it into a real product and are prepared to replace the placeholder policy, support, and operational assumptions throughout the stack.
