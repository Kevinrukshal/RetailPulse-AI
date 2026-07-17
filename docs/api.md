# Analytics API

The API is versioned under `/api/v1`, serves analytics only, and exposes no ETL or write route.
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

