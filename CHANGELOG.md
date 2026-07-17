# Changelog

All notable changes to RetailPulse AI are documented here.

## 1.1.0 - 2026-07-17

### Added

- Disabled-by-default AI business assistant with six deterministic intents.
- Static, read-only SQL catalog with row caps, statement timeouts, and source allowlisting.
- Local documentation retrieval and evidence/source disclosure in every assistant response.
- Optional OpenAI Responses API narrator installed through the `ai` package extra.
- Offline provider fakes, prompt-injection checks, and PostgreSQL-backed intent tests.

## 1.0.0 - 2026-07-17

### Added

- Deterministic synthetic retail dataset and configurable CSV/XLSX extraction.
- Multi-reason validation, quality reports, warnings, and rejected-row quarantine.
- Deterministic transformations with stable order-item lineage keys.
- Normalized PostgreSQL schema, Alembic migrations, audit tables, and Docker Compose stack.
- Transactional, idempotent ETL CLI with rollback-safe failure auditing.
- Six analytical views and 22 executable business-analysis queries.
- Versioned, filtered, read-only FastAPI analytics endpoints and OpenAPI contracts.
- Reproducible Power BI model, DAX measures, dashboard specification, and data dictionary.
- PostgreSQL-backed CI, 80% coverage gate, and portfolio/deployment documentation.

### Notes

- All bundled records and numerical findings are synthetic demonstration content.
- AI remains disabled and outside the v1.0.0 dependency/runtime surface.
