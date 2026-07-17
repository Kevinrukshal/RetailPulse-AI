# Analytics API

The API is versioned under `/api/v1`, serves analytics only, and exposes no ETL or database-write
route. The assistant uses POST for a question body but executes read-only analytics.
Interactive OpenAPI documentation is available at `/docs` while the stack is running.

| Endpoint | Purpose | Notable query parameters |
|---|---|---|
| `/summary` | Executive KPIs | date, region, category, subcategory |
| `/revenue/monthly` | Monthly trend | date, region, category, subcategory |
| `/products/top` | Ranked products | filters, `limit`, allowlisted `sort_by` |
| `/products/loss-making` | Negative-profit products | filters, `limit` |
| `/customers/top` | Lifetime customer ranking | `region`, `limit`, `sort_by` |
| `/customers/segments` | RFM segment summary | `region` |
| `/regions/performance` | Region KPIs | date/category filters |
| `/profit-leakage` | Weak line economics | filters, `limit` |
| `/data-quality/latest` | Latest completed quality result | none |
| `/etl-runs` | Paginated execution history | `limit`, `offset` |
| `/assistant/status` | Non-secret AI availability and supported intents | none |
| `/assistant/query` | Grounded answer and exact evidence (`POST`) | JSON question body |

Dates use ISO `YYYY-MM-DD`. A start date after the end date returns `422`; invalid limits or sort
values also return `422`. Empty analytical result sets return an empty list or zero-valued summary,
not a fabricated finding. Database unavailability returns a safe `503` without credentials or SQL.

Examples:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/summary
Invoke-RestMethod "http://localhost:8000/api/v1/products/top?category=Furniture&limit=5"
Invoke-RestMethod "http://localhost:8000/api/v1/revenue/monthly?start_date=2025-01-01"
```

SQL values are bound parameters. The few dynamic order expressions are selected from explicit
server-side maps. Each request transaction is set read-only at the database level.

This local portfolio API intentionally has no authentication. Before internet exposure, place it
behind an authenticated gateway or add application auth, rate limiting, HTTPS, request-size limits,
and environment-specific CORS origins.

The assistant endpoint is disabled by default. It accepts a 5-500 character question, maps it to a
fixed intent/query, and returns `422` for unsupported questions, `503` when disabled, and `502` for
a provider outage. See `docs/ai_assistant.md` for configuration and safety controls.
