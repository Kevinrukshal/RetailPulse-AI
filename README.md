# RetailPulse AI

RetailPulse AI is a local-first retail analytics platform that will turn CSV and Excel
sales data into validated PostgreSQL records, business KPIs, read-only FastAPI endpoints,
and Power BI-ready views. It is designed as an interview-friendly portfolio project for
analytics, BI, data engineering, and junior backend roles.

> Project status: Phase 5 platform foundation. The normalized PostgreSQL schema, Alembic
> migration, Docker Compose environment, and database-aware health endpoint are available.
> Transactional ETL loading and analytics follow in later verified phases.

## Planned MVP

The first complete vertical slice will provide:

```text
CSV/XLSX -> map -> validate -> reject/report -> transform -> PostgreSQL
         -> analytical summary view -> FastAPI -> tests
```

Synthetic sample data and every insight derived from it will be clearly labeled as
demonstration content. A configurable column-mapping layer will allow a real public
dataset to be introduced without rewriting the pipeline.

## Architecture decisions

- Normalized `customers`, `products`, `orders`, and `order_items` tables preserve clear
  business entities and avoid update anomalies.
- Power BI consumes denormalized analytical views rather than the transactional tables.
- ETL runs from the command line; the API remains stateless and read-only.
- Settings come from environment variables, logs go to standard output as JSON, and
  secrets stay outside source control.
- AI is disabled and has no package or dependency until the core platform is stable.

## Requirements

- Windows with PowerShell
- Python 3.14 (the project rejects Python 3.15 until dependencies are revalidated)
- Git
- Docker Desktop with Docker Compose for later phases
- Power BI Desktop for later manual dashboard validation

## Phase 1 setup

Run these commands from the repository root:

```powershell
python --version
docker --version
docker compose version
git --version

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

The expected Python version is `3.14.x`. Change local values in `.env`; never commit it.

## Phase 1 verification

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest tests\unit -v
```

All commands must exit with code `0` before Phase 2 begins.

## Demonstration data and extraction

Regenerate the 750-row synthetic sample and test fixtures with:

```powershell
.\.venv\Scripts\python.exe scripts\generate_sample_data.py
```

The public extraction function is `etl.extract.extract_sales_data`. It accepts `.csv` and
`.xlsx` paths, returns a Pandas DataFrame, selects the first usable Excel worksheet, and
raises clear domain exceptions for missing, empty, encoded, unsupported, or unreadable
inputs. Optional source-to-canonical aliases support future public datasets without ETL
rewrites.

The generated records are fictional demonstration data. Do not present findings from them
as real business conclusions.

## Validation and quality scoring

`etl.validate.validate_sales_data` preserves the source DataFrame and returns separate
valid and rejected DataFrames. Every rejected row contains all applicable machine-readable
reason codes. Unreasonable profit is retained as a warning for investigation rather than
silently discarded.

The quality score is:

```text
round(100 * valid_rows / total_rows, 2)
```

A row with several issues counts once as rejected. `etl.quality_report.write_quality_outputs`
writes valid and rejected CSVs plus machine-readable JSON and human-readable Markdown.

## Deterministic transformation

`etl.transform.transform_sales_data` standardizes validated values, parses dates and
numerics, and derives calendar fields, profit margin, revenue per unit, discount band, and
profit status. It also attaches the ETL run ID, source SHA-256, UTC load timestamp, and a
stable order-item key. The key combines source hash, order ID, product ID, and source row
number, preserving legitimate repeated products while making the same-file rerun stable.

## PostgreSQL and Docker Compose

Copy the local environment template once, then build the three services:

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
docker compose exec api alembic upgrade head
Invoke-RestMethod http://localhost:8000/health
```

Expected local services:

- FastAPI and Swagger: `http://localhost:8000` and `http://localhost:8000/docs`
- PostgreSQL 16: `localhost:5432`
- pgAdmin: `http://localhost:5050`

The API image runs as a non-root user and logs to standard output. Compose uses named
volumes for PostgreSQL and pgAdmin, binds `data/` for ETL artifacts, waits for PostgreSQL
health, and applies Alembic migrations before starting Uvicorn. Ports and credentials come
from `.env`; never commit that file.

### Normalized model versus a star schema

The initial model separates customers, products, order headers, order items, ETL runs,
quality results, and rejected records. This reduces duplicated descriptive data and makes
loading and auditing easy to explain. A dimensional star schema would copy descriptive
attributes into dedicated dimensions around a sales fact table for reporting performance.
RetailPulse initially keeps normalized source-of-truth tables and exposes denormalized SQL
views to Power BI; a dedicated dimensional layer can be added later if scale justifies it.

## Configuration

`app/core/config.py` uses Pydantic Settings v2. Environment variables override defaults;
`.env.example` documents the supported local values. `AI_ENABLED=false` is the only
supported AI mode during the MVP foundation.

## Roadmap

1. Project foundation and developer tooling.
2. CSV/XLSX extraction, mapping, validation, transformation, and quality reports.
3. PostgreSQL schema, Alembic migrations, idempotent loading, and ETL orchestration.
4. Analytics views and versioned FastAPI endpoints.
5. Docker Compose hardening and end-to-end test coverage.
6. Power BI guidance, CI, and portfolio documentation.
7. Safe AI business assistant after the non-AI platform is stable.

Possible future deployment targets include Render, Railway, Azure, and AWS. No cloud
infrastructure is included in the local-first MVP.

## Author

Kevin

- Full name: _Not provided_
- GitHub: _Not provided_
- LinkedIn: _Not provided_
- Email: _Not provided_

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
