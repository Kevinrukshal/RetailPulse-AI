# RetailPulse AI

RetailPulse AI is a local-first retail analytics platform that turns CSV and Excel
sales data into validated PostgreSQL records, business KPIs, read-only FastAPI endpoints,
and Power BI-ready views. It is designed as an interview-friendly portfolio project for
analytics, BI, data engineering, and junior backend roles.

> Project status: v1.1.0. The release-verified analytics platform now includes an optional,
> disabled-by-default, grounded AI business assistant. All bundled findings use synthetic
> demonstration data.

## What it demonstrates

- CSV/XLSX ingestion with configurable aliases and explicit domain errors.
- Multi-reason row validation, rejected-record quarantine, and auditable quality scoring.
- Deterministic transformations and transactional, idempotent PostgreSQL loading.
- Alembic-managed normalized tables plus six BI-oriented analytical views.
- A versioned read-only FastAPI surface with filters, pagination, and safe failures.
- A reproducible four-page Power BI specification and DAX measure library.
- A guarded AI narrator over deterministic intents, reviewed SQL, and local documentation.
- Docker Compose operations and PostgreSQL-backed CI with an 80% coverage gate.

The complete vertical slice is:

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
- AI is disabled by default; its provider SDK is isolated in the optional `ai` package extra.

## Requirements

- Windows with PowerShell
- Python 3.14 (the project rejects Python 3.15 until dependencies are revalidated)
- Git
- Docker Desktop with Docker Compose
- Power BI Desktop only when building the optional report

## Quick start

Run these commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api python -m etl.pipeline --file data/sample/sample_sales.csv
Invoke-RestMethod http://localhost:8000/api/v1/summary
```

The expected Python version is `3.14.x`. Change local values in `.env`; never commit it.

## Local verification

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
docker compose exec -e RUN_INTEGRATION_TESTS=1 api pytest --cov=ai --cov=app --cov=etl
```

All commands must exit with code `0` before a release is accepted.

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

## Run the ETL pipeline

With the Compose stack healthy, run the sample inside the API container:

```powershell
docker compose exec api python -m etl.pipeline --file data/sample/sample_sales.csv
```

For a local Python process, set `DATABASE_URL` to a reachable PostgreSQL host and run:

```powershell
.\.venv\Scripts\python.exe -m etl.pipeline --file data\sample\sample_sales.csv
```

The command exits with `0` on success, `2` for source/validation problems, `3` for database
problems, and `1` for unexpected failures. It writes valid/rejected CSV files and JSON/
Markdown quality reports under `data/processed` and `data/rejected`. Each execution gets a
new ETL run record; the stable order-item key prevents the same file from duplicating sales
facts when it is processed again.

## SQL analytics

Alembic creates six read-only views from `sql/views.sql`:

- `executive_summary`
- `monthly_performance`
- `product_performance`
- `customer_performance`
- `regional_performance`
- `profit_leakage`

`sql/analysis_queries.sql` contains 22 executable, documented analyses using CTEs, window
functions, ranking, `CASE`, date functions, joins, and aggregation. These cover executive
KPIs, trends, product/customer/region performance, RFM, discount impact, and profit leakage.
Any result from the bundled synthetic dataset is a demonstration finding only.

## Analytics API

Swagger UI is available at `http://localhost:8000/docs`. The read-only endpoints are:

```text
GET /health
GET /api/v1/summary
GET /api/v1/revenue/monthly
GET /api/v1/products/top
GET /api/v1/products/loss-making
GET /api/v1/customers/top
GET /api/v1/customers/segments
GET /api/v1/regions/performance
GET /api/v1/profit-leakage
GET /api/v1/data-quality/latest
GET /api/v1/etl-runs
GET /api/v1/assistant/status
POST /api/v1/assistant/query
```

Fact-level endpoints accept appropriate `start_date`, `end_date`, `region`, `category`, and
`subcategory` filters. Ranked endpoints validate `limit` and `sort_by`; ETL history uses
`limit` and `offset`. SQL parameters are bound, sort expressions are allowlisted, and API
database transactions are explicitly read-only.

## Power BI dashboard handoff

The dashboard package avoids committing an opaque `.pbix` binary while making the report
reproducible:

- [`dashboard/README.md`](dashboard/README.md) defines pages, visuals, and acceptance criteria.
- [`dashboard/powerbi_data_dictionary.md`](dashboard/powerbi_data_dictionary.md) documents grains,
  fields, aggregations, and optional relationships.
- [`dashboard/measures.dax`](dashboard/measures.dax) provides fact-model and views-only measures.
- [`docs/powerbi_setup.md`](docs/powerbi_setup.md) covers connection, modeling, refresh, security,
  and reconciliation to PostgreSQL and the API.

All supplied KPI values are deterministic outputs from synthetic demonstration data.

## Configuration

`app/core/config.py` uses Pydantic Settings v2. Environment variables override defaults and
`.env.example` documents all values. Keep `AI_ENABLED=false` for the core-only platform. To use
the narrator, set `INSTALL_AI=true`, configure the provider key/model, and rebuild the API image.
The detailed threat model and examples are in [the AI assistant guide](docs/ai_assistant.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Database design](docs/database.md)
- [Analytics API](docs/api.md)
- [Guarded AI assistant](docs/ai_assistant.md)
- [Demonstration business insights](docs/business_insights.md)
- [Deployment](docs/deployment.md)
- [Power BI setup](docs/powerbi_setup.md)

No cloud infrastructure is claimed by this local-first release.

## Author

Kevin

- Full name: _Not provided_
- GitHub: _Not provided_
- LinkedIn: _Not provided_
- Email: _Not provided_

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
