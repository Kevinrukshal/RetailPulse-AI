# Deployment Guide

The supported v1.x target is local Docker Compose. Cloud providers are possible future targets;
none is implied to be production-ready by this repository.

## Local deployment

```powershell
Copy-Item .env.example .env
# Fill the blank database/pgAdmin passwords and API_ACCESS_TOKEN with generated secrets.
docker compose config
docker compose up --build -d
docker compose ps
docker compose exec api python -m etl.pipeline --file data/sample/sample_sales.csv
Invoke-RestMethod http://localhost:8000/health
```

Swagger is at `http://localhost:8000/docs`; pgAdmin is at `http://localhost:5050`. Stop services
with `docker compose down`. Do not add `-v` unless intentionally deleting local database volumes.

## Configuration and secrets

`.env.example` is documentation only. Generate strong database and pgAdmin passwords in `.env`,
restrict CORS, and never commit or paste that file into tickets. AI is disabled by default. Enabling
it requires `INSTALL_AI=true`, `AI_ENABLED=true`, and provider credentials before rebuilding; see
`docs/ai_assistant.md`. The API container is non-root, but local port publishing still exposes
services to the host network.

## Production checklist

- Run PostgreSQL as a managed/private service with backups, TLS, patching, and least privilege.
- Build a production image without development dependencies and pin it by digest or release tag.
- Run Alembic as a one-off release job before starting API replicas.
- Put the API behind HTTPS, authentication, rate limits, access logs, and a restrictive CORS policy.
- Do not publish PostgreSQL or pgAdmin ports to the public internet.
- Add centralized logs, metrics, traces, uptime checks, alerting, and tested restore procedures.
- Separate ETL/upload, analytics, migration, and BI identities; analytics and BI should be read-only.
- Scan dependencies/images and define retention for source, rejected, and audit data.

## Release and rollback

Create a database backup, test migrations against a production-like copy, deploy the migration,
then deploy the matching immutable API image. Application rollback uses the previous image. Schema
downgrade should occur only when the migration explicitly preserves compatibility and has been
tested; forward-fix is safer after destructive or data-shaping migrations.

## Power BI Service

Power BI Desktop connects directly to local PostgreSQL. Service refresh requires either an
on-premises data gateway to the local network or a securely hosted PostgreSQL endpoint. Configure
credentials in the Power BI service and grant access only to approved reporting views.

## Local access and data protection

Before starting, set a random `API_ACCESS_TOKEN` of at least 32 characters in `.env`
(generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`).
All `/api/v1/` endpoints require `Authorization: Bearer <token>`; missing configuration
fails closed. Unlock the dashboard with this token; it is kept only in page memory,
never browser storage or a URL. Reload or sign out to forget it. This is single-operator
access, not per-user permissions. Rotate the token by changing `.env` and restarting.
Compose binds services to loopback; pgAdmin requires login. Keep strong database and
pgAdmin passwords. Existing pgAdmin volumes may retain older configuration; verify its
login screen. Use HTTPS and rate limits before any remote access.

Uploads allow at most 100,000 rows. XLSX archives are limited to 1,000 entries and
50 MiB expanded size. Files exceeding limits are rejected, never silently truncated.
AI additionally requires `AI_EXTERNAL_SHARING_ENABLED=true`. Customer names/IDs and
free-form user questions are excluded from provider requests; selected commercial
metrics and approved documentation still leave the machine. Keep disabled for confidential
data unless that sharing is authorized. Uploaded data and generated reports remain on disk;
remove these deliberately according to your retention policy.

API access is limited to 120 attempts per source address per minute in each process.
The bounded in-memory limit resets on restart; use a gateway limit for multiple workers.

Uploads are disabled by default. Set `UPLOAD_ENABLED=true` explicitly to enable imports.
XLSX parsing additionally caps columns at 256 and total worksheet cells at 2,000,000,
checks cell coordinates before pandas, and rejects XML entity expansion.

Generate separate database, pgAdmin, and API secrets with `python -c "import secrets;
print(secrets.token_urlsafe(32))"`. Fill the blank password values before Compose starts.
Leave `DATABASE_URL` empty when using individual PostgreSQL settings outside Compose.
Assistant JSON is capped at 16 KiB before parsing, including chunked requests.
The local rate limit uses the ASGI client address: configure trusted proxy addresses explicitly
before remote use; never trust arbitrary forwarded headers. Loopback is the supported default.
