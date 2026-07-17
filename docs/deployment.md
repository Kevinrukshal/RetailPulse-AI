# Deployment Guide

The supported v1.0 target is local Docker Compose. Cloud providers are possible future targets;
none is implied to be production-ready by this repository.

## Local deployment

```powershell
Copy-Item .env.example .env
# Replace every change_me value in .env.
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
restrict CORS, and never commit or paste that file into tickets. `AI_ENABLED=false` is the only
supported v1.0 mode. The API container is non-root, but local port publishing still exposes services
to the host network.

## Production checklist

- Run PostgreSQL as a managed/private service with backups, TLS, patching, and least privilege.
- Build a production image without development dependencies and pin it by digest or release tag.
- Run Alembic as a one-off release job before starting API replicas.
- Put the API behind HTTPS, authentication, rate limits, access logs, and a restrictive CORS policy.
- Do not publish PostgreSQL or pgAdmin ports to the public internet.
- Add centralized logs, metrics, traces, uptime checks, alerting, and tested restore procedures.
- Separate ETL, API, migration, and BI identities; the API and BI identities should be read-only.
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
