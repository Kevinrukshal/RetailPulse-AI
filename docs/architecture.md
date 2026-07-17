# Architecture

RetailPulse is a local-first, layered analytics platform. It keeps ingestion concerns separate
from read-only analytics serving; one explicit, bounded HTTP upload route invokes the same audited
ETL used by the command line.

```text
CSV / XLSX
    |
    v
extract -> map -> validate -> reject/report -> transform -> transactional load
                                                        |
                                                        v
                                                PostgreSQL 16
                                             /        |       \
                                    analytics views  audit   normalized data
                                         |                         |
                            FastAPI analytics + upload         Power BI
```

## Component boundaries

- `etl/` owns extraction, aliases, row validation, deterministic transformation, quality
  artifacts, transactional loading, and the CLI orchestration contract.
- `app/database/` owns SQLAlchemy models and connection lifecycle; Alembic owns schema changes.
- `sql/` contains reviewable business views and analytical queries.
- `app/services/` executes bound, allowlisted analytics queries; `app/api/` validates HTTP input
  and serializes Pydantic contracts.
- `dashboard/` and `docs/powerbi_setup.md` are the reproducible BI delivery layer.

## Design choices

The source of truth is normalized to customers, products, order headers, and order lines. This
supports idempotent updates and clear foreign keys. Denormalized views give BI consumers stable,
business-oriented grains without duplicating transactional storage.

Every order-item key is a SHA-256 of source hash, order ID, product ID, and source row number.
The entire database load occurs in one transaction, while each execution receives an audit run.
Invalid rows are quarantined with all reasons; unreasonable profit remains a warning rather than
being silently removed.

Analytics routes open read-only transactions, use bound SQL parameters, and allowlist dynamic
sorts. The upload route validates and deletes its temporary file around a transactional ETL run.
Secrets come from environment variables. Containers run the application as a non-root user.

## Operational properties

- Deterministic sample generation and transformation.
- Same-file reruns do not duplicate facts.
- Alembic migrations and analytical views are reproducible from an empty database.
- Structured JSON logs go to standard output.
- Health checks coordinate PostgreSQL, API, and pgAdmin startup.
- Unit, integration, SQL-view, HTTP, rollback, and idempotency tests run in CI.

## Known scale boundary

The implementation favors clarity for portfolio and small-team use. At higher volume, stage files
with PostgreSQL `COPY`, introduce incremental partitions/materialized views, use a queue for ETL,
and separate operational and BI credentials. These are deliberate future optimizations, not
requirements for the current 750-row demonstration workload.
