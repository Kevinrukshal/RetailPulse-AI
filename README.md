# RetailPulse AI

RetailPulse AI is a local-first retail analytics platform that turns CSV and Excel
sales data into validated PostgreSQL records, business KPIs, read-only FastAPI endpoints,
and Power BI-ready views. It is designed as an interview-friendly portfolio project for
analytics, BI, data engineering, and junior backend roles.

> Project status: v1.2.0. The release-verified analytics platform includes a browser upload
> dashboard and an optional, disabled-by-default, grounded AI business assistant. All bundled
> findings use synthetic demonstration data.

## What it demonstrates

- CSV/XLSX ingestion with configurable aliases and explicit domain errors.
- Multi-reason row validation, rejected-record quarantine, and auditable quality scoring.
- Deterministic transformations and transactional, idempotent PostgreSQL loading.
- Alembic-managed normalized tables plus six BI-oriented analytical views.
- Versioned read-only analytics endpoints with filters, pagination, and safe failures.
- A responsive browser dashboard with bounded CSV/XLSX upload and automatic refresh.
- A reproducible four-page Power BI specification and DAX measure library.
- A guarded AI narrator over deterministic intents, reviewed SQL, and local documentation.
- Docker Compose operations and documented local verification commands.

The complete vertical slice is:

```text
CSV/XLSX -> map -> validate -> reject/report -> transform -> PostgreSQL
         -> analytical summary view -> FastAPI -> tests
```

Synthetic sample data and every insight derived from it will be clearly labeled as
demonstration content. A configurable column-mapping layer will allow a real public
dataset to be introduced without rewriting the pipeline.

## Requirements

- Windows with PowerShell
- Python 3.14 (the project rejects Python 3.15 until dependencies are revalidated)
- Git
- Docker Desktop with Docker Compose
- Power BI Desktop only when building the optional report

## Quick start

Set strong database/pgAdmin passwords and a random `API_ACCESS_TOKEN` in `.env`
before starting Compose; see [local access and data protection](docs/project-reference.md#local-access-and-data-protection).

Run these commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
# Configure the passwords and API_ACCESS_TOKEN in .env before continuing.
docker compose up --build -d
docker compose exec api python -m etl.pipeline --file data/sample/sample_sales.csv
Start-Process http://localhost:8000
```

The browser opens the RetailPulse dashboard. Choose a CSV/XLSX file, select **Process file**,
then explore Overview, Products, Customers, Regions, Data quality, and Profit leakage. The
expected Python version is `3.14.x`. Change local values in `.env`; never commit it.

## Local verification

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
docker compose exec -e RUN_INTEGRATION_TESTS=1 api pytest --cov=ai --cov=app --cov=etl
```

All commands must exit with code `0` before a release is accepted.

## Repository layout

- `app/`: FastAPI routes, services, database models and browser dashboard assets.
- `etl/`: extraction, validation, transformations and loading.
- `ai/`: optional grounded assistant.
- `migrations/` and `sql/`: database evolution, views and analytical queries.
- `dashboard/`: reproducible Power BI specifications and DAX measures.
- `data/sample/`: synthetic demonstration inputs.
- `scripts/`, `tests/` and `docs/`: maintenance, verification and guides.

## Documentation

- [Project reference](docs/project-reference.md): architecture decisions, extraction,
  validation, ETL commands, SQL, API contracts, configuration and data protection.
- [Architecture](docs/architecture.md)
- [Database design](docs/database.md)
- [Analytics API](docs/api.md)
- [Browser dashboard](docs/web_dashboard.md)
- [Guarded AI assistant](docs/ai_assistant.md)
- [Demonstration business insights](docs/business_insights.md)
- [Deployment](docs/deployment.md)
- [Power BI setup](docs/powerbi_setup.md)

No cloud infrastructure is claimed by this local-first release.

## Author

Kevin Rukshal

- [GitHub](https://github.com/Kevinrukshal)
- [LinkedIn](https://www.linkedin.com/in/kevinrukshal/)
- [Email](mailto:contact@kevinrukshal.com)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
